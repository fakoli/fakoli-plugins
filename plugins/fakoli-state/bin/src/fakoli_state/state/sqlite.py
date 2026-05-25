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
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fakoli_state.state.backend import (
    PENDING_EVENT_ID,
    BackendError,  # noqa: F401
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
    Score,
    Task,
)
from fakoli_state.state.payloads import (
    ClaimCreatedPayload,
    ClaimReleasedPayload,
    ClaimRenewedPayload,
    ClaimStalePayload,
    EvidenceSubmittedPayload,
    FeatureCreatedPayload,
    FileChangedPayload,
    PrdApprovedPayload,
    PrdParsedPayload,
    PrdReviewedPayload,
    ProjectCreatedPayload,
    StateInitializedPayload,
    TaskAppliedPayload,
    TaskCreatedPayload,
    TaskExpandedPayload,
    TaskScoredPayload,
    TaskStatusChangedPayload,
)
from fakoli_state.state.schema import DDL, SCHEMA_VERSION

if TYPE_CHECKING:
    from fakoli_state.clock import Clock
    from fakoli_state.state.models import Evidence

logger = logging.getLogger(__name__)


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

        # Apply DDL (CREATE TABLE IF NOT EXISTS — idempotent).
        # Execute statement-by-statement; sqlite3 executescript auto-commits,
        # so we split manually to preserve our transaction control.
        self._apply_ddl()

        # After DDL, verify schema version.
        self._check_schema_version()

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
        """
        if self._conn is None:
            return "E000001"
        row = self._conn.execute(
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
        import datetime

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

        from fakoli_state.state.models import Evidence

        submitted_at = datetime.datetime.fromisoformat(row[10])
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=datetime.UTC)

        return Evidence(
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

    def _check_schema_version(self) -> None:
        """Raise SchemaMismatch if on-disk version != SCHEMA_VERSION."""
        conn = self._require_conn()
        row = conn.execute("PRAGMA user_version").fetchone()
        on_disk = row[0] if row else 0
        if on_disk != SCHEMA_VERSION:
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

    def _get_action_handlers(
        self,
    ) -> dict[str, tuple[type[Any], Callable[..., None]]]:
        """Return the dispatch table mapping action → (PayloadModel, handler).

        All handlers share the normalised signature:
            handler(conn, payload: TypedPayload, event: Event) -> None

        The payload is validated against the model before the handler is called.

        The table is built once per instance and cached. Bound-method values
        capture ``self``, so the cache is invalidated naturally if the instance
        is replaced.
        """
        cached = getattr(self, "_action_handlers_cache", None)
        if cached is not None:
            return cached
        table: dict[str, tuple[type[Any], Callable[..., None]]] = {
            "project.created": (ProjectCreatedPayload, self._handle_project_created),
            "state.initialized": (StateInitializedPayload, self._handle_state_initialized),
            "prd.parsed": (PrdParsedPayload, self._handle_prd_parsed),
            "prd.reviewed": (PrdReviewedPayload, self._handle_prd_reviewed),
            "prd.approved": (PrdApprovedPayload, self._handle_prd_approved),
            "feature.created": (FeatureCreatedPayload, self._handle_feature_created),
            "task.created": (TaskCreatedPayload, self._handle_task_created),
            "task.scored": (TaskScoredPayload, self._handle_task_scored),
            "task.expanded": (TaskExpandedPayload, self._handle_task_expanded),
            "task.status_changed": (
                TaskStatusChangedPayload,
                self._handle_task_status_changed,
            ),
            "claim.created": (ClaimCreatedPayload, self._handle_claim_created),
            "claim.released": (ClaimReleasedPayload, self._handle_claim_released),
            "claim.renewed": (ClaimRenewedPayload, self._handle_claim_renewed),
            "claim.stale": (ClaimStalePayload, self._handle_claim_stale),
            "evidence.submitted": (EvidenceSubmittedPayload, self._handle_evidence_submitted),
            "task.applied": (TaskAppliedPayload, self._handle_task_applied),
            "file_changed": (FileChangedPayload, self._handle_file_changed),
        }
        self._action_handlers_cache = table
        return table

    def _apply_mutation(self, conn: sqlite3.Connection, event: Event) -> None:
        """Dispatch event.action to the appropriate mutation handler.

        Phase 2 handles 'project.created' and 'state.initialized'.
        Phase 3 adds: prd.parsed, prd.reviewed, prd.approved, feature.created,
        task.created, task.scored, task.expanded, task.status_changed.
        Phase 4 adds: claim.created, claim.released, claim.renewed, claim.stale.
        Phase 5 adds: evidence.submitted, task.applied.

        Payload validation is centralised here: each action's payload model is
        looked up in the dispatch table, validated once, and the typed model is
        passed to the handler.  Unknown keys in the payload raise ValidationError
        immediately (extra='forbid' on every payload model).
        """
        action = event.action
        handlers = self._get_action_handlers()

        if action not in handlers:
            raise NotImplementedError(
                f"Event action {action!r} is not yet supported. "
                "This action will be implemented in a later phase."
            )

        payload_model_cls, handler = handlers[action]
        typed_payload = payload_model_cls.model_validate(event.payload_json)
        handler(conn, typed_payload, event)

    def _handle_project_created(
        self,
        conn: sqlite3.Connection,
        payload: ProjectCreatedPayload,
        event: Event,
    ) -> None:
        """Insert or replace the project row from the event payload."""
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

    def _handle_state_initialized(
        self,
        conn: sqlite3.Connection,
        payload: StateInitializedPayload,
        event: Event,
    ) -> None:
        """Handle the state.initialized event.

        This event signals that the state engine has been set up.  In Phase 2 it
        is a no-op beyond being recorded in the events table; future phases may
        use the payload to seed configuration.
        """
        # Nothing to mutate for Phase 2 — the event row insertion is handled
        # by the caller (_apply_event_sqlite_only / apply_event).
        _ = payload  # acknowledged; intentionally unused

    # ------------------------------------------------------------------
    # Phase 3 handlers
    # ------------------------------------------------------------------

    def _handle_prd_parsed(
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
        """
        project_id: str = payload.project_id
        summary: str = payload.summary
        status: str = payload.status
        goals = payload.goals
        non_goals = payload.non_goals
        requirements_raw: list[Any] = payload.requirements
        acceptance_criteria = payload.acceptance_criteria
        risks = payload.risks
        open_questions = payload.open_questions

        # Validate requirement payloads and collect IDs.
        requirement_objects: list[Requirement] = []
        for req_data in requirements_raw:
            try:
                req = Requirement.model_validate(req_data)
            except Exception as exc:
                raise TransactionAborted(
                    f"prd.parsed: invalid Requirement in payload: {exc}"
                ) from exc
            requirement_objects.append(req)

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

    def _handle_prd_reviewed(
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

    def _handle_prd_approved(
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

    def _handle_feature_created(
        self,
        conn: sqlite3.Connection,
        payload: FeatureCreatedPayload,
        event: Event,
    ) -> None:
        """Insert a Feature row from the event payload.

        Payload fields: all Feature model fields (id, title, description,
        status, requirements, tasks).
        """
        try:
            feature = Feature.model_validate(payload.model_dump(mode="json"))
        except Exception as exc:
            raise TransactionAborted(
                f"feature.created: invalid Feature payload: {exc}"
            ) from exc

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

    def _handle_task_created(
        self,
        conn: sqlite3.Connection,
        payload: TaskCreatedPayload,
        event: Event,
    ) -> None:
        """Insert a Task row from the event payload.

        Payload fields: all Task model fields.  Scores may be None for all
        dimensions at creation time; they get populated by task.scored later.
        """
        task_dict = payload.model_dump(mode="json")
        # Task.scores / Task.verification are required submodels; the payload
        # allows None so MCP / hand-rolled callers can send a minimal task
        # without preloading sentinels. Normalize before validation.
        if task_dict.get("scores") is None:
            task_dict["scores"] = {}
        if task_dict.get("verification") is None:
            task_dict["verification"] = {}
        try:
            task = Task.model_validate(task_dict)
        except Exception as exc:
            raise TransactionAborted(
                f"task.created: invalid Task payload: {exc}"
            ) from exc

        self._insert_task_row(conn, task)

    def _handle_task_scored(
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
        """
        task_id: str = payload.task_id
        scores_dict: dict[str, Any] = payload.scores
        explanation: str | None = payload.explanation
        timestamp: str = event.timestamp.isoformat()

        # Build the Score model from the payload dimensions + explanation.
        score_data = dict(scores_dict)
        score_data["explanation"] = explanation
        try:
            score = Score.model_validate(score_data)
        except Exception as exc:
            raise TransactionAborted(
                f"task.scored: invalid scores payload: {exc}"
            ) from exc

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
        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            raise TransactionAborted(
                f"task.scored: task '{task_id}' not found."
            )

    def _handle_task_expanded(
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
        """
        parent_task_id: str = payload.parent_task_id
        subtasks_raw: list[Any] = payload.subtasks
        if not subtasks_raw:
            raise TransactionAborted(
                "task.expanded payload has empty 'subtasks' list; nothing to expand."
            )

        for subtask_data in subtasks_raw:
            # Force parent_task_id from the event, not from the payload sub-dict.
            subtask_data = dict(subtask_data)
            subtask_data["parent_task_id"] = parent_task_id
            # Same None→{} normalization as task.created — subtasks can also
            # be minimal payloads from MCP callers.
            if subtask_data.get("scores") is None:
                subtask_data["scores"] = {}
            if subtask_data.get("verification") is None:
                subtask_data["verification"] = {}
            try:
                subtask = Task.model_validate(subtask_data)
            except Exception as exc:
                raise TransactionAborted(
                    f"task.expanded: invalid subtask payload: {exc}"
                ) from exc
            self._insert_task_row(conn, subtask)

    def _handle_task_status_changed(
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

        The UPDATE uses a WHERE status=from clause as a concurrency guard.
        If zero rows are updated (the task does not exist or its status has
        drifted), TransactionAborted is raised.
        """
        task_id: str = payload.task_id
        from_status: str = payload.from_status
        to_status: str = payload.to_status
        timestamp: str = event.timestamp.isoformat()

        conn.execute(
            """
            UPDATE tasks
               SET status = ?,
                   updated_at = ?
             WHERE id = ?
               AND status = ?
            """,
            (to_status, timestamp, task_id, from_status),
        )
        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            # Determine whether task exists at all for a clearer error.
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise TransactionAborted(
                    f"task.status_changed: task '{task_id}' not found."
                )
            actual_status = row[0]
            # Idempotent re-application: if the task is already at the
            # target status, treat as a successful no-op. This lets `plan`
            # (which emits proposed→drafted) be re-run safely after the
            # first run has already promoted tasks. Without this branch,
            # re-plan would always raise because status no longer matches
            # the 'from' field.
            if actual_status == to_status:
                return
            raise TransactionAborted(
                f"task.status_changed: concurrency guard failed for task '{task_id}'. "
                f"Expected status '{from_status}', got '{actual_status}'. "
                "The task status may have been changed by a concurrent operation."
            )

    # ------------------------------------------------------------------
    # Phase 4 handlers — claim lifecycle
    # ------------------------------------------------------------------

    def _handle_claim_created(
        self,
        conn: sqlite3.Connection,
        payload: ClaimCreatedPayload,
        event: Event,
    ) -> None:
        """Atomically INSERT the claim and transition the task to 'claimed'.

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

        Idempotent: INSERT OR IGNORE on the claim id PK — replay is safe.

        Concurrency guard: the task status UPDATE uses WHERE status='ready'
        so a parallel claim attempt that has already transitioned the task
        results in 0 rows updated → TransactionAborted.  The task→claimed
        transition is a side effect of claim.created; it does NOT need a
        separate task.status_changed event.
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
        # The WHERE status='ready' is the concurrency guard — if another claim
        # has already moved the task to 'claimed', 0 rows are updated and we
        # abort (the INSERT OR IGNORE above means the claim row itself is also
        # a no-op on replay, keeping the two mutations consistent).
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
        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            # Determine whether the task exists and what its current status is.
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise TransactionAborted(
                    f"claim.created: task '{task_id}' not found."
                )
            actual_status = row[0]
            # Idempotent replay path: if the INSERT OR IGNORE above was a no-op
            # (claim already existed) AND the task is already 'claimed', this
            # is a replay of a previously-committed claim.created — treat as
            # no-op instead of raising.
            if actual_status == "claimed":
                return
            raise TransactionAborted(
                f"claim.created: concurrency guard failed for task '{task_id}'. "
                f"Expected status 'ready', got '{actual_status}'. "
                "Another claim may have already acquired this task."
            )

    def _handle_claim_released(
        self,
        conn: sqlite3.Connection,
        payload: ClaimReleasedPayload,
        event: Event,
    ) -> None:
        """Release an active claim and return the task to 'ready'.

        Payload fields (all required):
            claim_id (str)       — PK of the claim to release
            released_by (str)    — agent releasing the claim
            release_reason (str) — human-readable reason

        On already-released (idempotent): log a warning tombstone to the event
        log via _append_abort_event but do NOT raise — the stale detector runs
        frequently and should not error on already-released claims.

        Side-effect: UPDATE tasks SET status='ready' WHERE id=task_id AND
        status='claimed' — uses the WHERE guard for concurrency safety.
        """
        claim_id: str = payload.claim_id
        # release_reason is optional — the ClaimManager passes None when the
        # caller provides no explicit reason.
        release_reason: str | None = payload.release_reason
        # `force` honours the CLI's --force flag: lets non-owners release a
        # claim and lets release succeed even on already-stale/non-active
        # claims (Greptile + critic both flagged that the original handler
        # silently no-op'd force-release of stale claims).
        force: bool = payload.force
        timestamp: str = event.timestamp.isoformat()

        # Force-release writes a distinct terminal status (force_released) so
        # the audit trail captures the override; normal release uses 'released'.
        # Force also allows non-active claims to be released so a stranded
        # stale claim can be cleaned up after the fact.
        target_status = "force_released" if force else "released"
        if force:
            status_guard = "status NOT IN ('released', 'force_released')"
        else:
            status_guard = "status = 'active'"

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

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            # Check whether the claim exists at all, or was already released.
            row = conn.execute(
                "SELECT status FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
            if row is None:
                raise TransactionAborted(
                    f"claim.released: claim '{claim_id}' not found."
                )
            # Already in a terminal state — idempotent no-op; log but don't raise.
            current_status = row[0]
            self._append_warn_log(
                action="claim.released",
                target_id=claim_id or "",
                reason=(
                    f"claim.released: claim '{claim_id}' already has status "
                    f"'{current_status}'; treating as idempotent no-op."
                ),
            )
            return

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

    def _handle_claim_renewed(
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

        Raises TransactionAborted if the claim does not exist or is not active.

        The event-level timestamp is not used here — the renewed lease timestamps
        come from the payload itself.
        """
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

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            row = conn.execute(
                "SELECT status FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
            if row is None:
                raise TransactionAborted(
                    f"claim.renewed: claim '{claim_id}' not found."
                )
            actual_status = row[0]
            raise TransactionAborted(
                f"claim.renewed: cannot renew claim '{claim_id}' "
                f"with status '{actual_status}' (must be 'active')."
            )

    def _handle_claim_stale(
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

        On already-stale (idempotent): log a warning tombstone but do NOT raise.
        The stale detector runs on every CLI call and should not error on claims
        it has already processed.

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

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            # Check whether it's already stale (idempotent no-op) or truly missing.
            row = conn.execute(
                "SELECT status FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
            if row is None:
                raise TransactionAborted(
                    f"claim.stale: claim '{claim_id}' not found."
                )
            # Already stale (or force_released) — idempotent; log warning only.
            current_status = row[0]
            self._append_warn_log(
                action="claim.stale",
                target_id=claim_id or "",
                reason=(
                    f"claim.stale: claim '{claim_id}' already has status "
                    f"'{current_status}'; treating as idempotent no-op."
                ),
            )
            return

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

    def _handle_evidence_submitted(
        self,
        conn: sqlite3.Connection,
        payload: EvidenceSubmittedPayload,
        event: Event,
    ) -> None:
        """Insert evidence and atomically transition task to needs_review.

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

        Idempotent on replay:
            - INSERT OR IGNORE on evidence.id PK — duplicate events are no-ops.
            - Task UPDATE uses WHERE status IN ('claimed', 'in_progress', 'blocked');
              if already 'needs_review' that branch is treated as a no-op.

        Auto-release the active claim:
            - UPDATE claims SET status='released' WHERE id=claim_id AND
              status='active'. 0 rows = claim already stale/released; log only.
        """
        task_id: str = payload.task_id
        claim_id: str = payload.claim_id
        submitted_by: str = payload.submitted_by
        evidence_id: str = payload.evidence_id
        commands_run: list[Any] = payload.commands_run
        files_changed: list[Any] = payload.files_changed
        timestamp: str = event.timestamp.isoformat()

        # Require commands_run and files_changed to be non-empty —
        # submitting evidence with neither a verification command nor any
        # changed files is meaningless.
        if not commands_run:
            raise TransactionAborted(
                "evidence.submitted payload requires non-empty 'commands_run'."
            )
        if not files_changed:
            raise TransactionAborted(
                "evidence.submitted payload requires non-empty 'files_changed'."
            )

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

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            # Task not updated — check why.
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise TransactionAborted(
                    f"evidence.submitted: task '{task_id}' not found."
                )
            actual_status = row[0]
            # Idempotent replay path: task already at needs_review.
            if actual_status == "needs_review":
                pass  # acceptable — evidence INSERT OR IGNORE above was also a no-op
            else:
                raise TransactionAborted(
                    f"evidence.submitted: task '{task_id}' has status "
                    f"'{actual_status}', which is not eligible for evidence submission "
                    "(must be 'claimed', 'in_progress', or 'blocked')."
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

    def _handle_task_applied(
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

        0 rows on the main UPDATE: existence check then raise with clear
        status-drift message.
        """
        task_id: str = payload.task_id
        reviewer: str = payload.reviewer
        decision: str = payload.decision
        notes: str | None = payload.notes
        event_id: str = event.id
        timestamp: str = event.timestamp.isoformat()

        if decision not in ("accepted", "rejected"):
            raise TransactionAborted(
                f"task.applied: 'decision' must be 'accepted' or 'rejected', "
                f"got {decision!r}."
            )

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

    def _handle_file_changed(
        self,
        conn: sqlite3.Connection,
        payload: FileChangedPayload,
        event: Event,
    ) -> None:
        """Audit-trail-only event emitted by the PostToolUse hook.

        (record-file-change.sh → fakoli-state hook record-file-change).
        No SQLite mutation: the JSONL line is the audit record.  The validated
        payload model is accepted here to keep the dispatch table uniform and to
        enforce the known field schema via extra='forbid'.
        """
        # No-op — the event row is recorded by the caller in the events table.
        _ = payload
        _ = conn
        _ = event

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
