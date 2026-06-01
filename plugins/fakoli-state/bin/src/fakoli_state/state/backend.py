"""Storage backend protocol for fakoli-state.

Defines the Backend Protocol that all storage implementations must satisfy,
plus the exception hierarchy for backend failures.

The SQLite implementation lives in state/sqlite.py (Wave 2).
This file ships the contract only — no I/O, no imports of concrete modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fakoli_state.state.models import (
        PRD,
        Claim,
        Event,
        Evidence,
        Feature,
        Project,
        Requirement,
        Review,
        SyncMapping,
        Task,
    )

# ---------------------------------------------------------------------------
# Sentinel for race-free event ID assignment
# ---------------------------------------------------------------------------

#: Pass as event.id to have the Backend assign a sequential ID inside the
#: BEGIN IMMEDIATE lock, eliminating the read-before-lock race flagged by
#: Critic-3 on PR #41.  The returned Event from apply_event() carries the
#: assigned ID.  Use a real E%06d ID only on the replay path (where the
#: original ID from JSONL must be preserved).
#:
#: Trade-off: for PENDING events the JSONL write moves AFTER the SQLite
#: COMMIT (the ID is not known until inside the lock).  This weakens the
#: "log-before-mutation" crash-recovery property for the live path, but
#: eliminates the silent-drop race that is strictly worse.  The replay path
#: uses non-PENDING IDs (event.id is a real ID from JSONL) and is unchanged.
PENDING_EVENT_ID = "PENDING"


class Backend(Protocol):
    """Storage backend interface. SQLite is the v0 impl; in-memory + Postgres are future.

    All mutating methods are expected to be atomic: the event is appended to the
    JSONL audit log and the SQLite state is updated in a single transaction.
    Replay from the event log must reproduce the exact same SQLite state.
    """

    def initialize(self) -> None:
        """Open the backend, create schema if not present, validate version.

        Idempotent — safe to call repeatedly. Paths (db_path, events_path) are
        supplied to the concrete backend via its constructor; this method takes
        no arguments so impls with different connection models (in-memory,
        connection pool, etc.) can satisfy the Protocol without a path API.

        Raises:
            SchemaMismatch: If an existing DB has a user_version that does not
                match the version this code expects.
        """
        ...

    def apply_event(self, event: Event) -> Event:
        """Atomically: append event to JSONL, mutate SQLite state. Single transaction.

        If event.id == PENDING_EVENT_ID the Backend assigns a fresh sequential
        ID inside the BEGIN IMMEDIATE lock, eliminating the read-before-lock race
        flagged by Critic-3 on PR #41.  The materialized event (with assigned ID)
        is returned so callers can record it.

        If event.id is a real ID (e.g. from replay), it is honored as-is.

        Trade-off: for PENDING events the JSONL write moves AFTER the SQLite
        COMMIT (the ID is not known until inside the lock).  This weakens the
        "log-before-mutation" crash-recovery property for the live path, but
        eliminates the silent-drop race that is strictly worse.  The replay path
        uses non-PENDING IDs (event.id is a real ID from JSONL) and is unchanged.

        Raises:
            TransactionAborted: If the mutation could not complete. The event is
                logged with action ``error.transaction_aborted``; state is unchanged.
            StateLocked: If SQLite busy_timeout was exceeded.
            SchemaMismatch: If the DB schema version does not match the expected version.
        """
        ...

    def get_task(self, task_id: str) -> Task | None:
        """Return the Task with the given ID, or None if not found."""
        ...

    def list_tasks(
        self,
        *,
        status: str | None = None,
        feature_id: str | None = None,
    ) -> list[Task]:
        """Return tasks, optionally filtered by status and/or feature."""
        ...

    def get_claim(self, claim_id: str) -> Claim | None:
        """Return the Claim with the given ID, or None if not found."""
        ...

    def get_feature(self, feature_id: str) -> Feature | None:
        """Return the Feature with the given ID, or None if not found."""
        ...

    def list_features(self) -> list[Feature]:
        """Return all Feature rows. Used by `plan` for orphan detection
        on re-parse (v1.15.0): the new parse's feature set is diffed
        against this to compute which features to delete."""
        ...

    def get_latest_evidence(self, task_id: str) -> Evidence | None:
        """Return the most recently submitted Evidence for task_id, or None.
        Used by `apply` to display the evidence summary."""
        ...

    def list_active_claims(self) -> list[Claim]:
        """Return all claims with a non-expired lease and non-terminal status."""
        ...

    def list_claims(self) -> list[Claim]:
        """Return ALL claims regardless of status, sorted by id ASC.

        Used by serialize_state and other snapshot paths that need the full
        claim history — not just the currently active subset returned by
        list_active_claims().  Includes active, released, stale, and
        force_released claims.
        """
        ...

    def list_reviews(self) -> list[Review]:
        """Return all Review rows sorted by id ASC.

        Used by serialize_state to capture the full review history.
        Includes approval reviews inserted by prd.approved as well as task
        reviews inserted by task.applied.
        """
        ...

    def list_evidence(self) -> list[Evidence]:
        """Return all Evidence rows sorted by id ASC.

        Used by serialize_state to capture every evidence submission for
        every task.  The ordering by id (E%06d-style primary key) guarantees
        deterministic output across runs.
        """
        ...

    def list_requirements(self) -> list[Requirement]:
        """Return all Requirement rows sorted by id ASC.

        Used by serialize_state to capture the full requirement set written
        by prd.parsed.  The id-based ordering is deterministic because
        requirement IDs are assigned at parse time and never mutate.
        """
        ...

    def list_events(
        self,
        *,
        target_id: str,
        target_kind: str | None = None,
        limit: int = 10,
    ) -> list[tuple[str, str]]:
        """Return recent events for the given target as (action, timestamp_iso) tuples,
        most-recent first. Used by `show` to surface task history."""
        ...

    def get_prd(self) -> PRD | None:
        """Return the current PRD, or None if not yet parsed."""
        ...

    def get_project(self) -> Project | None:
        """Return the Project record, or None if not initialised."""
        ...

    def replay_from_empty(self, events_path: str) -> None:
        """Reconstruct state.db from events.jsonl. The audit-guarantee primitive.

        Drops and recreates all tables, then replays every non-error event in
        order. After replay the DB is byte-for-byte equivalent to the state
        produced by the original sequence of apply_event() calls.

        Args:
            events_path: Absolute path to the JSONL event log to replay.
        """
        ...

    def close(self) -> None:
        """Release any held resources (connections, file handles)."""
        ...

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
        mapping wins is ASC-sort-position-dependent and brittle. Callers
        that need to enumerate every mapping for a task should use
        ``list_sync_mappings`` and filter by ``task_id`` instead.
        """
        raise NotImplementedError(
            "Backend.get_sync_mapping() must be implemented by the concrete backend."
        )

    def list_sync_mappings(
        self,
        external_system: str | None = None,
    ) -> list[SyncMapping]:
        """Return SyncMapping rows, optionally filtered by external_system."""
        raise NotImplementedError(
            "Backend.list_sync_mappings() must be implemented by the concrete backend."
        )

    def apply_sync_mapping(
        self,
        mapping: SyncMapping,
        *,
        actor: str = "system",
    ) -> Event:
        """Convenience wrapper that emits a sync_mapping.upserted event.

        Builds an Event with PENDING_EVENT_ID, calls apply_event(), and
        returns the materialized Event (with the backend-assigned ID) so the
        caller can record it. The underlying SQLite mutation is the upsert
        described by ``_handle_sync_mapping_upserted``. ``actor`` is recorded
        in the event audit row; defaults to ``"system"``.
        """
        raise NotImplementedError(
            "Backend.apply_sync_mapping() must be implemented by the concrete backend."
        )

    def next_event_id(self) -> str:
        """Return a hint of the next sequential event ID in canonical E%06d format.

        Subject to races — do not use this to pre-assign IDs for new events.
        Use PENDING_EVENT_ID + apply_event() for race-free ID assignment instead.
        Kept for callers that need to preview the upcoming ID (e.g. tests that
        check format) or for legacy compatibility.

        Single source of truth for event IDs so the CLI and ClaimManager
        cannot drift into incompatible schemes (the original Phase 4 bug:
        CLI used E000003-style sequential, ClaimManager used 20-digit
        microsecond IDs; once both landed in the same events table the
        MAX-based sequential generator silently produced 20-digit IDs).
        """
        ...


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class BackendError(Exception):
    """Base for backend failures (concurrency, schema mismatch, etc.)."""


class TransactionAborted(BackendError):
    """The event was logged as error.transaction_aborted; state is unchanged."""


class StateLocked(BackendError):
    """SQLite busy_timeout exceeded; another writer held the lock too long."""


class EventRejected(BackendError):
    """An ``append`` was refused before anything was logged.

    Raised by a ``_check_<action>`` on an illegal transition or a bad payload
    (e.g. claiming an already-claimed task, evidence missing required fields).
    This is a *normal, expected* control-flow signal on the write path — not an
    infrastructure failure. Nothing is written to ``events.jsonl``; the rejection
    is recorded in the sibling ``audit.jsonl`` and re-raised to the caller.

    Distinct from :class:`TransactionAborted`, which (under the SL1-RR-1
    write-path rework) is narrowed to mean only an unexpected infrastructure
    failure *after* the log append.
    """


class IdempotentNoOp(BackendError):
    """An ``append`` request that is legal but already satisfied — a no-op.

    Raised by a ``_check_<action>`` when the requested mutation has already
    happened (e.g. releasing an already-released claim). This is *not* an error:
    ``append`` catches it internally, records an ``idempotent_no_op`` line in
    ``audit.jsonl``, and returns ``None`` without logging a canonical event or
    mutating state. It is defined as an exception purely so a ``_check_*`` can
    signal this third outcome (alongside "proceed" and ``EventRejected``) via
    control flow; callers of ``append`` never see it.
    """


class SchemaMismatch(BackendError):
    """DB schema version != code expected version."""
