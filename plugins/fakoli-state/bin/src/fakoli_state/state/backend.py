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

    def initialize(self, *, db_path: str, events_path: str) -> None:
        """Create schema if not present. Idempotent.

        Args:
            db_path: Absolute path to the SQLite database file.
            events_path: Absolute path to the JSONL event log.
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
