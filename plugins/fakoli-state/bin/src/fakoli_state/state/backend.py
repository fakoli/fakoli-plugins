"""Storage backend protocol for fakoli-state.

Defines the Backend Protocol that all storage implementations must satisfy,
plus the exception hierarchy for backend failures.

The SQLite implementation lives in state/sqlite.py (Wave 2).
This file ships the contract only — no I/O, no imports of concrete modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fakoli_state.state.models import PRD, Claim, Event, Project, Task


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

    def apply_event(self, event: Event) -> None:
        """Atomically: append event to JSONL, mutate SQLite state. Single transaction.

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

    def list_active_claims(self) -> list[Claim]:
        """Return all claims with a non-expired lease and non-terminal status."""
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


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class BackendError(Exception):
    """Base for backend failures (concurrency, schema mismatch, etc.)."""


class TransactionAborted(BackendError):
    """The event was logged as error.transaction_aborted; state is unchanged."""


class StateLocked(BackendError):
    """SQLite busy_timeout exceeded; another writer held the lock too long."""


class SchemaMismatch(BackendError):
    """DB schema version != code expected version."""
