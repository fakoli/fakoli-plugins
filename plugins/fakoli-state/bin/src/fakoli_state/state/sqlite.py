"""SQLite backend implementing the Backend protocol.

WAL mode + JSONL audit log.  The replay guarantee:
    replay_from_empty(events.jsonl) → state.db identical to original run.

Events are serialised to JSONL *before* the SQLite mutation so that even a
process crash after the JSONL write but before the COMMIT leaves the log
in a state that can be replayed cleanly.

Phase 2 note: only 'project.created' and 'state.initialized' are routed;
all other actions raise NotImplementedError with a clear message.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import TYPE_CHECKING, Any

from fakoli_state.state.backend import (
    BackendError,  # noqa: F401
    SchemaMismatch,
    StateLocked,
    TransactionAborted,
)
from fakoli_state.state.models import PRD, Claim, ClaimStatus, Event, Project, Task
from fakoli_state.state.schema import DDL, SCHEMA_VERSION

if TYPE_CHECKING:
    from fakoli_state.clock import Clock


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

    # ------------------------------------------------------------------
    # Core mutation
    # ------------------------------------------------------------------

    def apply_event(self, event: Event) -> None:
        """Atomically append event to JSONL and mutate SQLite state.

        Order of operations
        -------------------
        1. Serialise event to JSON.
        2. Append to events.jsonl (fsync is not forced — OS buffer is enough for
           Phase 2; production hardening would add fdatasync).
        3. BEGIN IMMEDIATE on SQLite.
        4. Dispatch to _apply_mutation().
        5. INSERT the event row into the events table.
        6. COMMIT.

        On any failure: ROLLBACK, append an error.transaction_aborted event to
        JSONL, and re-raise as TransactionAborted.
        """
        conn = self._require_conn()
        event_line = event.model_dump_json() + "\n"

        # --- Phase 1: write to JSONL BEFORE SQLite mutation ---
        try:
            with open(self._events_path, "a", encoding="utf-8") as fh:
                fh.write(event_line)
        except OSError as exc:
            raise TransactionAborted(
                f"Failed to write event {event.id!r} to JSONL log: {exc}"
            ) from exc

        # --- Phase 2: SQLite transaction ---
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

                # Skip abort tombstones.
                if raw.get("action") == "error.transaction_aborted":
                    continue

                event = Event.model_validate(raw)
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

    def _apply_mutation(self, conn: sqlite3.Connection, event: Event) -> None:
        """Dispatch event.action to the appropriate mutation handler.

        Phase 2 only handles 'project.created' and 'state.initialized'.
        All other actions raise NotImplementedError.
        """
        action = event.action
        payload = event.payload_json

        if action == "project.created":
            self._handle_project_created(conn, payload)
        elif action == "state.initialized":
            self._handle_state_initialized(conn, payload)
        else:
            raise NotImplementedError(
                f"Event action {action!r} is not yet supported in Phase 2. "
                "This action will be implemented in a later phase."
            )

    def _handle_project_created(
        self, conn: sqlite3.Connection, payload: dict[str, Any]
    ) -> None:
        """Insert or replace the project row from the event payload."""
        project = Project.model_validate(payload)
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
        self, conn: sqlite3.Connection, payload: dict[str, Any]
    ) -> None:
        """Handle the state.initialized event.

        This event signals that the state engine has been set up.  In Phase 2 it
        is a no-op beyond being recorded in the events table; future phases may
        use the payload to seed configuration.
        """
        # Nothing to mutate for Phase 2 — the event row insertion is handled
        # by the caller (_apply_event_sqlite_only / apply_event).
        _ = payload  # acknowledged; intentionally unused

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
        abort_data = {
            "id": failed_event.id,
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
        except OSError:
            # If we can't write the abort tombstone, swallow the error — the
            # caller already has the TransactionAborted exception.
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
