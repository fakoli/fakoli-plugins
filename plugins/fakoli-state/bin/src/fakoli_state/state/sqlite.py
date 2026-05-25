"""SQLite backend implementing the Backend protocol.

WAL mode + JSONL audit log.  The replay guarantee:
    replay_from_empty(events.jsonl) → state.db identical to original run.

Events are serialised to JSONL *before* the SQLite mutation so that even a
process crash after the JSONL write but before the COMMIT leaves the log
in a state that can be replayed cleanly.

Phase 2 note: only 'project.created' and 'state.initialized' are routed;
Phase 3 extends routing with: prd.parsed, prd.reviewed, prd.approved,
feature.created, task.created, task.scored, task.expanded, task.status_changed.
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

        Phase 2 handles 'project.created' and 'state.initialized'.
        Phase 3 adds: prd.parsed, prd.reviewed, prd.approved, feature.created,
        task.created, task.scored, task.expanded, task.status_changed.
        """
        action = event.action
        payload = event.payload_json

        if action == "project.created":
            self._handle_project_created(conn, payload)
        elif action == "state.initialized":
            self._handle_state_initialized(conn, payload)
        elif action == "prd.parsed":
            self._handle_prd_parsed(conn, payload)
        elif action == "prd.reviewed":
            self._handle_prd_reviewed(conn, payload, event.id, event.timestamp.isoformat())
        elif action == "prd.approved":
            self._handle_prd_approved(conn, payload, event.id, event.timestamp.isoformat())
        elif action == "feature.created":
            self._handle_feature_created(conn, payload)
        elif action == "task.created":
            self._handle_task_created(conn, payload)
        elif action == "task.scored":
            self._handle_task_scored(conn, payload, event.timestamp.isoformat())
        elif action == "task.expanded":
            self._handle_task_expanded(conn, payload)
        elif action == "task.status_changed":
            self._handle_task_status_changed(conn, payload, event.timestamp.isoformat())
        else:
            raise NotImplementedError(
                f"Event action {action!r} is not yet supported. "
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

    # ------------------------------------------------------------------
    # Phase 3 handlers
    # ------------------------------------------------------------------

    def _handle_prd_parsed(
        self, conn: sqlite3.Connection, payload: dict[str, Any]
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
        project_id: str | None = payload.get("project_id")
        if not project_id:
            raise TransactionAborted(
                "prd.parsed payload missing required field 'project_id'."
            )
        summary: str = payload.get("summary", "")
        status: str = payload.get("status", "draft")
        goals = payload.get("goals", [])
        non_goals = payload.get("non_goals", [])
        requirements_raw: list[dict[str, Any]] = payload.get("requirements", [])
        acceptance_criteria = payload.get("acceptance_criteria", [])
        risks = payload.get("risks", [])
        open_questions = payload.get("open_questions", [])

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
        payload: dict[str, Any],
        event_id: str,
        timestamp: str,
    ) -> None:
        """Mark PRD as reviewed and insert a Review row.

        Payload fields:
            reviewer (str) — required
            notes (str | None) — optional

        The Review row ID is derived deterministically from the event_id so
        that replay produces byte-for-byte identical rows.
        """
        reviewer: str | None = payload.get("reviewer")
        if not reviewer:
            raise TransactionAborted(
                "prd.reviewed payload missing required field 'reviewer'."
            )
        notes: str | None = payload.get("notes")

        conn.execute(
            """
            UPDATE prds
               SET status = 'reviewed',
                   last_reviewed_at = ?,
                   last_reviewed_by = ?
            """,
            (timestamp, reviewer),
        )

        # Derive a stable review ID from the event ID so replay is idempotent.
        review_id = f"RV-{event_id}"
        conn.execute(
            """
            INSERT OR REPLACE INTO reviews
                (id, target_kind, target_id, reviewed_by, decision, notes, created_at)
            VALUES
                (?, 'prd', 'prd', ?, 'approve', ?, ?)
            """,
            (review_id, reviewer, notes, timestamp),
        )

    def _handle_prd_approved(
        self,
        conn: sqlite3.Connection,
        payload: dict[str, Any],
        event_id: str,
        timestamp: str,
    ) -> None:
        """Mark PRD as approved and insert a Review row.

        Payload fields:
            approver (str) — required

        The Review row ID is derived deterministically from the event_id so
        that replay produces byte-for-byte identical rows.
        """
        approver: str | None = payload.get("approver")
        if not approver:
            raise TransactionAborted(
                "prd.approved payload missing required field 'approver'."
            )

        conn.execute(
            """
            UPDATE prds
               SET status = 'approved',
                   last_reviewed_at = ?,
                   last_reviewed_by = ?
            """,
            (timestamp, approver),
        )

        review_id = f"RV-{event_id}"
        conn.execute(
            """
            INSERT OR REPLACE INTO reviews
                (id, target_kind, target_id, reviewed_by, decision, notes, created_at)
            VALUES
                (?, 'prd', 'prd', ?, 'approve', NULL, ?)
            """,
            (review_id, approver, timestamp),
        )

    def _handle_feature_created(
        self, conn: sqlite3.Connection, payload: dict[str, Any]
    ) -> None:
        """Insert a Feature row from the event payload.

        Payload fields: all Feature model fields (id, title, description,
        status, requirements, tasks).
        """
        try:
            feature = Feature.model_validate(payload)
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
        self, conn: sqlite3.Connection, payload: dict[str, Any]
    ) -> None:
        """Insert a Task row from the event payload.

        Payload fields: all Task model fields.  Scores may be None for all
        dimensions at creation time; they get populated by task.scored later.
        """
        try:
            task = Task.model_validate(payload)
        except Exception as exc:
            raise TransactionAborted(
                f"task.created: invalid Task payload: {exc}"
            ) from exc

        self._insert_task_row(conn, task)

    def _handle_task_scored(
        self,
        conn: sqlite3.Connection,
        payload: dict[str, Any],
        timestamp: str,
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
        task_id: str | None = payload.get("task_id")
        if not task_id:
            raise TransactionAborted(
                "task.scored payload missing required field 'task_id'."
            )
        scores_dict: dict[str, Any] | None = payload.get("scores")
        if scores_dict is None:
            raise TransactionAborted(
                "task.scored payload missing required field 'scores'."
            )
        explanation: str | None = payload.get("explanation")

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
        self, conn: sqlite3.Connection, payload: dict[str, Any]
    ) -> None:
        """Insert subtask rows derived from expanding a parent task.

        Payload fields:
            parent_task_id (str) — required; must exist in tasks table
            subtasks (list[dict]) — list of Task payloads; each will be
                                    inserted with parent_task_id set

        The parent task's status is NOT changed here; the subtask rows
        themselves signal expansion (parent_task_id IS NOT NULL).
        """
        parent_task_id: str | None = payload.get("parent_task_id")
        if not parent_task_id:
            raise TransactionAborted(
                "task.expanded payload missing required field 'parent_task_id'."
            )
        subtasks_raw: list[dict[str, Any]] = payload.get("subtasks", [])
        if not subtasks_raw:
            raise TransactionAborted(
                "task.expanded payload has empty 'subtasks' list; nothing to expand."
            )

        for subtask_data in subtasks_raw:
            # Force parent_task_id from the event, not from the payload sub-dict.
            subtask_data = dict(subtask_data)
            subtask_data["parent_task_id"] = parent_task_id
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
        payload: dict[str, Any],
        timestamp: str,
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
        task_id: str | None = payload.get("task_id")
        from_status: str | None = payload.get("from")
        to_status: str | None = payload.get("to")

        if not task_id:
            raise TransactionAborted(
                "task.status_changed payload missing required field 'task_id'."
            )
        if not from_status:
            raise TransactionAborted(
                "task.status_changed payload missing required field 'from'."
            )
        if not to_status:
            raise TransactionAborted(
                "task.status_changed payload missing required field 'to'."
            )

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
            raise TransactionAborted(
                f"task.status_changed: concurrency guard failed for task '{task_id}'. "
                f"Expected status '{from_status}', got '{actual_status}'. "
                "The task status may have been changed by a concurrent operation."
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
                status               = excluded.status,
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
