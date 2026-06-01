"""SQLite backend implementing the Backend protocol.

WAL mode + JSONL audit log.  The replay guarantee:
    replay_from_empty(events.jsonl) → state.db identical to original run.

Events are serialised to JSONL *before* the SQLite mutation so that even a
process crash after the JSONL write but before the COMMIT leaves the log
in a state that can be replayed cleanly.

Phase 2 note: only 'project.created' and 'state.initialized' are routed;
Phase 3 extends routing with: prd.parsed, prd.reviewed, prd.approved,
feature.created, task.created, task.scored, task.expanded, task.status_changed.
Phase 4 extends routing with: claim.created, claim.released, claim.renewed,
claim.stale.
Phase 5 extends routing with: evidence.submitted, task.applied.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NamedTuple

from pydantic import BaseModel

from fakoli_state.state.backend import (
    PENDING_EVENT_ID,
    BackendError,  # noqa: F401
    EventRejected,
    IdempotentNoOp,
    SchemaMismatch,
    StateLocked,
    TransactionAborted,
)
from fakoli_state.state.models import (
    PRD,
    Claim,
    ClaimStatus,
    Event,
    Feature,
    Project,
    Requirement,
    Review,
    ReviewDecision,
    Score,
    SyncMapping,
    Task,
)
from fakoli_state.state.payloads import (
    ACTION_TO_PAYLOAD,
    ClaimCreatedPayload,
    ClaimReleasedPayload,
    ClaimRenewedPayload,
    ClaimStalePayload,
    EvidenceSubmittedPayload,
    FeatureCreatedPayload,
    FeatureDeletedPayload,
    FileChangedPayload,
    PrdApprovedPayload,
    PrdParsedPayload,
    PrdReviewedPayload,
    ProgressNotedPayload,
    ProjectCreatedPayload,
    StateInitializedPayload,
    SyncMappingDeletedPayload,
    SyncMappingUpsertedPayload,
    TaskAppliedPayload,
    TaskCreatedPayload,
    TaskDeletedPayload,
    TaskExpandedPayload,
    TaskScoredPayload,
    TaskStatusChangedPayload,
    TaskSyncedFromRemotePayload,
)
from fakoli_state.state.schema import DDL, SCHEMA_VERSION

if TYPE_CHECKING:
    from fakoli_state.clock import Clock
    from fakoli_state.state.models import Evidence

logger = logging.getLogger(__name__)

# Maps the raw ``task.applied`` outcome strings stored in the reviews table to
# their canonical ReviewDecision equivalents.  ``"rejected"`` maps to
# ``needs_changes`` because a rejected task immediately auto-promotes back to
# ``drafted`` for rework (see _handle_task_applied) — it is NOT the terminal
# ``reject`` decision that would permanently close the review.
_TASK_OUTCOME_TO_REVIEW_DECISION: dict[str, str] = {
    "accepted": ReviewDecision.approve,
    "rejected": ReviewDecision.needs_changes,
}


# Signature shared by every ``_check_*`` and ``_write_*`` bound method.
_PhaseFn = Callable[["sqlite3.Connection", Any, "Event"], None]


class ActionSpec(NamedTuple):
    """Dispatch entry for one event action: payload model + decide/apply phases.

    SL1-RR-1 architecture move #1 — every dispatched action is split into a
    validation phase and an infallible mutation phase:

    - ``check(conn, payload, event)`` reads current state and raises
      :class:`EventRejected` on an illegal transition / bad payload, or
      :class:`IdempotentNoOp` on an already-satisfied request. It performs no
      writes.
    - ``write(conn, payload, event)`` performs the mutation and contains no
      validation that can raise a rejection — it assumes ``check`` passed.

    This wave keeps ``apply_event``'s observable behavior unchanged: a
    ``check`` raising ``EventRejected`` flows through ``apply_event``'s existing
    except-block (abort tombstone + ``TransactionAborted``); an
    ``IdempotentNoOp`` is mapped back to the prior warn-and-record behavior by
    ``_apply_mutation``. The strict write-path rewire (``append`` / log-first /
    ``audit.jsonl``) is Task 4.
    """

    payload_model: type[BaseModel]
    check: _PhaseFn
    write: _PhaseFn


def _idempotent_no_op(
    reason: str,
    *,
    warn_action: str | None = None,
    warn_target_id: str | None = None,
) -> IdempotentNoOp:
    """Build an :class:`IdempotentNoOp` carrying optional warn-log metadata.

    Some legal-but-already-satisfied requests historically emitted a
    ``warn.idempotent_no_op`` JSONL line (already-released / already-stale
    claims, double-submitted evidence); others returned silently (a
    status_changed already at its target, a replayed claim.created). The
    ``warn_*`` attributes let ``_apply_mutation`` reproduce exactly the prior
    behavior for each case: when ``warn_action`` is set it re-emits the warn
    log, otherwise it returns silently. ``reason`` is the human-readable detail.
    """
    exc = IdempotentNoOp(reason)
    exc.warn_action = warn_action  # type: ignore[attr-defined]
    exc.warn_target_id = warn_target_id  # type: ignore[attr-defined]
    return exc


class SqliteBackend:
    """Concrete SQLite + JSONL implementation of the Backend protocol.

    Constructor parameters
    ----------------------
    db_path      : absolute path to the SQLite database file.
    events_path  : absolute path to the JSONL event-log file.
    clock        : Clock instance injected for all timestamp generation.
                   Never call datetime.now() directly in this class.

    Lifecycle
    ---------
    b = SqliteBackend(db_path=..., events_path=..., clock=...)
    b.initialize()   # open connection, set PRAGMAs, create schema
    b.apply_event(event)
    ...
    b.close()
    """

    def __init__(
        self,
        *,
        db_path: str,
        events_path: str,
        clock: Clock,
    ) -> None:
        self._db_path = db_path
        self._events_path = events_path
        self._clock = clock
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Open the SQLite connection, set PRAGMAs, apply DDL if needed.

        Idempotent — safe to call multiple times.  Raises SchemaMismatch if
        the on-disk user_version differs from SCHEMA_VERSION.

        Ordering note (P1-3): the pre-DDL ``user_version`` is captured
        BEFORE ``_apply_ddl`` runs because ``_apply_ddl`` unconditionally
        stamps ``PRAGMA user_version = SCHEMA_VERSION`` at the end. If we
        deferred reading until afterward, the v2→v3 migration branch
        would never fire — every reopened db would look "already v3" to
        ``_check_schema_version`` and the missing ALTERs would silently
        not happen.
        """
        if self._conn is not None:
            # Already initialised — verify version and return.
            self._check_schema_version()
            return

        try:
            conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                isolation_level=None,  # autocommit off; we manage transactions explicitly
            )
        except sqlite3.OperationalError as exc:
            raise TransactionAborted(f"Cannot open database at {self._db_path!r}: {exc}") from exc

        # WAL mode for concurrent readers + one writer.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")

        # Row factory enables dict(row) in query helpers.
        conn.row_factory = sqlite3.Row

        self._conn = conn

        # Capture the on-disk version BEFORE _apply_ddl re-stamps it. The
        # v2→v3 migration relies on knowing the original version (the DDL
        # always sets user_version to SCHEMA_VERSION at the end).
        pre_ddl_row = conn.execute("PRAGMA user_version").fetchone()
        pre_ddl_version = pre_ddl_row[0] if pre_ddl_row else 0

        # Apply DDL (CREATE TABLE IF NOT EXISTS — idempotent).
        # Execute statement-by-statement; sqlite3 executescript auto-commits,
        # so we split manually to preserve our transaction control.
        self._apply_ddl()

        # After DDL, verify schema version. Pass the pre-DDL version so the
        # migration logic can decide what (if any) ALTER steps are needed.
        self._check_schema_version(pre_ddl_version=pre_ddl_version)

    def close(self) -> None:
        """Close the SQLite connection cleanly.  Idempotent."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    def next_event_id(self) -> str:
        """Return a hint of the next sequential event ID in E%06d format.

        Queries MAX(id) on the events mirror table without holding a lock.
        Subject to races — do NOT use this to pre-assign IDs for new events
        (Critic-3 flagged the read-before-lock race on PR #41: two concurrent
        processes calling next_event_id() + apply_event() can both observe
        MAX=N, both attempt INSERT E{N+1}, and the second INSERT OR IGNORE
        silently no-ops — event survives in JSONL but is missing from the
        events table; replay produces diverging state.db).

        For race-free ID assignment use PENDING_EVENT_ID + apply_event():
            event = Event(id=PENDING_EVENT_ID, ...)
            event = backend.apply_event(event)  # returns event with real ID

        Kept as a hint/preview API for callers that need the upcoming ID
        without mutating state (e.g., tests that check ID format, legacy
        callers that have not yet been migrated to PENDING_EVENT_ID).

        CL-13: callers must hold an open connection. The previous behavior of
        returning a hardcoded ``"E000001"`` when ``self._conn is None`` was a
        latent footgun — calling ``next_event_id()`` after ``close()`` would
        return a plausible-looking but stale ID guaranteed to collide on the
        next reopen. Route the no-conn branch through ``_require_conn`` like
        every other Backend method so the error is loud and immediate.
        """
        conn = self._require_conn()
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(id, 2) AS INTEGER)) FROM events"
        ).fetchone()
        max_num: int = row[0] if row and row[0] is not None else 0
        return f"E{max_num + 1:06d}"

    # ------------------------------------------------------------------
    # Core mutation
    # ------------------------------------------------------------------

    def apply_event(self, event: Event) -> Event:
        """Atomically append event to JSONL and mutate SQLite state.

        ID assignment
        -------------
        If event.id == PENDING_EVENT_ID the Backend assigns a fresh sequential
        ID inside the BEGIN IMMEDIATE lock — eliminating the read-before-lock race
        flagged by Critic-3 on PR #41 (two concurrent processes calling
        next_event_id() + apply_event() can both observe MAX=N and both attempt
        INSERT E{N+1}; the second INSERT OR IGNORE silently no-ops, leaving the
        event in JSONL but missing from the events table).

        If event.id is a real ID it is honored as-is — required for the replay
        path where the original ID must be preserved.

        Order of operations for non-PENDING (replay/legacy) events
        -----------------------------------------------------------
        1. Serialise event to JSON.
        2. Append to events.jsonl.
        3. BEGIN IMMEDIATE.
        4. Dispatch to _apply_mutation().
        5. INSERT the event row into events table.
        6. COMMIT.

        Order of operations for PENDING events (live path)
        ---------------------------------------------------
        Trade-off: JSONL write moves AFTER COMMIT because the ID is unknown until
        inside the lock.  This weakens the "log-before-mutation" crash-recovery
        property for PENDING events specifically — if the process dies after COMMIT
        but before the JSONL write, the SQLite row exists but the JSONL line does
        not.  This is strictly better than the alternative (silent event loss from
        the race), and the replay path is not affected (it only uses non-PENDING IDs
        from the existing JSONL log).

        1. BEGIN IMMEDIATE.
        2. Read MAX(id) inside the lock; compute assigned_id = E{max+1:06d}.
        3. Rebuild event with the assigned ID.
        4. Dispatch to _apply_mutation().
        5. INSERT the event row into events table.
        6. COMMIT.
        7. Append the materialized event to events.jsonl.

        Returns
        -------
        The materialized event (with assigned ID if PENDING was passed).  Callers
        must use the returned value — do not rely on the input event having a
        real ID after the call if PENDING_EVENT_ID was passed.

        On any failure: ROLLBACK, append an error.transaction_aborted event to
        JSONL, and re-raise as TransactionAborted.
        """
        conn = self._require_conn()
        needs_id = event.id == PENDING_EVENT_ID

        if needs_id:
            # PENDING path: generate ID inside the lock.
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT MAX(CAST(SUBSTR(id, 2) AS INTEGER)) FROM events"
                ).fetchone()
                max_num: int = row[0] if row and row[0] is not None else 0
                assigned_id = f"E{max_num + 1:06d}"
                # Rebuild event with the assigned ID (model_copy is pydantic v2).
                event = event.model_copy(update={"id": assigned_id})
                self._apply_mutation(conn, event)
                self._insert_event_row(conn, event)
                conn.execute("COMMIT")
            except sqlite3.OperationalError as exc:
                self._safe_rollback(conn)
                if "database is locked" in str(exc).lower():
                    raise StateLocked(
                        f"SQLite busy_timeout exceeded assigning PENDING event "
                        f"(action={event.action!r}): {exc}"
                    ) from exc
                # For PENDING events that failed before COMMIT, no JSONL line
                # was written — append an abort tombstone using whatever partial
                # event state we have so the audit log records the attempt.
                self._append_abort_event(event, str(exc))
                raise TransactionAborted(
                    f"Transaction aborted for PENDING event (action={event.action!r}): {exc}"
                ) from exc
            except Exception as exc:
                self._safe_rollback(conn)
                self._append_abort_event(event, str(exc))
                raise TransactionAborted(
                    f"Transaction aborted for PENDING event (action={event.action!r}): {exc}"
                ) from exc

            # COMMIT succeeded — now write to JSONL (post-COMMIT ordering for PENDING).
            # If this write fails, the mutation lives only in SQLite. This is a
            # permanent audit gap: replay_from_empty deletes the SQLite file
            # before rebuilding from JSONL, so this event will be lost on the
            # next full replay. We accept the gap here because the alternative
            # (raising TransactionAborted) would lie to the caller — SQLite has
            # already committed. The best-effort tombstone below may also fail
            # on disk-full; in that case _append_abort_event surfaces via the
            # process logger so the divergence is at least operator-visible.
            event_line = event.model_dump_json() + "\n"
            try:
                with open(self._events_path, "a", encoding="utf-8") as fh:
                    fh.write(event_line)
            except OSError as exc:
                self._append_abort_event(
                    event,
                    f"JSONL write failed after successful COMMIT (audit gap): {exc}",
                )
        else:
            # Non-PENDING (replay/legacy) path: write JSONL first, then SQLite.
            # This is the original "log-before-mutation" ordering — if SQLite fails,
            # the JSONL line is the recovery record.
            event_line = event.model_dump_json() + "\n"
            try:
                with open(self._events_path, "a", encoding="utf-8") as fh:
                    fh.write(event_line)
            except OSError as exc:
                raise TransactionAborted(
                    f"Failed to write event {event.id!r} to JSONL log: {exc}"
                ) from exc

            try:
                conn.execute("BEGIN IMMEDIATE")
                self._apply_mutation(conn, event)
                self._insert_event_row(conn, event)
                conn.execute("COMMIT")
            except sqlite3.OperationalError as exc:
                self._safe_rollback(conn)
                if "database is locked" in str(exc).lower():
                    raise StateLocked(
                        f"SQLite busy_timeout exceeded for event {event.id!r}: {exc}"
                    ) from exc
                self._append_abort_event(event, str(exc))
                raise TransactionAborted(
                    f"Transaction aborted for event {event.id!r}: {exc}"
                ) from exc
            except Exception as exc:
                self._safe_rollback(conn)
                self._append_abort_event(event, str(exc))
                raise TransactionAborted(
                    f"Transaction aborted for event {event.id!r}: {exc}"
                ) from exc

        return event

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay_from_empty(self, events_path: str) -> None:
        """Reconstruct state.db from events.jsonl.

        Steps
        -----
        1. Close and delete state.db.
        2. Re-open and re-create schema (call initialize()).
        3. Read events_path line-by-line.
        4. Skip events with action == 'error.transaction_aborted'.
        5. Apply each remaining event via apply_event().
        """
        # Close existing connection.
        self.close()

        # Delete the database file (and any WAL/SHM sidecars).
        for suffix in ("", "-wal", "-shm"):
            path = self._db_path + suffix
            if os.path.exists(path):
                os.remove(path)

        # Re-open fresh.
        self.initialize()

        if not os.path.exists(events_path):
            return

        with open(events_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    # Corrupted line — skip silently (log files can have partial
                    # writes on crash; in production we'd raise).
                    continue

                # Skip abort tombstones and informational warning lines.
                # warn.idempotent_no_op entries (written by _append_warn_log
                # whenever a claim release/stale is already-terminal) lack a
                # canonical Event 'id' field — passing them to model_validate
                # would crash mid-replay on any project that triggered a stale
                # reaping cycle. Critic-3 flagged this on PR #41.
                action = raw.get("action", "")
                if action in ("error.transaction_aborted", "warn.idempotent_no_op"):
                    continue

                try:
                    event = Event.model_validate(raw)
                except Exception:
                    # Defensive: any future non-canonical audit line (e.g. a
                    # hook fallback that wrote a malformed entry) shouldn't
                    # abort replay — log skip and move on. The byte-compare
                    # test will fail on the next phase if a real action is
                    # dropped silently, so this is safe forwards-compat.
                    continue
                # During replay we write only to SQLite; the JSONL is the source.
                # We temporarily redirect apply_event to avoid re-appending to JSONL.
                self._apply_event_sqlite_only(event)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_task(self, task_id: str) -> Task | None:
        """Return the Task with the given ID, or None if not found."""
        conn = self._require_conn()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_task(row, conn)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        feature_id: str | None = None,
    ) -> list[Task]:
        """Return tasks, optionally filtered by status and/or feature_id."""
        conn = self._require_conn()
        clauses: list[str] = []
        params: list[str] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if feature_id is not None:
            clauses.append("feature_id = ?")
            params.append(feature_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(f"SELECT * FROM tasks {where}", params).fetchall()
        return [self._row_to_task(row, conn) for row in rows]

    def get_claim(self, claim_id: str) -> Claim | None:
        """Return the Claim with the given ID, or None if not found."""
        conn = self._require_conn()
        row = conn.execute(
            "SELECT * FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_claim(row)

    def list_active_claims(self) -> list[Claim]:
        """Return all claims with status == 'active'."""
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT * FROM claims WHERE status = ?",
            (ClaimStatus.active,),
        ).fetchall()
        return [self._row_to_claim(row) for row in rows]

    def list_claims(self) -> list[Claim]:
        """Return ALL claims regardless of status, sorted by id ASC.

        Includes active, released, stale, and force_released claims.
        The id-based ordering is deterministic because claim IDs follow
        the same C-prefixed format (e.g. 'C001') assigned at claim creation
        and never mutate.
        """
        conn = self._require_conn()
        rows = conn.execute(
            # ORDER BY id ASC: lexical order matches numeric only while the
            # zero-padded claim/event id suffix stays within its digit width.
            "SELECT * FROM claims ORDER BY id ASC"
        ).fetchall()
        return [self._row_to_claim(row) for row in rows]

    def list_reviews(self) -> list[Review]:
        """Return all Review rows sorted by id ASC.

        Covers both prd.approved reviews (id = RV-E{n}) and task.applied
        reviews (id = RV-E{n}).  The id-based ordering is deterministic
        because review IDs are derived deterministically from event IDs
        inside their handlers.
        """
        conn = self._require_conn()
        rows = conn.execute(
            # ORDER BY id ASC: lexical order matches numeric only while the
            # zero-padded event/id suffix stays within its digit width.
            "SELECT id, target_kind, target_id, reviewed_by, decision, notes, created_at "
            "FROM reviews ORDER BY id ASC"
        ).fetchall()
        return [self._row_to_review(row) for row in rows]

    def list_evidence(self) -> list[Evidence]:
        """Return all Evidence rows sorted by id ASC.

        The id-based ordering is deterministic because evidence IDs are
        assigned by callers before emitting evidence.submitted events and
        are stable across replay.
        """
        conn = self._require_conn()
        rows = conn.execute(
            # ORDER BY id ASC: lexical order matches numeric only while the
            # zero-padded event/id suffix stays within its digit width.
            "SELECT id, task_id, claim_id, commands_run, output_excerpt, "
            "files_changed, pr_url, commit_sha, screenshots, "
            "known_limitations, submitted_at, submitted_by "
            "FROM evidence ORDER BY id ASC"
        ).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    def list_requirements(self) -> list[Requirement]:
        """Return all Requirement rows sorted by id ASC.

        The id-based ordering is deterministic because requirement IDs are
        assigned at prd.parsed time and never mutate.  prd.parsed is
        destructive — it deletes and re-inserts all rows — so the result
        always reflects the current parse, in stable id order.
        """
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT id, prd_section, text, source_paragraph, derived "
            "FROM requirements ORDER BY id ASC"
        ).fetchall()
        return [self._row_to_requirement(row) for row in rows]

    def get_prd(self) -> PRD | None:
        """Return the current PRD, or None if not yet created."""
        conn = self._require_conn()
        row = conn.execute("SELECT * FROM prds").fetchone()
        if row is None:
            return None
        return self._row_to_prd(row)

    def get_project(self) -> Project | None:
        """Return the Project record, or None if not initialised."""
        conn = self._require_conn()
        row = conn.execute("SELECT * FROM projects").fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    def get_feature(self, feature_id: str) -> Feature | None:
        """Return the Feature with the given ID, or None if not found."""
        conn = self._require_conn()
        row = conn.execute(
            "SELECT id, title, description, status, requirements, tasks "
            "FROM features WHERE id = ?",
            (feature_id,),
        ).fetchone()
        if row is None:
            return None
        return Feature(
            id=row[0],
            title=row[1],
            description=row[2],
            status=row[3],
            requirements=json.loads(row[4] or "[]"),
            tasks=json.loads(row[5] or "[]"),
        )

    def list_features(self) -> list[Feature]:
        """Return all Feature rows ordered by ID — see Protocol docstring."""
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT id, title, description, status, requirements, tasks "
            "FROM features ORDER BY id"
        ).fetchall()
        return [
            Feature(
                id=r[0],
                title=r[1],
                description=r[2],
                status=r[3],
                requirements=json.loads(r[4] or "[]"),
                tasks=json.loads(r[5] or "[]"),
            )
            for r in rows
        ]

    def list_events(
        self,
        *,
        target_id: str,
        target_kind: str | None = None,
        limit: int = 10,
    ) -> list[tuple[str, str]]:
        """Return recent events for target as (action, timestamp_iso) tuples, most-recent first."""
        conn = self._require_conn()
        if target_kind is not None:
            rows = conn.execute(
                "SELECT action, timestamp FROM events "
                "WHERE target_id = ? AND target_kind = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (target_id, target_kind, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT action, timestamp FROM events "
                "WHERE target_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (target_id, limit),
            ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def get_latest_evidence(self, task_id: str) -> Evidence | None:
        """Return the most recently submitted Evidence for task_id, or None."""
        conn = self._require_conn()
        try:
            row = conn.execute(
                "SELECT id, task_id, claim_id, commands_run, output_excerpt, "
                "files_changed, pr_url, commit_sha, screenshots, "
                "known_limitations, submitted_at, submitted_by "
                "FROM evidence "
                "WHERE task_id = ? "
                "ORDER BY submitted_at DESC "
                "LIMIT 1",
                (task_id,),
            ).fetchone()
        except Exception:  # noqa: BLE001
            return None
        if row is None:
            return None
        return self._row_to_evidence(row)

    # ------------------------------------------------------------------
    # Phase 8 — sync mapping query helpers
    # ------------------------------------------------------------------

    def get_sync_mapping(
        self,
        task_id: str,
        *,
        external_system: str | None = None,
    ) -> SyncMapping | None:
        """Return the SyncMapping for ``task_id``, or None if not mapped.

        If ``external_system`` is None, returns the first mapping by
        ``external_system`` ASC — kept for backward-compat single-provider
        callers. Multi-provider callers MUST pass ``external_system``
        explicitly to get a scoped lookup; otherwise which provider's
        mapping wins is ASC-sort-position-dependent and brittle.
        """
        conn = self._require_conn()
        base = (
            "SELECT task_id, external_system, external_id, external_url, "
            "last_synced_at, sync_state, conflict_resolution_strategy, "
            "provider_metadata_json FROM sync_mappings WHERE task_id = ?"
        )
        if external_system is None:
            row = conn.execute(
                base + " ORDER BY external_system ASC LIMIT 1",
                (task_id,),
            ).fetchone()
        else:
            row = conn.execute(
                base + " AND external_system = ? LIMIT 1",
                (task_id, external_system),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_sync_mapping(row)

    def list_sync_mappings(
        self,
        external_system: str | None = None,
    ) -> list[SyncMapping]:
        """Return SyncMapping rows, optionally filtered by external_system.

        Sorted by (task_id, external_system) ASC for deterministic output —
        important for replay-equality tests and for any CLI rendering that
        relies on stable ordering across runs.
        """
        conn = self._require_conn()
        base = (
            "SELECT task_id, external_system, external_id, external_url, "
            "last_synced_at, sync_state, conflict_resolution_strategy, "
            "provider_metadata_json FROM sync_mappings"
        )
        if external_system is None:
            rows = conn.execute(
                base + " ORDER BY task_id ASC, external_system ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                base + " WHERE external_system = ? "
                "ORDER BY task_id ASC, external_system ASC",
                (external_system,),
            ).fetchall()
        return [self._row_to_sync_mapping(r) for r in rows]

    def apply_sync_mapping(
        self,
        mapping: SyncMapping,
        *,
        actor: str = "system",
    ) -> Event:
        """Build a sync_mapping.upserted event and dispatch it via apply_event().

        Convenience for callers that want to write a mapping without having to
        construct the Event/payload boilerplate. Uses PENDING_EVENT_ID so the
        Backend assigns a fresh sequential ID inside the BEGIN IMMEDIATE lock
        (race-free); the returned Event carries the assigned ID.

        Serializes the mapping through the canonical
        :class:`SyncMappingUpsertedPayload` model EXPLICITLY — not via
        ``mapping.model_dump()`` — so a hypothetical extra field on
        ``SyncMapping`` that hasn't been added to the payload model fails
        fast at THIS call site with a ``ValidationError`` rather than
        surfacing as ``TransactionAborted`` inside the BEGIN IMMEDIATE
        lock. (Wave 1 critic fix MF-2.)
        """
        payload = SyncMappingUpsertedPayload(
            task_id=mapping.task_id,
            external_system=str(mapping.external_system),
            external_id=mapping.external_id,
            external_url=mapping.external_url,
            last_synced_at=mapping.last_synced_at.isoformat(),
            sync_state=str(mapping.sync_state),
            conflict_resolution_strategy=str(mapping.conflict_resolution_strategy),
            provider_metadata=dict(mapping.provider_metadata),
        )
        event = Event(
            id=PENDING_EVENT_ID,
            timestamp=self._clock.now(),
            actor=actor,
            action="sync_mapping.upserted",
            target_kind="task",
            target_id=mapping.task_id,
            payload_json=payload.model_dump(mode="json"),
        )
        return self.apply_event(event)

    # ------------------------------------------------------------------
    # Internal helpers — DDL & version
    # ------------------------------------------------------------------

    def _apply_ddl(self) -> None:
        """Execute the DDL script statement-by-statement."""
        conn = self._require_conn()
        # Split on semicolons; filter blanks and PRAGMA user_version (set last).
        statements = [s.strip() for s in DDL.split(";") if s.strip()]
        # Separate the user_version pragma — it must be set outside a transaction
        # on some SQLite versions, so we handle it explicitly at the end.
        version_pragma = f"PRAGMA user_version = {SCHEMA_VERSION}"
        non_version = [s for s in statements if "user_version" not in s.lower()]
        conn.execute("BEGIN")
        for stmt in non_version:
            if stmt:
                conn.execute(stmt)
        conn.execute("COMMIT")
        conn.execute(version_pragma)

    def _check_schema_version(self, *, pre_ddl_version: int | None = None) -> None:
        """Raise SchemaMismatch if on-disk version is incompatible with SCHEMA_VERSION.

        Auto-upgrade behaviour (Phase 8 SF-6, refined by P1-3):

        - ``v0 / v1 → v3``: purely additive. The IF NOT EXISTS DDL created
          the v3-shaped ``sync_mappings`` table from scratch (those versions
          had no such table). Just bump ``user_version``.
        - ``v2 → v3``: NOT purely additive. The v2 db has a real
          ``sync_mappings`` table that ``CREATE TABLE IF NOT EXISTS``
          cannot retroactively modify — we must explicitly ALTER it to
          add ``external_url``, ``provider_metadata_json``, and the v3
          UNIQUE(external_system, external_id) index. Pre-fix this branch
          was a no-op stamp; queries against the new columns raised
          ``OperationalError`` until the v3 ALTERs landed.

        ``pre_ddl_version`` carries the user_version that was on disk
        BEFORE ``_apply_ddl`` re-stamped it. Required for the v2→v3 path:
        without it we'd always observe the post-DDL stamp (always equal
        to SCHEMA_VERSION) and the migration branch would never fire.

        Older gaps (e.g. a v3 db opened by code that expects v4) still
        raise. See docs/migrations.md.
        """
        conn = self._require_conn()
        # Use the pre-DDL version when provided (initialize path); fall back
        # to whatever PRAGMA reports now (early-return path where DDL did
        # not run between captures).
        if pre_ddl_version is not None:
            on_disk = pre_ddl_version
        else:
            row = conn.execute("PRAGMA user_version").fetchone()
            on_disk = row[0] if row else 0
        if on_disk == SCHEMA_VERSION:
            return
        if on_disk in (0, 1) and SCHEMA_VERSION == 3:
            # v0/v1 → v3: no sync_mappings existed pre-v2, so the DDL above
            # created the v3-shaped table directly. Just bump.
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            return
        if on_disk == 2 and SCHEMA_VERSION == 3:
            # v2 → v3: add the three v3 sync_mappings additions that the
            # IF NOT EXISTS DDL cannot retroactively apply to the v2 table.
            # Each ALTER is wrapped because re-running the migration (e.g.
            # crash-recovery) must remain idempotent — a "duplicate column"
            # error means the ALTER already happened on a previous run.
            try:
                conn.execute(
                    "ALTER TABLE sync_mappings ADD COLUMN external_url TEXT"
                )
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
            try:
                conn.execute(
                    "ALTER TABLE sync_mappings ADD COLUMN "
                    "provider_metadata_json TEXT"
                )
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
            # SQLite does not support adding a table-level UNIQUE constraint
            # via ALTER TABLE, but a UNIQUE INDEX has the same enforcement
            # semantics for query planning AND constraint violation. The
            # IF NOT EXISTS makes the migration replay-safe.
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "idx_sync_mappings_external_unique "
                "ON sync_mappings (external_system, external_id)"
            )
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            return
        raise SchemaMismatch(
            f"Database schema version {on_disk} does not match "
            f"expected version {SCHEMA_VERSION}. "
            "Run a migration or delete state.db to start fresh."
        )

    def _require_conn(self) -> sqlite3.Connection:
        """Return the open connection or raise if not initialised."""
        if self._conn is None:
            raise RuntimeError(
                "SqliteBackend.initialize() must be called before any query or mutation."
            )
        return self._conn

    # ------------------------------------------------------------------
    # Internal helpers — event routing
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Dispatch table — maps action name to (PayloadModel, bound handler).
    # Built lazily on first access to allow self-referential bound methods.
    # ------------------------------------------------------------------

    def _get_action_dispatch(self) -> dict[str, ActionSpec]:
        """Return the dispatch table mapping action → ``ActionSpec``.

        SL1-RR-1 architecture move #1: each action resolves to an
        ``ActionSpec(payload_model, check, write)`` rather than a single
        interleaved handler. The check/write phases share the normalised
        signature ``(conn, payload: TypedPayload, event: Event) -> None``; the
        payload is validated against ``payload_model`` before either phase runs.

        The table is built once per instance and cached. Bound-method values
        capture ``self``, so the cache is invalidated naturally if the instance
        is replaced.
        """
        cached: dict[str, ActionSpec] | None = getattr(
            self, "_action_dispatch_cache", None
        )
        if cached is not None:
            return cached
        table: dict[str, ActionSpec] = {
            "project.created": ActionSpec(
                ProjectCreatedPayload,
                self._check_project_created,
                self._write_project_created,
            ),
            "state.initialized": ActionSpec(
                StateInitializedPayload,
                self._check_audit_only,
                self._write_audit_only,
            ),
            "prd.parsed": ActionSpec(
                PrdParsedPayload, self._check_prd_parsed, self._write_prd_parsed
            ),
            "prd.reviewed": ActionSpec(
                PrdReviewedPayload, self._check_prd_reviewed, self._write_prd_reviewed
            ),
            "prd.approved": ActionSpec(
                PrdApprovedPayload, self._check_prd_approved, self._write_prd_approved
            ),
            "feature.created": ActionSpec(
                FeatureCreatedPayload,
                self._check_feature_created,
                self._write_feature_created,
            ),
            "task.created": ActionSpec(
                TaskCreatedPayload, self._check_task_created, self._write_task_created
            ),
            "task.scored": ActionSpec(
                TaskScoredPayload, self._check_task_scored, self._write_task_scored
            ),
            "task.expanded": ActionSpec(
                TaskExpandedPayload,
                self._check_task_expanded,
                self._write_task_expanded,
            ),
            "task.status_changed": ActionSpec(
                TaskStatusChangedPayload,
                self._check_task_status_changed,
                self._write_task_status_changed,
            ),
            # v1.15.0 — orphan cleanup on re-parse.
            "task.deleted": ActionSpec(
                TaskDeletedPayload, self._check_task_deleted, self._write_task_deleted
            ),
            "feature.deleted": ActionSpec(
                FeatureDeletedPayload,
                self._check_feature_deleted,
                self._write_feature_deleted,
            ),
            # Phase 8: pull-applies-remote — local Task gets title/desc/status
            # rewritten from the remote payload after a non-conflict pull.
            "task.synced_from_remote": ActionSpec(
                TaskSyncedFromRemotePayload,
                self._check_task_synced_from_remote,
                self._write_task_synced_from_remote,
            ),
            "claim.created": ActionSpec(
                ClaimCreatedPayload,
                self._check_claim_created,
                self._write_claim_created,
            ),
            "claim.released": ActionSpec(
                ClaimReleasedPayload,
                self._check_claim_released,
                self._write_claim_released,
            ),
            "claim.renewed": ActionSpec(
                ClaimRenewedPayload,
                self._check_claim_renewed,
                self._write_claim_renewed,
            ),
            "claim.stale": ActionSpec(
                ClaimStalePayload, self._check_claim_stale, self._write_claim_stale
            ),
            "evidence.submitted": ActionSpec(
                EvidenceSubmittedPayload,
                self._check_evidence_submitted,
                self._write_evidence_submitted,
            ),
            "task.applied": ActionSpec(
                TaskAppliedPayload, self._check_task_applied, self._write_task_applied
            ),
            "file_changed": ActionSpec(
                FileChangedPayload, self._check_audit_only, self._write_audit_only
            ),
            # Phase 6: MCP submit_progress — audit-only, no SQLite mutation.
            "progress.noted": ActionSpec(
                ProgressNotedPayload, self._check_audit_only, self._write_audit_only
            ),
            # Phase 8: sync_mappings table — external-system mirroring.
            "sync_mapping.upserted": ActionSpec(
                SyncMappingUpsertedPayload,
                self._check_sync_mapping_upserted,
                self._write_sync_mapping_upserted,
            ),
            "sync_mapping.deleted": ActionSpec(
                SyncMappingDeletedPayload,
                self._check_sync_mapping_deleted,
                self._write_sync_mapping_deleted,
            ),
            # Phase 8 Wave 3: sync.* audit events (CLI sync surface). Every
            # one is an audit-only no-op; the JSONL row is the entire audit
            # record. State mutation flows through the `sync_mapping.upserted`
            # event above, kept separate so replay can rebuild the mappings
            # table without `sync.*` semantics.
            #
            # Phase 9 T3/T5: ``SyncAuditPayload`` is now a discriminated
            # union (TypeAlias), NOT a BaseModel subclass — calling
            # ``SyncAuditPayload.model_validate(...)`` from the dispatcher
            # raises ``AttributeError`` because ``types.UnionType`` has no
            # such classmethod. We dispatch each ``sync.*`` action against its
            # concrete subclass via ``ACTION_TO_PAYLOAD`` from ``payloads.py``
            # so every entry resolves to a real ``BaseModel`` class with a
            # working ``.model_validate``. This also tightens validation: each
            # subclass declares only the fields its action actually carries
            # (``extra='forbid'``), so malformed payloads fail fast at dispatch.
            **{
                action: ActionSpec(
                    model_cls, self._check_audit_only, self._write_audit_only
                )
                for action, model_cls in ACTION_TO_PAYLOAD.items()
            },
        }
        self._action_dispatch_cache = table
        return table

    def _apply_mutation(self, conn: sqlite3.Connection, event: Event) -> None:
        """Validate via ``_check_*`` then mutate via ``_write_*``.

        SL1-RR-1 architecture move #1: a dispatched action is now applied in
        two phases. The payload is validated against its model, then the
        action's ``check`` runs (read-only validation that may raise
        ``EventRejected`` / ``IdempotentNoOp``), then its ``write`` performs the
        mutation.

        This wave is behavior-preserving — the split is internal to
        ``_apply_mutation``; the outcomes observed by ``apply_event`` /
        ``replay_from_empty`` are exactly today's:

        - ``EventRejected`` (raised by a check that used to ``raise
          TransactionAborted`` as a validation guard) is left to propagate.
          ``apply_event``'s existing ``except Exception`` block treats it like
          the validation failures it handled before: rollback, append an
          ``error.transaction_aborted`` tombstone, re-raise ``TransactionAborted``.
        - ``IdempotentNoOp`` (raised by a check where the handler used to
          warn-and-return or return silently) is caught here and mapped back to
          the prior behavior: emit the ``warn.idempotent_no_op`` line when the
          original handler did, then return normally so the caller still records
          the event row + JSONL line exactly as before.
        - Genuine infra failures (``sqlite3.OperationalError`` from a ``write``)
          keep flowing to the caller untouched.

        Task 4 rewires error handling (log-first ``append`` + ``audit.jsonl``);
        until then this mapping keeps the suite green.
        """
        action = event.action
        dispatch = self._get_action_dispatch()

        if action not in dispatch:
            raise NotImplementedError(
                f"Event action {action!r} is not yet supported. "
                "This action will be implemented in a later phase."
            )

        spec = dispatch[action]
        typed_payload = spec.payload_model.model_validate(event.payload_json)

        try:
            spec.check(conn, typed_payload, event)
        except IdempotentNoOp as no_op:
            # Already-satisfied request. Reproduce the prior behavior: some
            # handlers emitted a warn.idempotent_no_op JSONL line, others
            # returned silently. Either way the event row + JSONL line are still
            # recorded by the caller (apply_event continues to _insert_event_row
            # + COMMIT), so we return normally without running the write.
            warn_action = getattr(no_op, "warn_action", None)
            if warn_action is not None:
                self._append_warn_log(
                    action=warn_action,
                    target_id=getattr(no_op, "warn_target_id", "") or "",
                    reason=str(no_op),
                )
            return

        spec.write(conn, typed_payload, event)

    # ------------------------------------------------------------------
    # Audit-only phases — shared by state.initialized, file_changed,
    # progress.noted, and every sync.* action. The JSONL row is the entire
    # audit record; there is no SQLite mutation. The check always proceeds and
    # the write is a no-op.
    # ------------------------------------------------------------------

    def _check_audit_only(
        self,
        conn: sqlite3.Connection,
        payload: BaseModel,
        event: Event,
    ) -> None:
        """No-op check for audit-only actions — always proceeds.

        Payload validation (the model + ``extra='forbid'``) already ran in
        ``_apply_mutation``; an audit-only action has no state precondition that
        could reject it, so this phase never raises.
        """
        _ = (conn, payload, event)

    def _write_audit_only(
        self,
        conn: sqlite3.Connection,
        payload: BaseModel,
        event: Event,
    ) -> None:
        """No-op write for audit-only actions — the event row is the record.

        Covers ``state.initialized``, ``file_changed``, ``progress.noted`` and
        every ``sync.*`` action. The events-table INSERT + JSONL line (written
        by the caller) are the entire audit trail; no domain table is touched.
        """
        _ = (conn, payload, event)

    def _check_project_created(
        self,
        conn: sqlite3.Connection,
        payload: ProjectCreatedPayload,
        event: Event,
    ) -> None:
        """No validation gate — project.created is an idempotent upsert."""
        _ = (conn, payload, event)

    def _write_project_created(
        self,
        conn: sqlite3.Connection,
        payload: ProjectCreatedPayload,
        event: Event,
    ) -> None:
        """Insert or replace the project row from the event payload."""
        _ = event
        project = Project.model_validate(payload.model_dump(mode="json"))
        data = project.model_dump(mode="json")
        conn.execute(
            """
            INSERT OR REPLACE INTO projects
                (id, name, description, created_at, updated_at)
            VALUES
                (:id, :name, :description, :created_at, :updated_at)
            """,
            data,
        )

    # ------------------------------------------------------------------
    # Phase 3 handlers
    # ------------------------------------------------------------------

    def _check_prd_parsed(
        self,
        conn: sqlite3.Connection,
        payload: PrdParsedPayload,
        event: Event,
    ) -> None:
        """Validate every Requirement payload before any write.

        Was a validation guard inside the old handler (``raise
        TransactionAborted`` on an invalid Requirement); now rejects up front.
        """
        _ = (conn, event)
        for req_data in payload.requirements:
            try:
                Requirement.model_validate(req_data)
            except Exception as exc:
                raise EventRejected(
                    f"prd.parsed: invalid Requirement in payload: {exc}"
                ) from exc

    def _write_prd_parsed(
        self,
        conn: sqlite3.Connection,
        payload: PrdParsedPayload,
        event: Event,
    ) -> None:
        """Upsert PRD and destructively replace all requirements.

        Payload fields (all required):
            project_id (str)  — FK into projects table
            status (str)      — PRDStatus value (default 'draft' if absent)
            summary (str)
            goals (list[str])
            non_goals (list[str])
            requirements (list[dict]) — each is a Requirement payload
            acceptance_criteria (list[str])
            risks (list[str])
            open_questions (list[str])

        The ``requirements`` list in the PRD payload contains full Requirement
        dicts.  The top-level ``prds.requirements`` column stores only the list
        of requirement IDs (FK-style); the actual Requirement rows live in the
        ``requirements`` table.

        Parsing is destructive: old Requirement rows are deleted and replaced
        with the new set inside a SAVEPOINT so failure leaves no partial state.

        Each Requirement was already validated by ``_check_prd_parsed``; the
        ``model_validate`` calls here are an infallible rebuild.
        """
        _ = event
        project_id: str = payload.project_id
        summary: str = payload.summary
        status: str = payload.status
        goals = payload.goals
        non_goals = payload.non_goals
        requirements_raw: list[Any] = payload.requirements
        acceptance_criteria = payload.acceptance_criteria
        risks = payload.risks
        open_questions = payload.open_questions

        requirement_objects: list[Requirement] = [
            Requirement.model_validate(req_data) for req_data in requirements_raw
        ]
        requirement_ids = [r.id for r in requirement_objects]

        # Upsert the PRD row.
        conn.execute(
            """
            INSERT OR REPLACE INTO prds
                (project_id, status, summary, goals, non_goals, requirements,
                 acceptance_criteria, risks, open_questions,
                 last_reviewed_at, last_reviewed_by)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                project_id,
                status,
                summary,
                json.dumps(goals),
                json.dumps(non_goals),
                json.dumps(requirement_ids),
                json.dumps(acceptance_criteria),
                json.dumps(risks),
                json.dumps(open_questions),
            ),
        )

        # Destructive re-parse of requirements — use SAVEPOINT so failure is
        # atomic within the outer transaction.
        conn.execute("SAVEPOINT prd_requirements_replace")
        try:
            conn.execute("DELETE FROM requirements")
            for req in requirement_objects:
                conn.execute(
                    """
                    INSERT INTO requirements
                        (id, prd_section, text, source_paragraph, derived)
                    VALUES
                        (?, ?, ?, ?, ?)
                    """,
                    (
                        req.id,
                        req.prd_section,
                        req.text,
                        req.source_paragraph,
                        1 if req.derived else 0,
                    ),
                )
        except Exception:
            conn.execute("ROLLBACK TO prd_requirements_replace")
            conn.execute("RELEASE prd_requirements_replace")
            raise
        conn.execute("RELEASE prd_requirements_replace")

    def _check_prd_reviewed(
        self,
        conn: sqlite3.Connection,
        payload: PrdReviewedPayload,
        event: Event,
    ) -> None:
        """No state precondition — the UPDATE is scoped and side-effect-only."""
        _ = (conn, payload, event)

    def _write_prd_reviewed(
        self,
        conn: sqlite3.Connection,
        payload: PrdReviewedPayload,
        event: Event,
    ) -> None:
        """Mark PRD as reviewed.

        Payload fields:
            project_id (str) — required (scopes the UPDATE so multi-PRD
                              setups in future phases don't co-mutate)
            reviewer (str)   — required
            notes (str | None) — optional

        We deliberately do NOT insert into the reviews table here. The
        prds.status column transitioning draft → reviewed is its own audit
        record. The reviews table is reserved for outcome-bearing review
        decisions (approve, reject, needs_changes). Recording prd.reviewed
        as decision='approve' would make it indistinguishable from a real
        approval and cause false positives for any downstream code (e.g.,
        the Phase 4 claims manager) that queries
        `reviews WHERE decision='approve'` to determine approval state.
        """
        project_id: str = payload.project_id
        reviewer: str = payload.reviewer
        timestamp: str = event.timestamp.isoformat()

        conn.execute(
            """
            UPDATE prds
               SET status = 'reviewed',
                   last_reviewed_at = ?,
                   last_reviewed_by = ?
             WHERE project_id = ?
            """,
            (timestamp, reviewer, project_id),
        )

    def _check_prd_approved(
        self,
        conn: sqlite3.Connection,
        payload: PrdApprovedPayload,
        event: Event,
    ) -> None:
        """No state precondition — scoped UPDATE plus an idempotent Review upsert."""
        _ = (conn, payload, event)

    def _write_prd_approved(
        self,
        conn: sqlite3.Connection,
        payload: PrdApprovedPayload,
        event: Event,
    ) -> None:
        """Mark PRD as approved and insert an approval Review row.

        Payload fields:
            project_id (str) — required (scopes the UPDATE)
            approver (str)   — required

        The Review row ID is derived deterministically from the event_id so
        that replay produces byte-for-byte identical rows. This is the
        canonical 'approved' marker — queries should use the PRD's status
        column OR look for reviews WHERE target_id=<project_id> AND
        decision='approve' AND target_kind='prd'.
        """
        project_id: str = payload.project_id
        approver: str = payload.approver
        event_id: str = event.id
        timestamp: str = event.timestamp.isoformat()

        conn.execute(
            """
            UPDATE prds
               SET status = 'approved',
                   last_reviewed_at = ?,
                   last_reviewed_by = ?
             WHERE project_id = ?
            """,
            (timestamp, approver, project_id),
        )

        review_id = f"RV-{event_id}"
        conn.execute(
            """
            INSERT OR REPLACE INTO reviews
                (id, target_kind, target_id, reviewed_by, decision, notes, created_at)
            VALUES
                (?, 'prd', ?, ?, 'approve', NULL, ?)
            """,
            (review_id, project_id, approver, timestamp),
        )

    def _check_feature_created(
        self,
        conn: sqlite3.Connection,
        payload: FeatureCreatedPayload,
        event: Event,
    ) -> None:
        """Validate the Feature payload before any write.

        Was a validation guard inside the old handler (``raise
        TransactionAborted`` on an invalid Feature); now rejects up front.
        """
        _ = (conn, event)
        try:
            Feature.model_validate(payload.model_dump(mode="json"))
        except Exception as exc:
            raise EventRejected(
                f"feature.created: invalid Feature payload: {exc}"
            ) from exc

    def _write_feature_created(
        self,
        conn: sqlite3.Connection,
        payload: FeatureCreatedPayload,
        event: Event,
    ) -> None:
        """Insert a Feature row from the event payload.

        Payload fields: all Feature model fields (id, title, description,
        status, requirements, tasks).

        The payload was already validated by ``_check_feature_created``; the
        ``model_validate`` here is an infallible rebuild.
        """
        _ = event
        feature = Feature.model_validate(payload.model_dump(mode="json"))
        data = feature.model_dump(mode="json")
        # Use INSERT ... ON CONFLICT DO UPDATE (UPSERT) instead of INSERT OR
        # REPLACE to avoid violating the ON DELETE RESTRICT FK from tasks.
        # INSERT OR REPLACE is equivalent to DELETE + INSERT which trips the FK
        # when tasks already reference this feature.
        conn.execute(
            """
            INSERT INTO features
                (id, title, description, status, requirements, tasks)
            VALUES
                (:id, :title, :description, :status, :requirements, :tasks)
            ON CONFLICT(id) DO UPDATE SET
                title        = excluded.title,
                description  = excluded.description,
                status       = excluded.status,
                requirements = excluded.requirements,
                tasks        = excluded.tasks
            """,
            {
                "id": data["id"],
                "title": data["title"],
                "description": data["description"],
                "status": data["status"],
                "requirements": json.dumps(data["requirements"]),
                "tasks": json.dumps(data["tasks"]),
            },
        )

    @staticmethod
    def _normalize_task_payload(task_dict: dict[str, Any]) -> dict[str, Any]:
        """Coerce a minimal Task payload's None scores/verification to ``{}``.

        Task.scores / Task.verification are required submodels; the payload
        allows None so MCP / hand-rolled callers can send a minimal task without
        preloading sentinels. Pure dict munging — shared by the check and write
        phases so both validate / build the identical normalized shape.
        """
        task_dict = dict(task_dict)
        if task_dict.get("scores") is None:
            task_dict["scores"] = {}
        if task_dict.get("verification") is None:
            task_dict["verification"] = {}
        return task_dict

    def _check_task_created(
        self,
        conn: sqlite3.Connection,
        payload: TaskCreatedPayload,
        event: Event,
    ) -> None:
        """Validate the (normalized) Task payload before any write.

        Was a validation guard inside the old handler (``raise
        TransactionAborted`` on an invalid Task); now rejects up front.
        """
        _ = (conn, event)
        task_dict = self._normalize_task_payload(payload.model_dump(mode="json"))
        try:
            Task.model_validate(task_dict)
        except Exception as exc:
            raise EventRejected(
                f"task.created: invalid Task payload: {exc}"
            ) from exc

    def _write_task_created(
        self,
        conn: sqlite3.Connection,
        payload: TaskCreatedPayload,
        event: Event,
    ) -> None:
        """Insert a Task row from the event payload.

        Payload fields: all Task model fields.  Scores may be None for all
        dimensions at creation time; they get populated by task.scored later.

        The payload was already validated by ``_check_task_created``; the
        ``model_validate`` here is an infallible rebuild.
        """
        _ = event
        task_dict = self._normalize_task_payload(payload.model_dump(mode="json"))
        task = Task.model_validate(task_dict)
        self._insert_task_row(conn, task)

    @staticmethod
    def _build_task_score(payload: TaskScoredPayload) -> Score:
        """Build the Score model from a task.scored payload (pure)."""
        score_data = dict(payload.scores)
        score_data["explanation"] = payload.explanation
        return Score.model_validate(score_data)

    def _check_task_scored(
        self,
        conn: sqlite3.Connection,
        payload: TaskScoredPayload,
        event: Event,
    ) -> None:
        """Validate the scores payload and confirm the task exists.

        Was two validation guards in the old handler (invalid scores payload;
        ``task not found`` after a 0-row UPDATE); both now reject up front.
        """
        _ = event
        try:
            self._build_task_score(payload)
        except Exception as exc:
            raise EventRejected(
                f"task.scored: invalid scores payload: {exc}"
            ) from exc
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (payload.task_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(f"task.scored: task '{payload.task_id}' not found.")

    def _write_task_scored(
        self,
        conn: sqlite3.Connection,
        payload: TaskScoredPayload,
        event: Event,
    ) -> None:
        """Update a task's scores and explanation.

        Payload fields:
            task_id (str) — required
            scores (dict[str, int | None]) — dimension name → score; required
            explanation (str) — required

        The scores dict is merged with any existing Score fields; null-valued
        dimensions remain null (not coerced to 0).  The explanation is stored
        inside the Score model's ``explanation`` field.

        ``_check_task_scored`` already proved the scores validate and the task
        exists, so this UPDATE always hits a row.
        """
        task_id: str = payload.task_id
        timestamp: str = event.timestamp.isoformat()
        score = self._build_task_score(payload)
        scores_json = json.dumps(score.model_dump(mode="json"))

        conn.execute(
            """
            UPDATE tasks
               SET scores = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (scores_json, timestamp, task_id),
        )

    def _normalize_subtask(
        self, subtask_data: Any, parent_task_id: str
    ) -> dict[str, Any]:
        """Force the parent id and coerce minimal scores/verification (pure)."""
        normalized: dict[str, Any] = self._normalize_task_payload(dict(subtask_data))
        normalized["parent_task_id"] = parent_task_id
        return normalized

    def _check_task_expanded(
        self,
        conn: sqlite3.Connection,
        payload: TaskExpandedPayload,
        event: Event,
    ) -> None:
        """Reject an empty expansion and validate every subtask payload.

        Was two validation guards in the old handler (empty ``subtasks`` list;
        invalid subtask payload); both now reject up front.
        """
        _ = (conn, event)
        if not payload.subtasks:
            raise EventRejected(
                "task.expanded payload has empty 'subtasks' list; nothing to expand."
            )
        for subtask_data in payload.subtasks:
            normalized = self._normalize_subtask(subtask_data, payload.parent_task_id)
            try:
                Task.model_validate(normalized)
            except Exception as exc:
                raise EventRejected(
                    f"task.expanded: invalid subtask payload: {exc}"
                ) from exc

    def _write_task_expanded(
        self,
        conn: sqlite3.Connection,
        payload: TaskExpandedPayload,
        event: Event,
    ) -> None:
        """Insert subtask rows derived from expanding a parent task.

        Payload fields:
            parent_task_id (str) — required; must exist in tasks table
            subtasks (list[dict]) — list of Task payloads; each will be
                                    inserted with parent_task_id set

        The parent task's status is NOT changed here; the subtask rows
        themselves signal expansion (parent_task_id IS NOT NULL).

        ``_check_task_expanded`` already proved the list is non-empty and every
        subtask validates, so each ``model_validate`` here is an infallible
        rebuild.
        """
        _ = event
        parent_task_id: str = payload.parent_task_id
        for subtask_data in payload.subtasks:
            normalized = self._normalize_subtask(subtask_data, parent_task_id)
            subtask = Task.model_validate(normalized)
            self._insert_task_row(conn, subtask)

    def _check_task_status_changed(
        self,
        conn: sqlite3.Connection,
        payload: TaskStatusChangedPayload,
        event: Event,
    ) -> None:
        """Decide the transition outcome before any write.

        The old handler ran the guarded UPDATE then interpreted a 0-row result:
        task-not-found / concurrency-drift were ``TransactionAborted``;
        already-at-target was a silent ``return``. This check reproduces those
        decisions on read-only state — reject (not found / drift) or signal a
        silent ``IdempotentNoOp`` (already at target).
        """
        _ = event
        task_id: str = payload.task_id
        from_status: str = payload.from_status
        to_status: str = payload.to_status

        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(f"task.status_changed: task '{task_id}' not found.")
        actual_status = row[0]
        if actual_status == from_status:
            return  # proceed — the guarded UPDATE will match.
        # Idempotent re-application: already at the target status. This lets
        # `plan` (which emits proposed→drafted) be re-run safely after the
        # first run promoted tasks. The old handler returned silently here — no
        # warn log — so this IdempotentNoOp carries no warn metadata.
        if actual_status == to_status:
            raise _idempotent_no_op(
                f"task.status_changed: task '{task_id}' already at '{to_status}'."
            )
        raise EventRejected(
            f"task.status_changed: concurrency guard failed for task '{task_id}'. "
            f"Expected status '{from_status}', got '{actual_status}'. "
            "The task status may have been changed by a concurrent operation."
        )

    def _write_task_status_changed(
        self,
        conn: sqlite3.Connection,
        payload: TaskStatusChangedPayload,
        event: Event,
    ) -> None:
        """Atomically transition a task from one status to another.

        Payload fields:
            task_id (str) — required
            from (str)    — expected current status (concurrency guard)
            to (str)      — target status
            reason (str | None) — optional human-readable reason

        ``_check_task_status_changed`` already proved the task exists and is at
        ``from_status``; the WHERE-status guard remains as a defensive belt but
        always matches here.
        """
        timestamp: str = event.timestamp.isoformat()
        conn.execute(
            """
            UPDATE tasks
               SET status = ?,
                   updated_at = ?
             WHERE id = ?
               AND status = ?
            """,
            (payload.to_status, timestamp, payload.task_id, payload.from_status),
        )

    # ------------------------------------------------------------------
    # v1.15.0 handlers — orphan cleanup on PRD re-parse
    # ------------------------------------------------------------------

    # Task statuses that may be deleted without an explicit `force=True`.
    # Anything outside this set carries claim/evidence history and would
    # silently lose audit data on delete. The handler refuses those unless
    # the caller (via `fakoli-state plan --prune-force`) explicitly accepts
    # the risk.
    _DELETABLE_TASK_STATUSES: frozenset[str] = frozenset({
        "proposed", "drafted", "ready",
    })

    def _check_task_deleted(
        self,
        conn: sqlite3.Connection,
        payload: TaskDeletedPayload,
        event: Event,
    ) -> None:
        """Refuse deletion of a missing / unsafe / FK-protected task.

        Was three validation guards in the old handler:
        1. Status check — refuses unless safe-deletable or ``force=True``.
        2. Existence check — task must exist.
        3. Audit-FK check — ``claims`` and ``evidence`` are RESTRICT-FK'd on
           ``task_id``; a referenced task cannot be deleted (``force`` does NOT
           bypass this — those tables hold the protected audit history).

        All three now reject up front, before the cleanup write runs.
        """
        _ = event
        task_id = payload.task_id

        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(
                f"task.deleted: task '{task_id}' not found in state.db"
            )
        current_status: str = row[0]

        if not payload.force and current_status not in self._DELETABLE_TASK_STATUSES:
            raise EventRejected(
                f"task.deleted: refusing to delete task '{task_id}' in status "
                f"'{current_status}' without force=True. "
                f"Safe-delete statuses: {sorted(self._DELETABLE_TASK_STATUSES)}. "
                "Release any active claim, complete the work, or pass "
                "force=True (via `fakoli-state plan --prune-force`) to "
                "delete despite the status."
            )

        claim_count = conn.execute(
            "SELECT COUNT(*) FROM claims WHERE task_id = ?", (task_id,)
        ).fetchone()[0]
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE task_id = ?", (task_id,)
        ).fetchone()[0]
        if claim_count or evidence_count:
            raise EventRejected(
                f"task.deleted: cannot delete task '{task_id}' — it has "
                f"{claim_count} claim row(s) and {evidence_count} evidence "
                "row(s) that are FK-protected by schema. The audit history "
                "intentionally outlives the task. Re-add the task to "
                "prd.md if you want to preserve a working entry, or "
                "accept that the orphan is conceptually dropped but its "
                "row stays (the data is reachable via events.jsonl)."
            )

    def _write_task_deleted(
        self,
        conn: sqlite3.Connection,
        payload: TaskDeletedPayload,
        event: Event,  # noqa: ARG002 — event metadata recorded via JSONL only
    ) -> None:
        """Delete a Task row after ``_check_task_deleted`` cleared it.

        Cleanup walk (the precondition guards live in ``_check_task_deleted``):
        3. ``conflict_groups.task_ids`` — JSON array; rewrite to drop the
           deleted task ID. Cosmetic since the row is going anyway, but
           keeps the groups table self-consistent.
        4. ``tasks`` — the row itself. ``parent_task_id ON DELETE SET
           NULL`` automatically detaches any child subtasks (they
           become orphaned rather than cascade-deleted, by design).

        Audit history preserved: ``events`` rows targeting this task ID
        stay in events.jsonl forever. ``events.target_id = 'T014'`` will
        still resolve to the now-gone task on replay — that is the
        intended audit-trail behaviour and the reason this handler does
        not touch the events table.
        """
        task_id = payload.task_id

        # 3. Rewrite conflict_groups.task_ids JSON arrays to remove this task.
        # Explicit Row indexing (row["id"]) is safer than positional unpack —
        # the connection's row_factory = sqlite3.Row makes this self-documenting
        # and survives column-order changes. Critic SHOULD FIX from PR #63.
        groups = conn.execute(
            "SELECT id, task_ids FROM conflict_groups"
        ).fetchall()
        for row in groups:
            group_id = row["id"]
            task_ids_json = row["task_ids"]
            try:
                task_ids = json.loads(task_ids_json) if task_ids_json else []
            except (TypeError, ValueError):
                # Malformed JSON in a conflict_group row would otherwise be
                # silently left alone — meaning a subsequent query reading
                # that group could still see the deleted task ID. Log the
                # corruption to stderr so the operator sees it AND rewrite
                # the row to an empty array so downstream queries are
                # consistent with what was actually deleted.
                print(
                    f"warning: conflict_groups row {group_id!r} has malformed "
                    f"task_ids JSON ({task_ids_json!r}); resetting to "
                    "empty array as part of task.deleted cleanup.",
                    file=sys.stderr,
                )
                conn.execute(
                    "UPDATE conflict_groups SET task_ids = ? WHERE id = ?",
                    ("[]", group_id),
                )
                continue
            if task_id in task_ids:
                task_ids = [t for t in task_ids if t != task_id]
                conn.execute(
                    "UPDATE conflict_groups SET task_ids = ? WHERE id = ?",
                    (json.dumps(task_ids), group_id),
                )

        # 4. The task row itself.
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def _check_feature_deleted(
        self,
        conn: sqlite3.Connection,
        payload: FeatureDeletedPayload,
        event: Event,
    ) -> None:
        """Refuse deletion of a missing or still-referenced feature.

        Was two validation guards in the old handler (feature not found;
        referencing tasks still present). The schema has ``tasks.feature_id
        REFERENCES features(id) ON DELETE RESTRICT``, so the DELETE would
        already fail with a generic FK error; pre-checking names the actual
        blocking task IDs. ``force=True`` does NOT bypass this — deleting a
        feature with tasks is data corruption, not an acceptable risk.
        """
        _ = event
        feature_id = payload.feature_id

        row = conn.execute(
            "SELECT id FROM features WHERE id = ?", (feature_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(
                f"feature.deleted: feature '{feature_id}' not found in state.db"
            )

        blocking = conn.execute(
            "SELECT id FROM tasks WHERE feature_id = ? ORDER BY id", (feature_id,)
        ).fetchall()
        if blocking:
            blocking_ids = [r[0] for r in blocking]
            raise EventRejected(
                f"feature.deleted: refusing to delete feature '{feature_id}' "
                f"while tasks still reference it: {blocking_ids}. "
                "Delete those tasks first (the orphan-prune flow in `plan` "
                "does this in the right order — tasks before features)."
            )

    def _write_feature_deleted(
        self,
        conn: sqlite3.Connection,
        payload: FeatureDeletedPayload,
        event: Event,  # noqa: ARG002 — event metadata recorded via JSONL only
    ) -> None:
        """Delete the Feature row after ``_check_feature_deleted`` cleared it."""
        conn.execute("DELETE FROM features WHERE id = ?", (payload.feature_id,))

    # ------------------------------------------------------------------
    # Phase 8 handler — pull-applies-remote (P1-1 fix)
    # ------------------------------------------------------------------

    def _check_task_synced_from_remote(
        self,
        conn: sqlite3.Connection,
        payload: TaskSyncedFromRemotePayload,
        event: Event,
    ) -> None:
        """Confirm the target task exists before the remote overwrite.

        Was the ``task not found`` guard (0-row UPDATE) in the old handler; now
        rejects up front. No from-status concurrency guard — the sync pull path
        already proved local was untouched before emitting this event.
        """
        _ = event
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (payload.task_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(
                f"task.synced_from_remote: task '{payload.task_id}' not found."
            )

    def _write_task_synced_from_remote(
        self,
        conn: sqlite3.Connection,
        payload: TaskSyncedFromRemotePayload,
        event: Event,
    ) -> None:
        """Overwrite a Task's title / description / status from a remote pull.

        Emitted by the sync CLI's pull path on the
        ``remote_moved and not local_moved`` branch — i.e. the remote
        legitimately moved ahead and there is no local divergence to
        protect. The handler rewrites exactly the three fields the
        forbid-extras payload model exposes (so no Task field outside
        the remote's known shape can be silently lost) and bumps
        ``updated_at`` to the event timestamp.

        Does NOT touch the ``sync_mappings`` row — the caller emits a
        separate ``sync_mapping.upserted`` event for that, keeping the
        mutation surfaces orthogonal (a future "rebuild local from
        remote" replay should NOT also bump the mapping's
        last_synced_at; that's a separate decision).

        ``status`` follows the same field-set rules as
        ``task.status_changed`` — the value must be a valid TaskStatus
        string. We do NOT enforce a from-status concurrency guard here:
        the sync pull path already proved local was untouched
        (``local_moved == False``) before emitting this event, so the
        guard would just duplicate work the caller already did.
        """
        task_id: str = payload.task_id
        title: str = payload.title
        description: str = payload.description
        status: str = payload.status
        timestamp: str = event.timestamp.isoformat()

        conn.execute(
            """
            UPDATE tasks
               SET title = ?,
                   description = ?,
                   status = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (title, description, status, timestamp, task_id),
        )

    # ------------------------------------------------------------------
    # Phase 4 handlers — claim lifecycle
    # ------------------------------------------------------------------

    def _check_claim_created(
        self,
        conn: sqlite3.Connection,
        payload: ClaimCreatedPayload,
        event: Event,
    ) -> None:
        """Decide whether a claim may transition its task ready → claimed.

        The old handler ran the INSERT OR IGNORE + guarded UPDATE, then on a
        0-row UPDATE: ``task not found`` → TransactionAborted; already
        ``'claimed'`` → silent return (replay of a committed claim); any other
        status → concurrency TransactionAborted. This check reproduces the
        reject decisions on read-only state.

        Note: the already-``'claimed'`` case is **not** an ``IdempotentNoOp``
        here — the write must still run so the INSERT OR IGNORE happens. With a
        ready/claimed task the UPDATE simply matches 0 rows, exactly as before,
        and the claim INSERT OR IGNORE is idempotent on its PK. Treating it as a
        no-op would skip the write and change behavior for a fresh claim PK
        against an already-claimed task.
        """
        _ = event
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (payload.task_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(f"claim.created: task '{payload.task_id}' not found.")
        actual_status = row[0]
        if actual_status not in ("ready", "claimed"):
            raise EventRejected(
                f"claim.created: concurrency guard failed for task "
                f"'{payload.task_id}'. Expected status 'ready', got "
                f"'{actual_status}'. Another claim may have already acquired "
                "this task."
            )

    def _write_claim_created(
        self,
        conn: sqlite3.Connection,
        payload: ClaimCreatedPayload,
        event: Event,
    ) -> None:
        """INSERT the claim and transition the task ready → claimed.

        Payload fields (all required):
            id (str)                — claim PK
            task_id (str)          — FK into tasks
            claimed_by (str)       — agent identifier
            claim_type (str)       — ClaimType value
            status (str)           — must be 'active' for a new claim
            branch (str | None)
            worktree_path (str | None)
            expected_files (list[str])
            created_at (str)       — ISO 8601 UTC
            lease_expires_at (str) — ISO 8601 UTC
            last_heartbeat_at (str) — ISO 8601 UTC

        Idempotent: INSERT OR IGNORE on the claim id PK — replay is safe. The
        task UPDATE keeps its WHERE status='ready' guard; when the task is
        already 'claimed' (replay of a committed claim) it matches 0 rows
        harmlessly, which ``_check_claim_created`` already determined is
        acceptable.
        """
        claim_id: str = payload.id
        task_id: str = payload.task_id
        claimed_by: str = payload.claimed_by
        claim_type: str = payload.claim_type
        status: str = payload.status
        created_at: str = payload.created_at
        lease_expires_at: str = payload.lease_expires_at
        last_heartbeat_at: str = payload.last_heartbeat_at
        branch: str | None = payload.branch
        worktree_path: str | None = payload.worktree_path
        expected_files = payload.expected_files
        timestamp: str = event.timestamp.isoformat()

        # INSERT OR IGNORE: idempotent on replay — duplicate claim.created events
        # (after crash mid-transaction) do not produce duplicate rows.
        conn.execute(
            """
            INSERT OR IGNORE INTO claims
                (id, task_id, claimed_by, claim_type, status, branch,
                 worktree_path, expected_files, created_at,
                 lease_expires_at, last_heartbeat_at, released_at, release_reason)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                claim_id,
                task_id,
                claimed_by,
                claim_type,
                status,
                branch,
                worktree_path,
                json.dumps(expected_files),
                created_at,
                lease_expires_at,
                last_heartbeat_at,
            ),
        )

        # Side-effect: transition the task status from 'ready' → 'claimed'.
        # The WHERE status='ready' guard is preserved; on an already-claimed
        # task it matches 0 rows (acceptable per the check) and on a fresh ready
        # task it promotes to claimed.
        conn.execute(
            """
            UPDATE tasks
               SET status = 'claimed',
                   updated_at = ?
             WHERE id = ?
               AND status = 'ready'
            """,
            (timestamp, task_id),
        )

    @staticmethod
    def _claim_release_target(force: bool) -> tuple[str, str]:
        """Return (target_status, SQL status_guard) for a claim release (pure).

        Force-release writes a distinct terminal status (force_released) so the
        audit trail captures the override; normal release uses 'released'. Force
        also allows non-active claims to be released so a stranded stale claim
        can be cleaned up after the fact.
        """
        if force:
            return "force_released", "status NOT IN ('released', 'force_released')"
        return "released", "status = 'active'"

    def _check_claim_released(
        self,
        conn: sqlite3.Connection,
        payload: ClaimReleasedPayload,
        event: Event,
    ) -> None:
        """Decide whether a claim release mutates or is an idempotent no-op.

        The old handler ran the guarded UPDATE then on a 0-row result: claim
        not found → TransactionAborted; already-terminal → warn.idempotent_no_op
        + silent return. This check reproduces those on read-only state: reject
        a missing claim, or signal an ``IdempotentNoOp`` (carrying the warn-log
        metadata so the prior tombstone is still emitted) for an already-terminal
        claim that the guard would not match.
        """
        _ = event
        claim_id: str = payload.claim_id
        row = conn.execute(
            "SELECT status FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(f"claim.released: claim '{claim_id}' not found.")
        current_status = row[0]
        if payload.force:
            guard_matches = current_status not in ("released", "force_released")
        else:
            guard_matches = current_status == "active"
        if not guard_matches:
            # Already terminal — idempotent no-op; the old handler emitted a
            # warn.idempotent_no_op line and returned without raising.
            raise _idempotent_no_op(
                f"claim.released: claim '{claim_id}' already has status "
                f"'{current_status}'; treating as idempotent no-op.",
                warn_action="claim.released",
                warn_target_id=claim_id or "",
            )

    def _write_claim_released(
        self,
        conn: sqlite3.Connection,
        payload: ClaimReleasedPayload,
        event: Event,
    ) -> None:
        """Release the claim and return its task to 'ready'.

        Payload fields (all required):
            claim_id (str)       — PK of the claim to release
            released_by (str)    — agent releasing the claim
            release_reason (str) — human-readable reason

        ``_check_claim_released`` already proved the guard matches, so the
        claims UPDATE always hits a row. The task UPDATE keeps its widened
        WHERE-status guard and tolerates 0 rows (the task may have legitimately
        advanced).
        """
        claim_id: str = payload.claim_id
        release_reason: str | None = payload.release_reason
        force: bool = payload.force
        timestamp: str = event.timestamp.isoformat()

        target_status, status_guard = self._claim_release_target(force)

        conn.execute(
            f"""
            UPDATE claims
               SET status = ?,
                   released_at = ?,
                   release_reason = ?
             WHERE id = ?
               AND {status_guard}
            """,  # noqa: S608 — status_guard is a literal, not user input
            (target_status, timestamp, release_reason, claim_id),
        )

        # Side-effect: return the task to 'ready'. Widened from the original
        # WHERE status='claimed' (which would TransactionAborted on tasks that
        # had advanced to in_progress or blocked) to all post-claim, pre-done
        # statuses. Critic flagged this: release --force is supposed to work
        # even when the task has progressed mid-work.
        task_row = conn.execute(
            "SELECT task_id FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if task_row is not None:
            task_id = task_row[0]
            conn.execute(
                """
                UPDATE tasks
                   SET status = 'ready',
                       updated_at = ?
                 WHERE id = ?
                   AND status IN ('claimed', 'in_progress', 'blocked')
                """,
                (timestamp, task_id),
            )
            # 0 rows is now acceptable: the task may have legitimately advanced
            # to needs_review, accepted, or done in parallel (Phase 5 completion).
            # No error — releasing the claim is the right behaviour regardless.

    def _check_claim_renewed(
        self,
        conn: sqlite3.Connection,
        payload: ClaimRenewedPayload,
        event: Event,
    ) -> None:
        """Confirm the claim exists and is active before extending its lease.

        Was two validation guards in the old handler (claim not found; claim not
        active) interpreted from a 0-row UPDATE; both now reject up front.
        """
        _ = event
        claim_id: str = payload.claim_id
        row = conn.execute(
            "SELECT status FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(f"claim.renewed: claim '{claim_id}' not found.")
        actual_status = row[0]
        if actual_status != "active":
            raise EventRejected(
                f"claim.renewed: cannot renew claim '{claim_id}' "
                f"with status '{actual_status}' (must be 'active')."
            )

    def _write_claim_renewed(
        self,
        conn: sqlite3.Connection,
        payload: ClaimRenewedPayload,
        event: Event,
    ) -> None:
        """Extend the lease on an active claim.

        Payload fields (all required):
            claim_id (str)          — PK of the claim to renew
            lease_expires_at (str)  — new expiry (ISO 8601 UTC)
            last_heartbeat_at (str) — updated heartbeat timestamp (ISO 8601 UTC)

        Does NOT mutate the tasks table.

        ``_check_claim_renewed`` already proved the claim exists and is active,
        so the WHERE status='active' UPDATE always hits a row.

        The event-level timestamp is not used here — the renewed lease timestamps
        come from the payload itself.
        """
        _ = event
        claim_id: str = payload.claim_id
        lease_expires_at: str = payload.lease_expires_at
        last_heartbeat_at: str = payload.last_heartbeat_at

        conn.execute(
            """
            UPDATE claims
               SET lease_expires_at = ?,
                   last_heartbeat_at = ?
             WHERE id = ?
               AND status = 'active'
            """,
            (lease_expires_at, last_heartbeat_at, claim_id),
        )

    def _check_claim_stale(
        self,
        conn: sqlite3.Connection,
        payload: ClaimStalePayload,
        event: Event,
    ) -> None:
        """Decide whether marking a claim stale mutates or is a no-op.

        The old handler ran the guarded UPDATE then on a 0-row result: claim not
        found → TransactionAborted; not active (already stale / terminal) →
        warn.idempotent_no_op + silent return. This check reproduces those on
        read-only state: reject a missing claim, or signal an ``IdempotentNoOp``
        (carrying warn-log metadata) for a non-active claim.
        """
        _ = event
        claim_id: str = payload.claim_id
        row = conn.execute(
            "SELECT status FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(f"claim.stale: claim '{claim_id}' not found.")
        current_status = row[0]
        if current_status != "active":
            raise _idempotent_no_op(
                f"claim.stale: claim '{claim_id}' already has status "
                f"'{current_status}'; treating as idempotent no-op.",
                warn_action="claim.stale",
                warn_target_id=claim_id or "",
            )

    def _write_claim_stale(
        self,
        conn: sqlite3.Connection,
        payload: ClaimStalePayload,
        event: Event,
    ) -> None:
        """Mark an active claim as stale and return the task to 'ready'.

        Payload fields (all required):
            claim_id (str)    — PK of the claim to mark stale
            detected_at (str) — when staleness was detected (ISO 8601 UTC)
            reason (str)      — typically 'lease_expired'

        ``_check_claim_stale`` already proved the claim is active, so the WHERE
        status='active' UPDATE always hits a row.

        Side-effect: UPDATE tasks SET status='ready' WHERE id=task_id AND
        status IN ('claimed', 'in_progress', 'blocked').  If the task status
        has already moved beyond those states (e.g., accepted, done), the
        UPDATE is a no-op — that is intentional and not an error.
        """
        claim_id: str = payload.claim_id
        timestamp: str = event.timestamp.isoformat()

        conn.execute(
            """
            UPDATE claims
               SET status = 'stale',
                   released_at = ?,
                   release_reason = 'lease_expired'
             WHERE id = ?
               AND status = 'active'
            """,
            (timestamp, claim_id),
        )

        # Side-effect: return the task to 'ready' if it is still in an
        # active-work status.  Tasks already at accepted/done/rejected are
        # left untouched — the work completed before the lease expired.
        task_row = conn.execute(
            "SELECT task_id FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if task_row is not None:
            task_id = task_row[0]
            conn.execute(
                """
                UPDATE tasks
                   SET status = 'ready',
                       updated_at = ?
                 WHERE id = ?
                   AND status IN ('claimed', 'in_progress', 'blocked')
                """,
                (timestamp, task_id),
            )
            # No error if 0 rows — the task may have been completed already.

    # ------------------------------------------------------------------
    # Phase 5 handlers — completion flow
    # ------------------------------------------------------------------

    def _check_evidence_submitted(
        self,
        conn: sqlite3.Connection,
        payload: EvidenceSubmittedPayload,
        event: Event,
    ) -> None:
        """Validate the evidence payload and decide the submission outcome.

        Reproduces the old handler's pre-mutation guards on read-only state:

        - Empty ``commands_run`` / ``files_changed`` → reject (was
          TransactionAborted).
        - CL-8 double-submit (this claim already carries evidence under a
          *different* id) → ``IdempotentNoOp`` carrying the warn-log metadata, so
          the prior warn.idempotent_no_op tombstone is still emitted and nothing
          mutates.
        - Task missing → reject; task not in an eligible status and not already
          ``needs_review`` → reject (was the 0-row TransactionAborted).

        The claim auto-release branch (and its conditional warn log) is NOT a
        gate — it is a side effect of the write and stays there.
        """
        _ = event
        if not payload.commands_run:
            raise EventRejected(
                "evidence.submitted payload requires non-empty 'commands_run'."
            )
        if not payload.files_changed:
            raise EventRejected(
                "evidence.submitted payload requires non-empty 'files_changed'."
            )

        claim_id: str = payload.claim_id
        evidence_id: str = payload.evidence_id
        task_id: str = payload.task_id

        # CL-8 idempotency guard: a second submit under a DIFFERENT evidence_id
        # is a double-submit; the old handler emitted a warn line and returned.
        existing_row = conn.execute(
            "SELECT id FROM evidence WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if existing_row is not None and existing_row[0] != evidence_id:
            raise _idempotent_no_op(
                f"evidence.submitted: claim '{claim_id}' already has evidence "
                f"'{existing_row[0]}'; rejecting duplicate submission with new "
                f"evidence_id '{evidence_id}' as idempotent no-op (CL-8).",
                warn_action="evidence.submitted",
                warn_target_id=claim_id or "",
            )

        # Task eligibility: must exist and be in an active-work status, or be
        # already at needs_review (idempotent replay — write's task UPDATE will
        # no-op harmlessly).
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(
                f"evidence.submitted: task '{task_id}' not found."
            )
        actual_status = row[0]
        if actual_status not in (
            "claimed",
            "in_progress",
            "blocked",
            "needs_review",
        ):
            raise EventRejected(
                f"evidence.submitted: task '{task_id}' has status "
                f"'{actual_status}', which is not eligible for evidence submission "
                "(must be 'claimed', 'in_progress', or 'blocked')."
            )

    def _write_evidence_submitted(
        self,
        conn: sqlite3.Connection,
        payload: EvidenceSubmittedPayload,
        event: Event,
    ) -> None:
        """Insert evidence, transition task to needs_review, auto-release claim.

        Payload fields:
            task_id (str)            — required; FK into tasks
            claim_id (str)           — required; FK into claims
            submitted_by (str)       — required; agent identifier
            evidence_id (str)        — required; PK for the evidence row
            commands_run (list[str]) — required; must be non-empty
            files_changed (list[str])— required
            output_excerpt (str | None) — optional
            pr_url (str | None)         — optional
            commit_sha (str | None)     — optional
            screenshots (list[str])     — optional, default []
            known_limitations (str | None) — optional

        ``_check_evidence_submitted`` already validated the payload, screened the
        CL-8 double-submit, and proved task eligibility. The mutations here are
        infallible:
            - INSERT OR IGNORE on evidence.id PK — idempotent on replay.
            - Task UPDATE (claimed/in_progress/blocked → needs_review) matches a
              row, or no-ops when the task was already needs_review.
            - Claim auto-release (UPDATE active → released). 0 rows means the
              claim was already released/stale; the conditional warn log records
              that — it is an audit side effect, not a rejection.
        """
        task_id: str = payload.task_id
        claim_id: str = payload.claim_id
        submitted_by: str = payload.submitted_by
        evidence_id: str = payload.evidence_id
        commands_run: list[Any] = payload.commands_run
        files_changed: list[Any] = payload.files_changed
        timestamp: str = event.timestamp.isoformat()

        output_excerpt: str | None = payload.output_excerpt
        pr_url: str | None = payload.pr_url
        commit_sha: str | None = payload.commit_sha
        screenshots: list[Any] = payload.screenshots or []
        known_limitations: str | None = payload.known_limitations

        # INSERT OR IGNORE: idempotent on replay — duplicate evidence.submitted
        # events (after crash mid-transaction) do not produce duplicate rows.
        conn.execute(
            """
            INSERT OR IGNORE INTO evidence
                (id, task_id, claim_id, commands_run, output_excerpt,
                 files_changed, pr_url, commit_sha, screenshots,
                 known_limitations, submitted_at, submitted_by)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                task_id,
                claim_id,
                json.dumps(commands_run),
                output_excerpt,
                json.dumps(files_changed),
                pr_url,
                commit_sha,
                json.dumps(screenshots),
                known_limitations,
                timestamp,
                submitted_by,
            ),
        )

        # Atomically transition the task to needs_review.
        # WHERE status IN ('claimed', 'in_progress', 'blocked') is the
        # concurrency guard — allows submit from any active-work status.
        # ``_check_evidence_submitted`` already proved the task is in one of
        # those statuses or already at needs_review, so a 0-row result here is
        # the harmless idempotent-replay case (no raise needed).
        conn.execute(
            """
            UPDATE tasks
               SET status = 'needs_review',
                   updated_at = ?
             WHERE id = ?
               AND status IN ('claimed', 'in_progress', 'blocked')
            """,
            (timestamp, task_id),
        )

        # Auto-release the active claim.
        conn.execute(
            """
            UPDATE claims
               SET status = 'released',
                   released_at = ?,
                   release_reason = 'auto-released on submit'
             WHERE id = ?
               AND status = 'active'
            """,
            (timestamp, claim_id),
        )

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            # Claim already released or stale — idempotent; log warning only.
            row = conn.execute(
                "SELECT status FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
            current_status = row[0] if row else "not found"
            self._append_warn_log(
                action="evidence.submitted",
                target_id=claim_id or "",
                reason=(
                    f"evidence.submitted: claim '{claim_id}' auto-release skipped; "
                    f"current status is '{current_status}'."
                ),
            )

    def _check_task_applied(
        self,
        conn: sqlite3.Connection,
        payload: TaskAppliedPayload,
        event: Event,
    ) -> None:
        """Validate the decision and the task's eligibility for it.

        Reproduces the old handler's pre-mutation guards on read-only state:

        - ``decision`` must be 'accepted' or 'rejected' → reject.
        - Task must exist → reject.
        - Task status must be ``needs_review`` (fresh apply) or, for replay
          idempotency, already in the decision's terminal set
          (accepted/done for accept, rejected/drafted for reject) → otherwise
          reject as status-drift.

        The accepted → done / rejected → drafted auto-promotion (and its
        defensive 0-row invariant) is a write-phase concern, left in
        ``_write_task_applied``.
        """
        _ = event
        decision: str = payload.decision
        task_id: str = payload.task_id

        if decision not in ("accepted", "rejected"):
            raise EventRejected(
                f"task.applied: 'decision' must be 'accepted' or 'rejected', "
                f"got {decision!r}."
            )

        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise EventRejected(f"task.applied: task '{task_id}' not found.")
        actual_status = row[0]
        if actual_status == "needs_review":
            return  # fresh apply — proceed.
        acceptable = (
            ("accepted", "done")
            if decision == "accepted"
            else ("rejected", "drafted")
        )
        if actual_status not in acceptable:
            raise EventRejected(
                f"task.applied: status-drift for task '{task_id}'. "
                f"Expected 'needs_review', got '{actual_status}'. "
                "The task may have been reviewed by a concurrent operation."
            )

    def _write_task_applied(
        self,
        conn: sqlite3.Connection,
        payload: TaskAppliedPayload,
        event: Event,
    ) -> None:
        """Gate needs_review → accepted → done (or rejected) and record a Review.

        Payload fields:
            task_id (str)              — required
            reviewer (str)             — required
            decision (str)             — required; 'accepted' or 'rejected'
            notes (str | None)         — optional

        Transition logic:
            - decision='accepted': UPDATE tasks SET status='accepted' WHERE
              status='needs_review', then immediately UPDATE tasks SET
              status='done'. These two mutations are committed in the same
              transaction (accepted → done is automatic; they are never split).
            - decision='rejected': UPDATE tasks SET status='rejected' WHERE
              status='needs_review'.

        Review row:
            INSERT OR REPLACE INTO reviews with id=f"RV-{event_id}" for
            replay safety. target_kind='task', target_id=task_id.

        ``_check_task_applied`` already validated the decision and proved the
        task is at needs_review (or in the idempotent-replay terminal set). The
        WHERE-status guards and 0-row branches remain as a defensive belt that
        handles the idempotent-replay no-op without raising; the only surviving
        raise is the accepted → done auto-promote invariant, which signals a
        genuine unexpected concurrent mutation (infra-class, not a validation
        rejection).
        """
        task_id: str = payload.task_id
        reviewer: str = payload.reviewer
        decision: str = payload.decision
        notes: str | None = payload.notes
        event_id: str = event.id
        timestamp: str = event.timestamp.isoformat()

        if decision == "accepted":
            # Transition needs_review → accepted.
            conn.execute(
                """
                UPDATE tasks
                   SET status = 'accepted',
                       updated_at = ?
                 WHERE id = ?
                   AND status = 'needs_review'
                """,
                (timestamp, task_id),
            )
            if conn.execute("SELECT changes()").fetchone()[0] == 0:
                row = conn.execute(
                    "SELECT status FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
                if row is None:
                    raise TransactionAborted(
                        f"task.applied: task '{task_id}' not found."
                    )
                actual_status = row[0]
                # Idempotent replay: already accepted or done.
                if actual_status not in ("accepted", "done"):
                    raise TransactionAborted(
                        f"task.applied: status-drift for task '{task_id}'. "
                        f"Expected 'needs_review', got '{actual_status}'. "
                        "The task may have been reviewed by a concurrent operation."
                    )
            else:
                # Immediately promote accepted → done in the same transaction.
                conn.execute(
                    """
                    UPDATE tasks
                       SET status = 'done',
                           updated_at = ?
                     WHERE id = ?
                       AND status = 'accepted'
                    """,
                    (timestamp, task_id),
                )
                # accepted → done is an automatic follow-up; 0 rows here would
                # be a logic error (we just set it to 'accepted' above), so we
                # do raise — it signals an unexpected concurrent mutation.
                if conn.execute("SELECT changes()").fetchone()[0] == 0:
                    raise TransactionAborted(
                        f"task.applied: failed to auto-promote task '{task_id}' "
                        "from 'accepted' to 'done'. Unexpected concurrent mutation."
                    )

        else:  # decision == "rejected"
            # Per spec: needs_review → rejected → drafted (automatic; same txn).
            # The 'rejected' state is a brief audit marker; the task immediately
            # transitions to 'drafted' so it can be re-reviewed and re-promoted.
            # Critic-1 + Critic-2 both flagged that the original code left the
            # task permanently at 'rejected' with no path back, contradicting
            # docs/specs/2026-05-24-fakoli-state-v0.md and skills/finish/SKILL.md.
            conn.execute(
                """
                UPDATE tasks
                   SET status = 'rejected',
                       updated_at = ?
                 WHERE id = ?
                   AND status = 'needs_review'
                """,
                (timestamp, task_id),
            )
            if conn.execute("SELECT changes()").fetchone()[0] == 0:
                row = conn.execute(
                    "SELECT status FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
                if row is None:
                    raise TransactionAborted(
                        f"task.applied: task '{task_id}' not found."
                    )
                actual_status = row[0]
                # Idempotent replay: either we already rejected (transient
                # marker before drafted) or already drafted (final state).
                if actual_status not in ("rejected", "drafted"):
                    raise TransactionAborted(
                        f"task.applied: status-drift for task '{task_id}'. "
                        f"Expected 'needs_review', got '{actual_status}'. "
                        "The task may have been reviewed by a concurrent operation."
                    )
            else:
                # Initial run (not replay): auto-promote rejected → drafted
                # in the same transaction. The audit log carries 'rejected'
                # as the recorded decision; the task lifecycle continues
                # at 'drafted' so it can be re-reviewed.
                conn.execute(
                    """
                    UPDATE tasks
                       SET status = 'drafted',
                           updated_at = ?
                     WHERE id = ?
                       AND status = 'rejected'
                    """,
                    (timestamp, task_id),
                )

        # Insert the Review row — INSERT OR REPLACE for replay safety.
        review_id = f"RV-{event_id}"
        conn.execute(
            """
            INSERT OR REPLACE INTO reviews
                (id, target_kind, target_id, reviewed_by, decision, notes, created_at)
            VALUES
                (?, 'task', ?, ?, ?, ?, ?)
            """,
            (review_id, task_id, reviewer, decision, notes, timestamp),
        )

    # ------------------------------------------------------------------
    # Phase 8 handlers — sync_mappings (external-system mirror)
    # ------------------------------------------------------------------

    def _check_sync_mapping_upserted(
        self,
        conn: sqlite3.Connection,
        payload: SyncMappingUpsertedPayload,
        event: Event,
    ) -> None:
        """Validate the SyncMapping (enum / UTC checks) before the upsert.

        Was a validation guard inside the old handler (``raise
        TransactionAborted`` on an invalid SyncMapping); now rejects up front.
        """
        _ = (conn, event)
        try:
            SyncMapping.model_validate(payload.model_dump())
        except Exception as exc:
            raise EventRejected(
                f"sync_mapping.upserted: invalid SyncMapping payload: {exc}"
            ) from exc

    def _write_sync_mapping_upserted(
        self,
        conn: sqlite3.Connection,
        payload: SyncMappingUpsertedPayload,
        event: Event,
    ) -> None:
        """Insert a sync_mappings row, or UPDATE on (task_id, external_system) conflict.

        The composite primary key is (task_id, external_system), so a task that
        is mirrored into two external systems gets two rows — the upsert keys
        on the full PK, not on task_id alone. This is intentional: a task can
        legitimately have a github_issues mapping AND, in the future, a
        linear mapping, both kept in sync.

        ``_check_sync_mapping_upserted`` already validated the payload; the
        ``model_validate`` here is an infallible rebuild that yields the
        canonical serialized form.
        """
        mapping = SyncMapping.model_validate(payload.model_dump())

        # Use the validated model's serialized form so enum values become the
        # canonical string. last_synced_at is already an ISO string from the
        # payload model.
        data = mapping.model_dump(mode="json")
        _ = event  # event-level timestamp not used; mapping carries last_synced_at
        # provider_metadata is opaque dict — serialise to JSON for the
        # provider_metadata_json TEXT column.
        provider_metadata_json = json.dumps(data.get("provider_metadata") or {})
        conn.execute(
            """
            INSERT INTO sync_mappings
                (task_id, external_system, external_id, external_url,
                 last_synced_at, sync_state, conflict_resolution_strategy,
                 provider_metadata_json)
            VALUES
                (:task_id, :external_system, :external_id, :external_url,
                 :last_synced_at, :sync_state, :conflict_resolution_strategy,
                 :provider_metadata_json)
            ON CONFLICT(task_id, external_system) DO UPDATE SET
                external_id                  = excluded.external_id,
                external_url                 = excluded.external_url,
                last_synced_at               = excluded.last_synced_at,
                sync_state                   = excluded.sync_state,
                conflict_resolution_strategy = excluded.conflict_resolution_strategy,
                provider_metadata_json       = excluded.provider_metadata_json
            """,
            {
                "task_id": data["task_id"],
                "external_system": data["external_system"],
                "external_id": data["external_id"],
                "external_url": data.get("external_url"),
                "last_synced_at": data["last_synced_at"],
                "sync_state": data["sync_state"],
                "conflict_resolution_strategy": data["conflict_resolution_strategy"],
                "provider_metadata_json": provider_metadata_json,
            },
        )

    def _check_sync_mapping_deleted(
        self,
        conn: sqlite3.Connection,
        payload: SyncMappingDeletedPayload,
        event: Event,
    ) -> None:
        """No validation gate — sync_mapping.deleted is an idempotent delete."""
        _ = (conn, payload, event)

    def _write_sync_mapping_deleted(
        self,
        conn: sqlite3.Connection,
        payload: SyncMappingDeletedPayload,
        event: Event,
    ) -> None:
        """Delete sync_mappings row(s) for ``task_id``.

        If ``external_system`` is provided the delete is scoped to that single
        row (composite-key delete). If absent, every mapping for the task is
        removed — supports the "untrack everything" case.

        Idempotent: a delete against an already-absent row is a silent no-op.
        Audit visibility comes from the event row itself, recorded by the
        caller in the events table.
        """
        _ = event  # event-level timestamp not used; delete carries no audit field
        if payload.external_system is None:
            conn.execute(
                "DELETE FROM sync_mappings WHERE task_id = ?",
                (payload.task_id,),
            )
        else:
            conn.execute(
                "DELETE FROM sync_mappings WHERE task_id = ? AND external_system = ?",
                (payload.task_id, payload.external_system),
            )

    # ------------------------------------------------------------------
    # Internal helpers — task row insertion (shared by task.created and
    # task.expanded)
    # ------------------------------------------------------------------

    def _insert_task_row(self, conn: sqlite3.Connection, task: Task) -> None:
        """Insert or upsert a Task row in the tasks table.

        Uses INSERT ... ON CONFLICT DO UPDATE (not INSERT OR REPLACE) for the
        same reason as feature.created: INSERT OR REPLACE is DELETE + INSERT,
        which trips ON DELETE RESTRICT on claims.task_id and evidence.task_id
        if anything has been claimed against this task. The upsert pattern
        preserves the row identity, so foreign keys remain valid even when
        `plan` is re-run after work has begun.
        """
        data = task.model_dump(mode="json")
        conn.execute(
            """
            INSERT INTO tasks
                (id, feature_id, title, description, status, priority,
                 dependencies, conflict_groups, scores, acceptance_criteria,
                 implementation_notes, verification, likely_files,
                 parent_task_id, created_at, updated_at)
            VALUES
                (:id, :feature_id, :title, :description, :status, :priority,
                 :dependencies, :conflict_groups, :scores, :acceptance_criteria,
                 :implementation_notes, :verification, :likely_files,
                 :parent_task_id, :created_at, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                feature_id           = excluded.feature_id,
                title                = excluded.title,
                description          = excluded.description,
                -- status is intentionally OMITTED from the upsert. Status
                -- transitions go exclusively through task.status_changed
                -- events. If task.created carried status=proposed and we
                -- overwrote it on re-plan, a re-plan after Phase 4 claims
                -- would silently reset claimed/in_progress tasks back to
                -- proposed, stripping the claim. Greptile flagged this on
                -- PR #38; the fix is to let status be managed by its
                -- dedicated transition handler only.
                priority             = excluded.priority,
                dependencies         = excluded.dependencies,
                conflict_groups      = excluded.conflict_groups,
                scores               = excluded.scores,
                acceptance_criteria  = excluded.acceptance_criteria,
                implementation_notes = excluded.implementation_notes,
                verification         = excluded.verification,
                likely_files         = excluded.likely_files,
                parent_task_id       = excluded.parent_task_id,
                updated_at           = excluded.updated_at
            """,
            {
                "id": data["id"],
                "feature_id": data["feature_id"],
                "title": data["title"],
                "description": data["description"],
                "status": data["status"],
                "priority": data["priority"],
                "dependencies": json.dumps(data["dependencies"]),
                "conflict_groups": json.dumps(data["conflict_groups"]),
                "scores": json.dumps(data["scores"]),
                "acceptance_criteria": json.dumps(data["acceptance_criteria"]),
                "implementation_notes": json.dumps(data["implementation_notes"]),
                "verification": json.dumps(data["verification"]),
                "likely_files": json.dumps(data["likely_files"]),
                "parent_task_id": data["parent_task_id"],
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
            },
        )

    def _insert_event_row(self, conn: sqlite3.Connection, event: Event) -> None:
        """Insert the event into the events mirror table."""
        data = event.model_dump(mode="json")
        conn.execute(
            """
            INSERT OR IGNORE INTO events
                (id, timestamp, actor, action, target_kind, target_id, payload_json)
            VALUES
                (:id, :timestamp, :actor, :action, :target_kind, :target_id, :payload_json)
            """,
            {
                "id": data["id"],
                "timestamp": data["timestamp"],
                "actor": data["actor"],
                "action": data["action"],
                "target_kind": data["target_kind"],
                "target_id": data["target_id"],
                "payload_json": json.dumps(data["payload_json"]),
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers — replay (JSONL-only path)
    # ------------------------------------------------------------------

    def _apply_event_sqlite_only(self, event: Event) -> None:
        """Apply a single event to SQLite without writing to JSONL.

        Used exclusively during replay_from_empty().
        """
        conn = self._require_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._apply_mutation(conn, event)
            self._insert_event_row(conn, event)
            conn.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            self._safe_rollback(conn)
            if "database is locked" in str(exc).lower():
                raise StateLocked(
                    f"SQLite busy_timeout exceeded during replay of event {event.id!r}: {exc}"
                ) from exc
            raise TransactionAborted(
                f"Transaction aborted during replay of event {event.id!r}: {exc}"
            ) from exc
        except NotImplementedError:
            # During replay, unsupported actions are skipped gracefully.
            self._safe_rollback(conn)
        except Exception as exc:
            self._safe_rollback(conn)
            raise TransactionAborted(
                f"Transaction aborted during replay of event {event.id!r}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers — error handling
    # ------------------------------------------------------------------

    def _safe_rollback(self, conn: sqlite3.Connection) -> None:
        """Attempt a ROLLBACK; ignore errors (connection may already be closed)."""
        try:
            conn.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            pass

    def _append_abort_event(self, failed_event: Event, reason: str) -> None:
        """Append an error.transaction_aborted tombstone to the JSONL log."""
        now = self._clock.now()
        # If the failure happened on the PENDING path before ID assignment, the
        # event still carries the sentinel. Synthesize a unique ABORT-PENDING-*
        # id so tombstones don't collide and the audit line is correlatable.
        if failed_event.id == PENDING_EVENT_ID:
            ts_us = int(now.timestamp() * 1_000_000)
            tombstone_id = f"ABORT-PENDING-{failed_event.action}-{ts_us}"
        else:
            tombstone_id = failed_event.id
        abort_data = {
            "id": tombstone_id,
            "timestamp": now.isoformat(),
            "actor": "system",
            "action": "error.transaction_aborted",
            "target_kind": failed_event.target_kind,
            "target_id": failed_event.target_id,
            "payload_json": {
                "original_action": failed_event.action,
                "reason": reason,
            },
        }
        try:
            with open(self._events_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(abort_data) + "\n")
        except OSError as fs_exc:
            # If we can't write the abort tombstone, surface via the process
            # logger so the SQLite/JSONL divergence is at least visible to
            # operators. Raising would mask the caller's TransactionAborted.
            logger.error(
                "Failed to write abort tombstone for event %r (action=%r, "
                "original_reason=%r): %s",
                tombstone_id,
                failed_event.action,
                reason,
                fs_exc,
            )

    def _append_warn_log(
        self,
        action: str,
        target_id: str,
        reason: str,
    ) -> None:
        """Append a warn.idempotent_no_op entry to the JSONL log.

        Used for idempotent no-ops (already-released / already-stale claims)
        where we need an audit trail but must not raise TransactionAborted.
        Unlike _append_abort_event this method does not require an Event object,
        so it avoids constructing a model with a non-standard ID.
        """
        now = self._clock.now()
        warn_data = {
            "timestamp": now.isoformat(),
            "actor": "system",
            "action": "warn.idempotent_no_op",
            "target_kind": "claim",
            "target_id": target_id,
            "payload_json": {
                "original_action": action,
                "reason": reason,
            },
        }
        try:
            with open(self._events_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(warn_data) + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Internal helpers — row → model conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(
        row: sqlite3.Row | tuple[Any, ...],
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        """Convert a sqlite3 row (with description) to a plain dict."""
        # sqlite3.Row supports keys() if the connection has row_factory set.
        # We use description-based conversion to avoid requiring row_factory.
        if isinstance(row, sqlite3.Row):
            return dict(row)
        # Fallback: use the cursor description from a previous query.
        # This path should not be reached if callers use fetchone()/fetchall()
        # on a cursor configured with row_factory.
        raise RuntimeError(  # pragma: no cover
            "Unexpected row type; configure row_factory on the connection."
        )

    def _row_to_task(
        self,
        row: Any,
        conn: sqlite3.Connection,  # noqa: ARG002 — reserved for future join queries
    ) -> Task:
        """Deserialise a tasks row into a Task model instance."""
        d = dict(row)
        # JSON columns need parsing back.
        for col in (
            "dependencies",
            "conflict_groups",
            "acceptance_criteria",
            "implementation_notes",
            "likely_files",
        ):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        for col in ("scores", "verification"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return Task.model_validate(d)

    def _row_to_claim(self, row: Any) -> Claim:
        """Deserialise a claims row into a Claim model instance."""
        d = dict(row)
        if isinstance(d.get("expected_files"), str):
            d["expected_files"] = json.loads(d["expected_files"])
        return Claim.model_validate(d)

    @staticmethod
    def _row_to_review(row: Any) -> Review:
        """Deserialise a reviews row into a Review model instance.

        The reviews table stores two decision vocabularies:
        - prd.approved writes ``"approve"`` (ReviewDecision canonical value).
        - task.applied writes the raw outcome string (``"accepted"`` or
          ``"rejected"``), which predates the ReviewDecision enum.

        To allow the Review model's enum to validate correctly we map
        task-outcome values to their ReviewDecision equivalents using the
        module-level ``_TASK_OUTCOME_TO_REVIEW_DECISION`` constant:
          ``"accepted"`` → ``ReviewDecision.approve``   (``"approve"``)
          ``"rejected"`` → ``ReviewDecision.needs_changes`` (``"needs_changes"``)

        ``"rejected"`` maps to ``needs_changes`` (NOT ``reject``) because a
        rejected task auto-promotes to ``drafted`` for rework; it is not a
        terminal closure.  See _TASK_OUTCOME_TO_REVIEW_DECISION and
        _handle_task_applied for the full rationale.

        All other decision values (``"approve"``, ``"reject"``,
        ``"needs_changes"``) are passed through unchanged.
        """
        d = dict(row)
        raw_decision = d.get("decision")
        if raw_decision in _TASK_OUTCOME_TO_REVIEW_DECISION:
            d["decision"] = _TASK_OUTCOME_TO_REVIEW_DECISION[raw_decision]
        elif raw_decision is not None and raw_decision not in {v.value for v in ReviewDecision}:
            _valid = sorted(_TASK_OUTCOME_TO_REVIEW_DECISION) + [v.value for v in ReviewDecision]
            raise ValueError(
                f"_row_to_review: unexpected decision value {raw_decision!r}. "
                f"Expected one of {_valid}."
            )
        # A NULL decision column (raw_decision is None) is left as-is for
        # Review.model_validate to reject with a schema-level error, rather than
        # the misleading "unexpected value" mapping error above.
        return Review.model_validate(d)

    @staticmethod
    def _row_to_evidence(row: Any) -> Evidence:
        """Deserialise an evidence row (positional tuple) into an Evidence model instance.

        Row column order must match the SELECT used in list_evidence and
        get_latest_evidence:
          0:id  1:task_id  2:claim_id  3:commands_run  4:output_excerpt
          5:files_changed  6:pr_url  7:commit_sha  8:screenshots
          9:known_limitations  10:submitted_at  11:submitted_by
        """
        import datetime

        from fakoli_state.state.models import Evidence as _Evidence

        submitted_at = datetime.datetime.fromisoformat(row[10])
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=datetime.UTC)
        return _Evidence(
            id=row[0],
            task_id=row[1],
            claim_id=row[2],
            commands_run=json.loads(row[3] or "[]"),
            output_excerpt=row[4],
            files_changed=json.loads(row[5] or "[]"),
            pr_url=row[6],
            commit_sha=row[7],
            screenshots=json.loads(row[8] or "[]"),
            known_limitations=row[9],
            submitted_at=submitted_at,
            submitted_by=row[11],
        )

    def _row_to_prd(self, row: Any) -> PRD:
        """Deserialise a prds row into a PRD model instance."""
        d = dict(row)
        # Remove the synthetic project_id PK column — PRD model doesn't have it.
        d.pop("project_id", None)
        for col in (
            "goals",
            "non_goals",
            "requirements",
            "acceptance_criteria",
            "risks",
            "open_questions",
        ):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return PRD.model_validate(d)

    def _row_to_project(self, row: Any) -> Project:
        """Deserialise a projects row into a Project model instance."""
        return Project.model_validate(dict(row))

    @staticmethod
    def _row_to_requirement(row: Any) -> Requirement:
        """Deserialise a requirements row into a Requirement model instance.

        Row column order must match the SELECT used in list_requirements:
          0:id  1:prd_section  2:text  3:source_paragraph  4:derived

        The ``derived`` column is stored as an integer (0/1) — bool() is
        applied so the Requirement model receives a proper Python bool.
        """
        return Requirement(
            id=row[0],
            prd_section=row[1],
            text=row[2],
            source_paragraph=row[3],
            derived=bool(row[4]),
        )

    @staticmethod
    def _row_to_sync_mapping(row: Any) -> SyncMapping:
        """Deserialise a sync_mappings row into a SyncMapping model instance.

        The DB column ``provider_metadata_json`` is renamed to the model
        field ``provider_metadata`` after a JSON parse; ``external_url``
        passes through directly. Missing columns (older rows) default
        cleanly via the model's own defaults.
        """
        d = dict(row)
        raw_meta = d.pop("provider_metadata_json", None)
        if raw_meta:
            d["provider_metadata"] = json.loads(raw_meta)
        else:
            d["provider_metadata"] = {}
        return SyncMapping.model_validate(d)
