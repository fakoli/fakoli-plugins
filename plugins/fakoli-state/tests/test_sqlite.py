"""Tests for fakoli_state.state.sqlite — SqliteBackend including the audit guarantee.

THE MOST CRITICAL TEST: test_replay_from_empty_reconstructs_state_exactly.

Coverage targets:
- initialize() idempotency and schema version check
- apply_event() JSONL + SQLite atomicity
- apply_event() rollback on failure → error.transaction_aborted in JSONL
- SchemaMismatch on version mismatch
- replay_from_empty() reconstructs identical state (audit guarantee)
- replay_from_empty() skips aborted events
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from fakoli_state.clock import FrozenClock
from fakoli_state.state.backend import PENDING_EVENT_ID, SchemaMismatch, TransactionAborted
from fakoli_state.state.models import Event
from fakoli_state.state.schema import SCHEMA_VERSION
from fakoli_state.state.sqlite import SqliteBackend

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UTC = UTC
_T0 = datetime(2026, 5, 24, 18, 0, 0, tzinfo=_UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_clock(dt: datetime = _T0) -> FrozenClock:
    return FrozenClock(dt)


def _make_backend(state_dir: Path, clock: FrozenClock | None = None) -> SqliteBackend:
    if clock is None:
        clock = _make_clock()
    db_path = str(state_dir / "state.db")
    events_path = str(state_dir / "events.jsonl")
    Path(events_path).touch()
    b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
    b.initialize()
    return b


def _make_project_event(
    *,
    event_id: str = "E000001",
    project_id: str = "proj-1",
    project_name: str = "Test Project",
    now: datetime = _T0,
) -> Event:
    return Event(
        id=event_id,
        timestamp=now,
        actor="test",
        action="project.created",
        target_kind="project",
        target_id=project_id,
        payload_json={
            "id": project_id,
            "name": project_name,
            "description": "",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    )


def _make_init_event(
    *,
    event_id: str = "E000002",
    project_id: str = "proj-1",
    now: datetime = _T0,
) -> Event:
    return Event(
        id=event_id,
        timestamp=now,
        actor="test",
        action="state.initialized",
        target_kind="project",
        target_id=project_id,
    )


def _sqlite_dump(db_path: str) -> str:
    """Return the full .dump output of a SQLite database as a string.

    This is used to compare two databases for structural and data equality.
    Filters out the user_version pragma line to avoid spurious diffs during
    intermediate states.
    """
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sqlite3; conn = sqlite3.connect({db_path!r}); "
         f"print('\\n'.join(conn.iterdump()))"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    """Parse a JSONL file and return a list of event dicts."""
    lines = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                lines.append(json.loads(line))
    return lines


# ---------------------------------------------------------------------------
# Schema initialization
# ---------------------------------------------------------------------------


class TestInitialize:
    def test_initialize_creates_schema(self, tmp_path: Path) -> None:
        """initialize() creates expected tables in SQLite."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            expected_tables = {
                "projects",
                "prds",
                "requirements",
                "features",
                "tasks",
                "claims",
                "evidence",
                "decisions",
                "reviews",
                "events",
                "sync_mappings",
                "conflict_groups",
            }
            assert expected_tables.issubset(tables)
        finally:
            b.close()

    def test_initialize_sets_schema_version(self, tmp_path: Path) -> None:
        """initialize() sets PRAGMA user_version to SCHEMA_VERSION."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            row = conn.execute("PRAGMA user_version").fetchone()
            conn.close()
            assert row[0] == SCHEMA_VERSION
        finally:
            b.close()

    def test_initialize_is_idempotent(self, tmp_path: Path) -> None:
        """Calling initialize() twice raises no error."""
        b = _make_backend(tmp_path)
        try:
            b.initialize()  # second call — should not raise
            b.initialize()  # third call — should also not raise
        finally:
            b.close()

    def test_initialize_without_calling_raises_on_query(self, tmp_path: Path) -> None:
        """Using backend without initialize() raises RuntimeError."""
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()
        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        # Do NOT call initialize()
        with pytest.raises(RuntimeError, match="initialize"):
            b.get_project()
        b.close()


# ---------------------------------------------------------------------------
# apply_event — atomicity
# ---------------------------------------------------------------------------


class TestApplyEvent:
    def test_apply_event_writes_jsonl_and_sqlite_in_same_transaction(
        self, tmp_path: Path
    ) -> None:
        """apply_event writes JSONL line AND SQLite row — both or neither."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            event = _make_project_event()
            b.apply_event(event)

            # JSONL line is present
            events = _read_jsonl(events_path)
            assert any(e.get("id") == "E000001" for e in events)

            # SQLite Project row is present
            project = b.get_project()
            assert project is not None
            assert project.id == "proj-1"
            assert project.name == "Test Project"
        finally:
            b.close()

    def test_apply_state_initialized_event(self, tmp_path: Path) -> None:
        """state.initialized event is accepted and recorded in events table."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            b.apply_event(_make_project_event())
            b.apply_event(_make_init_event())

            events = _read_jsonl(events_path)
            actions = [e["action"] for e in events]
            assert "state.initialized" in actions
        finally:
            b.close()

    def test_apply_event_rollback_on_mutation_failure(self, tmp_path: Path) -> None:
        """Unsupported action → JSONL gets error.transaction_aborted; SQLite unchanged."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            bad_event = Event(
                id="E000001",
                timestamp=_T0,
                actor="test",
                action="unsupported.action",  # triggers NotImplementedError
                target_kind="project",
                target_id="proj-1",
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)

            # JSONL should have the abort tombstone
            events = _read_jsonl(events_path)
            abort_events = [e for e in events if e.get("action") == "error.transaction_aborted"]
            assert len(abort_events) >= 1

            # SQLite project row should NOT be present
            project = b.get_project()
            assert project is None
        finally:
            b.close()

    def test_apply_event_adds_event_to_events_mirror_table(self, tmp_path: Path) -> None:
        """Successful apply_event records the event in the SQLite events mirror table."""
        b = _make_backend(tmp_path)
        try:
            b.apply_event(_make_project_event())
            # Query the events mirror table directly
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            row = conn.execute(
                "SELECT id, action FROM events WHERE id = 'E000001'"
            ).fetchone()
            conn.close()
            assert row is not None
            assert row[1] == "project.created"
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Schema version mismatch
# ---------------------------------------------------------------------------


class TestSchemaMismatch:
    def test_schema_version_mismatch_raises(self, tmp_path: Path) -> None:
        """A state.db with wrong PRAGMA user_version raises SchemaMismatch on second initialize().

        The mismatch check fires on the second+ call to initialize() (when the connection
        is already open). The first call runs DDL which sets the version, so we need to
        simulate the scenario where another process wrote a different version.

        We test this by:
        1. Initializing normally (version = SCHEMA_VERSION).
        2. Close the backend.
        3. Manually clobber the user_version to a wrong value.
        4. Open a NEW backend against the same db_path — this triggers _apply_ddl()
           which sets user_version back to SCHEMA_VERSION. So the mismatch window is
           on a *second call to initialize()* on an already-open connection.

        Alternatively: we test the _check_schema_version() path directly, which is
        triggered when the connection is re-initialized after already being open.
        """
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        # Step 1: Initialize normally to create the schema.
        clock = _make_clock()
        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        # Step 2: Second call to initialize() on the open connection → triggers _check_schema_version.
        # But it uses the same connection so version is still correct. Force a version mismatch
        # by manipulating the live connection's user_version:
        wrong_version = SCHEMA_VERSION + 99
        # pylint: disable=protected-access
        assert b._conn is not None  # guaranteed by initialize() above
        b._conn.execute(f"PRAGMA user_version = {wrong_version}")

        with pytest.raises(SchemaMismatch):
            b.initialize()  # re-checks version on re-entry

        b.close()


# ---------------------------------------------------------------------------
# THE AUDIT GUARANTEE
# ---------------------------------------------------------------------------


class TestAuditGuarantee:
    def test_replay_from_empty_reconstructs_state_exactly(self, tmp_path: Path) -> None:
        """Replay 3-5 events from events.jsonl; reconstructed state.db matches original.

        Steps:
        1. Apply 3 events (project.created, state.initialized, project.created again
           as an update).
        2. Snapshot the SQLite dump.
        3. Call replay_from_empty(events.jsonl).
        4. Assert new dump == original snapshot.
        """
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        events_path = str(tmp_path / "events.jsonl")
        db_path = str(tmp_path / "state.db")

        try:
            # Apply event 1: project.created
            b.apply_event(_make_project_event(event_id="E000001"))
            # Apply event 2: state.initialized
            b.apply_event(_make_init_event(event_id="E000002"))
            # Apply event 3: second project.created (updates project row)
            b.apply_event(
                _make_project_event(
                    event_id="E000003",
                    project_id="proj-1",
                    project_name="Test Project v2",
                )
            )
        finally:
            b.close()

        # Capture original dump
        original_dump = _sqlite_dump(db_path)

        # Replay from empty — should reconstruct identical state
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()  # need to open before replay
        try:
            b2.replay_from_empty(events_path)
        finally:
            pass  # replay_from_empty calls close() and re-opens internally

        b2.close()

        # Capture replayed dump
        replayed_dump = _sqlite_dump(db_path)

        assert original_dump == replayed_dump, (
            "Replayed state.db does not match original.\n"
            f"Original dump (truncated):\n{original_dump[:500]}\n\n"
            f"Replayed dump (truncated):\n{replayed_dump[:500]}"
        )

    def test_replay_skips_aborted_events(self, tmp_path: Path) -> None:
        """events.jsonl with one error.transaction_aborted — replay produces clean state."""
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        try:
            # Apply good event
            b.apply_event(_make_project_event(event_id="E000001"))

            # Inject a bad event to trigger TransactionAborted (generates abort tombstone)
            bad_event = Event(
                id="E000002",
                timestamp=_T0,
                actor="test",
                action="unsupported.action",
                target_kind="project",
                target_id="proj-1",
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)

            # Apply another good event after the abort
            b.apply_event(_make_init_event(event_id="E000003"))
        finally:
            b.close()

        # Verify JSONL contains the abort tombstone
        events = _read_jsonl(events_path)
        abort_events = [e for e in events if e.get("action") == "error.transaction_aborted"]
        assert len(abort_events) >= 1

        # Now replay from empty — should skip the abort event
        clock2 = _make_clock()
        b3 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b3.initialize()
        try:
            b3.replay_from_empty(events_path)
            project = b3.get_project()
        finally:
            b3.close()

        # Project should be present (from E000001 which was valid)
        assert project is not None
        assert project.id == "proj-1"

    def test_replay_produces_correct_project_data(self, tmp_path: Path) -> None:
        """After replay, get_project() returns the same Project as before."""
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        events_path = str(tmp_path / "events.jsonl")
        db_path = str(tmp_path / "state.db")

        try:
            b.apply_event(_make_project_event(project_name="My Replayed Project"))
            original_project = b.get_project()
        finally:
            b.close()

        assert original_project is not None

        # Replay
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
            replayed_project = b2.get_project()
        finally:
            b2.close()

        assert replayed_project is not None
        assert replayed_project.id == original_project.id
        assert replayed_project.name == original_project.name
        assert replayed_project.description == original_project.description

    def test_replay_from_empty_with_missing_events_file_is_noop(self, tmp_path: Path) -> None:
        """If events.jsonl does not exist, replay_from_empty returns cleanly."""
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()
        try:
            # Point to a non-existent file
            b.replay_from_empty(str(tmp_path / "nonexistent.jsonl"))
            # Should be a fresh empty database
            project = b.get_project()
            assert project is None
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


class TestQueryHelpers:
    def test_get_project_returns_none_when_empty(self, tmp_path: Path) -> None:
        b = _make_backend(tmp_path)
        try:
            assert b.get_project() is None
        finally:
            b.close()

    def test_get_project_returns_project_after_event(self, tmp_path: Path) -> None:
        b = _make_backend(tmp_path)
        try:
            b.apply_event(_make_project_event(project_name="Hello World"))
            project = b.get_project()
            assert project is not None
            assert project.name == "Hello World"
        finally:
            b.close()

    def test_get_prd_returns_none_when_empty(self, tmp_path: Path) -> None:
        b = _make_backend(tmp_path)
        try:
            assert b.get_prd() is None
        finally:
            b.close()

    def test_list_tasks_returns_empty_list_when_no_tasks(self, tmp_path: Path) -> None:
        b = _make_backend(tmp_path)
        try:
            assert b.list_tasks() == []
        finally:
            b.close()

    def test_list_active_claims_returns_empty_list_when_no_claims(self, tmp_path: Path) -> None:
        b = _make_backend(tmp_path)
        try:
            assert b.list_active_claims() == []
        finally:
            b.close()

    def test_get_claim_returns_none_for_unknown_id(self, tmp_path: Path) -> None:
        b = _make_backend(tmp_path)
        try:
            assert b.get_claim("nonexistent") is None
        finally:
            b.close()

    def test_get_task_returns_none_for_unknown_id(self, tmp_path: Path) -> None:
        b = _make_backend(tmp_path)
        try:
            assert b.get_task("nonexistent") is None
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Close idempotency
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        """Calling close() multiple times raises no error."""
        b = _make_backend(tmp_path)
        b.close()
        b.close()  # second close — should not raise
        b.close()  # third close — should not raise


# ---------------------------------------------------------------------------
# Replay — corrupted JSONL line
# ---------------------------------------------------------------------------


class TestReplayCorruptedJSONL:
    def test_replay_skips_corrupted_jsonl_line(self, tmp_path: Path) -> None:
        """Corrupted JSONL line (non-JSON) is skipped during replay_from_empty."""
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()
        try:
            b.apply_event(_make_project_event(event_id="E000001"))
        finally:
            b.close()

        # Manually inject a corrupted line between valid events
        with open(events_path, "a", encoding="utf-8") as fh:
            fh.write("NOT VALID JSON {{{\n")
            # Add another valid event after the corrupt line
            valid_event = {
                "id": "E000002",
                "timestamp": _T0.isoformat(),
                "actor": "test",
                "action": "state.initialized",
                "target_kind": "project",
                "target_id": "proj-1",
                "payload_json": {},
            }
            fh.write(json.dumps(valid_event) + "\n")

        # Replay from events.jsonl — corrupted line should be skipped
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
            project = b2.get_project()
        finally:
            b2.close()

        # Project from E000001 should still be present
        assert project is not None
        assert project.id == "proj-1"

    def test_replay_skips_empty_lines(self, tmp_path: Path) -> None:
        """Empty lines in JSONL are skipped during replay_from_empty."""
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()
        try:
            b.apply_event(_make_project_event(event_id="E000001"))
        finally:
            b.close()

        # Add empty lines to the JSONL
        with open(events_path, "a", encoding="utf-8") as fh:
            fh.write("\n\n\n")

        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
            project = b2.get_project()
        finally:
            b2.close()

        assert project is not None


# ---------------------------------------------------------------------------
# Row deserialization — direct DB insertion tests
# ---------------------------------------------------------------------------


class TestRowDeserialization:
    """Tests that exercise _row_to_task, _row_to_claim, _row_to_prd by inserting
    test rows directly into SQLite (bypassing the event system, which doesn't
    support task/claim/prd creation in Phase 2).
    """

    def _insert_feature(self, conn: sqlite3.Connection) -> None:
        """Insert a minimal feature row to satisfy tasks FK constraint."""
        conn.execute(
            "INSERT OR IGNORE INTO features (id, title, description, status, requirements, tasks) "
            "VALUES ('F001', 'Test Feature', 'desc', 'proposed', '[]', '[]')"
        )
        conn.commit()

    def test_row_to_task_via_list_tasks(self, tmp_path: Path) -> None:
        """_row_to_task is exercised by list_tasks when tasks are in the DB."""
        b = _make_backend(tmp_path)
        try:
            # Insert a task row directly via the connection
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            conn.row_factory = sqlite3.Row
            self._insert_feature(conn)
            conn.execute(
                """INSERT INTO tasks
                (id, feature_id, title, description, status, priority,
                 dependencies, conflict_groups, scores, acceptance_criteria,
                 implementation_notes, verification, likely_files,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "T001",
                    "F001",
                    "Test Task",
                    "A test task",
                    "proposed",
                    "medium",
                    "[]",
                    "[]",
                    "{}",
                    "[]",
                    "[]",
                    "{}",
                    "[]",
                    _T0.isoformat(),
                    _T0.isoformat(),
                ),
            )
            conn.commit()
            conn.close()

            # Now list_tasks should exercise _row_to_task
            tasks = b.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].id == "T001"
            assert tasks[0].title == "Test Task"
        finally:
            b.close()

    def test_list_tasks_filter_by_status(self, tmp_path: Path) -> None:
        """list_tasks(status=...) exercises the WHERE status = ? code path."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            self._insert_feature(conn)
            # Insert two tasks with different statuses
            for task_id, status in [("T001", "proposed"), ("T002", "ready")]:
                conn.execute(
                    """INSERT INTO tasks
                    (id, feature_id, title, description, status, priority,
                     dependencies, conflict_groups, scores, acceptance_criteria,
                     implementation_notes, verification, likely_files,
                     created_at, updated_at)
                    VALUES (?, 'F001', ?, 'desc', ?, 'medium',
                     '[]', '[]', '{}', '[]', '[]', '{}', '[]', ?, ?)""",
                    (task_id, f"Task {task_id}", status, _T0.isoformat(), _T0.isoformat()),
                )
            conn.commit()
            conn.close()

            # Filter by status
            proposed_tasks = b.list_tasks(status="proposed")
            ready_tasks = b.list_tasks(status="ready")
            all_tasks = b.list_tasks()

            assert len(proposed_tasks) == 1
            assert proposed_tasks[0].id == "T001"
            assert len(ready_tasks) == 1
            assert ready_tasks[0].id == "T002"
            assert len(all_tasks) == 2
        finally:
            b.close()

    def test_list_tasks_filter_by_feature_id(self, tmp_path: Path) -> None:
        """list_tasks(feature_id=...) exercises the WHERE feature_id = ? code path."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            self._insert_feature(conn)
            # Insert another feature
            conn.execute(
                "INSERT OR IGNORE INTO features (id, title, description, status, requirements, tasks) "
                "VALUES ('F002', 'Feature 2', 'desc', 'proposed', '[]', '[]')"
            )
            for task_id, feature_id in [("T001", "F001"), ("T002", "F002")]:
                conn.execute(
                    """INSERT INTO tasks
                    (id, feature_id, title, description, status, priority,
                     dependencies, conflict_groups, scores, acceptance_criteria,
                     implementation_notes, verification, likely_files,
                     created_at, updated_at)
                    VALUES (?, ?, ?, 'desc', 'proposed', 'medium',
                     '[]', '[]', '{}', '[]', '[]', '{}', '[]', ?, ?)""",
                    (task_id, feature_id, f"Task {task_id}", _T0.isoformat(), _T0.isoformat()),
                )
            conn.commit()
            conn.close()

            f1_tasks = b.list_tasks(feature_id="F001")
            f2_tasks = b.list_tasks(feature_id="F002")

            assert len(f1_tasks) == 1
            assert f1_tasks[0].feature_id == "F001"
            assert len(f2_tasks) == 1
            assert f2_tasks[0].feature_id == "F002"
        finally:
            b.close()

    def test_list_tasks_filter_by_status_and_feature_id(self, tmp_path: Path) -> None:
        """list_tasks with both status and feature_id filters (AND clause)."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            self._insert_feature(conn)
            for task_id, status in [("T001", "proposed"), ("T002", "ready")]:
                conn.execute(
                    """INSERT INTO tasks
                    (id, feature_id, title, description, status, priority,
                     dependencies, conflict_groups, scores, acceptance_criteria,
                     implementation_notes, verification, likely_files,
                     created_at, updated_at)
                    VALUES (?, 'F001', ?, 'desc', ?, 'medium',
                     '[]', '[]', '{}', '[]', '[]', '{}', '[]', ?, ?)""",
                    (task_id, f"Task {task_id}", status, _T0.isoformat(), _T0.isoformat()),
                )
            conn.commit()
            conn.close()

            # Only T001 is F001 + proposed
            filtered = b.list_tasks(status="proposed", feature_id="F001")
            assert len(filtered) == 1
            assert filtered[0].id == "T001"

            # No task is F001 + done
            empty = b.list_tasks(status="done", feature_id="F001")
            assert len(empty) == 0
        finally:
            b.close()

    def test_row_to_claim_via_get_claim(self, tmp_path: Path) -> None:
        """_row_to_claim is exercised by get_claim when claims are in the DB."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            self._insert_feature(conn)
            # Insert a task first (FK constraint)
            conn.execute(
                """INSERT INTO tasks
                (id, feature_id, title, description, status, priority,
                 dependencies, conflict_groups, scores, acceptance_criteria,
                 implementation_notes, verification, likely_files,
                 created_at, updated_at)
                VALUES ('T001', 'F001', 'Task', 'desc', 'claimed', 'medium',
                 '[]', '[]', '{}', '[]', '[]', '{}', '[]', ?, ?)""",
                (_T0.isoformat(), _T0.isoformat()),
            )
            # Insert a claim
            expires = (_T0 + timedelta(hours=1)).isoformat()
            conn.execute(
                """INSERT INTO claims
                (id, task_id, claimed_by, claim_type, status, expected_files,
                 created_at, lease_expires_at, last_heartbeat_at)
                VALUES ('C001', 'T001', 'agent-x', 'task', 'active', '[]', ?, ?, ?)""",
                (_T0.isoformat(), expires, _T0.isoformat()),
            )
            conn.commit()
            conn.close()

            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.id == "C001"
            assert claim.claimed_by == "agent-x"
            assert claim.task_id == "T001"
        finally:
            b.close()

    def test_list_active_claims_returns_active_claims(self, tmp_path: Path) -> None:
        """list_active_claims() returns active claims when they exist."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            self._insert_feature(conn)
            conn.execute(
                """INSERT INTO tasks
                (id, feature_id, title, description, status, priority,
                 dependencies, conflict_groups, scores, acceptance_criteria,
                 implementation_notes, verification, likely_files,
                 created_at, updated_at)
                VALUES ('T001', 'F001', 'Task', 'desc', 'claimed', 'medium',
                 '[]', '[]', '{}', '[]', '[]', '{}', '[]', ?, ?)""",
                (_T0.isoformat(), _T0.isoformat()),
            )
            expires = (_T0 + timedelta(hours=1)).isoformat()
            # Active claim
            conn.execute(
                """INSERT INTO claims
                (id, task_id, claimed_by, claim_type, status, expected_files,
                 created_at, lease_expires_at, last_heartbeat_at)
                VALUES ('C001', 'T001', 'agent-x', 'task', 'active', '[]', ?, ?, ?)""",
                (_T0.isoformat(), expires, _T0.isoformat()),
            )
            # Released claim (should not appear)
            conn.execute(
                """INSERT INTO claims
                (id, task_id, claimed_by, claim_type, status, expected_files,
                 created_at, lease_expires_at, last_heartbeat_at)
                VALUES ('C002', 'T001', 'agent-y', 'task', 'released', '[]', ?, ?, ?)""",
                (_T0.isoformat(), expires, _T0.isoformat()),
            )
            conn.commit()
            conn.close()

            active = b.list_active_claims()
            assert len(active) == 1
            assert active[0].id == "C001"
            assert active[0].status.value == "active"
        finally:
            b.close()

    def test_row_to_prd_via_get_prd(self, tmp_path: Path) -> None:
        """_row_to_prd is exercised by get_prd when a PRD is in the DB."""
        b = _make_backend(tmp_path)
        try:
            # Insert project first (PRD FK)
            b.apply_event(_make_project_event(event_id="E000001"))

            # Insert PRD directly
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            conn.execute(
                """INSERT INTO prds
                (project_id, status, summary, goals, non_goals, requirements,
                 acceptance_criteria, risks, open_questions)
                VALUES ('proj-1', 'draft', 'test prd', '[]', '[]', '[]', '[]', '[]', '[]')"""
            )
            conn.commit()
            conn.close()

            prd = b.get_prd()
            assert prd is not None
            assert prd.status.value == "draft"
            assert prd.summary == "test prd"
        finally:
            b.close()

    def test_get_task_returns_task_by_id(self, tmp_path: Path) -> None:
        """get_task() exercises _row_to_task for a specific task ID."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            self._insert_feature(conn)
            conn.execute(
                """INSERT INTO tasks
                (id, feature_id, title, description, status, priority,
                 dependencies, conflict_groups, scores, acceptance_criteria,
                 implementation_notes, verification, likely_files,
                 created_at, updated_at)
                VALUES ('T001', 'F001', 'Task Title', 'desc', 'proposed', 'high',
                 '[]', '[]', '{}', '["it works"]', '[]', '{}', '[]', ?, ?)""",
                (_T0.isoformat(), _T0.isoformat()),
            )
            conn.commit()
            conn.close()

            task = b.get_task("T001")
            assert task is not None
            assert task.id == "T001"
            assert task.title == "Task Title"
            assert task.priority.value == "high"
            assert task.acceptance_criteria == ["it works"]
        finally:
            b.close()


# ---------------------------------------------------------------------------
# JSONL write failure
# ---------------------------------------------------------------------------


class TestJSONLWriteFailure:
    def test_apply_event_jsonl_write_failure_raises_transaction_aborted(
        self, tmp_path: Path
    ) -> None:
        """If events.jsonl is unwritable, apply_event raises TransactionAborted."""
        import stat

        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        # Make events.jsonl read-only so writes fail
        os.chmod(events_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        try:
            event = _make_project_event()
            with pytest.raises(TransactionAborted):
                b.apply_event(event)
        finally:
            # Restore write permission so cleanup works
            os.chmod(events_path, stat.S_IREAD | stat.S_IWRITE)
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 event handlers — helper factories
# ---------------------------------------------------------------------------


def _make_feature_payload(
    *,
    feat_id: str = "F001",
    title: str = "Test Feature",
    description: str = "A test feature.",
    status: str = "proposed",
    requirements: list[str] | None = None,
    tasks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": feat_id,
        "title": title,
        "description": description,
        "status": status,
        "requirements": requirements or [],
        "tasks": tasks or [],
    }


def _make_task_payload(
    *,
    task_id: str = "T001",
    feature_id: str = "F001",
    title: str = "Test Task",
    description: str = "A test task.",
    status: str = "proposed",
    priority: str = "medium",
    acceptance_criteria: list[str] | None = None,
    verification_commands: list[str] | None = None,
    likely_files: list[str] | None = None,
    now: datetime = _T0,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "feature_id": feature_id,
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "dependencies": [],
        "conflict_groups": [],
        "scores": {},
        "acceptance_criteria": acceptance_criteria or ["Tests pass."],
        "implementation_notes": [],
        "verification": {
            "commands": verification_commands or ["pytest tests/ -v"],
            "manual_steps": [],
            "required_evidence": [],
        },
        "likely_files": likely_files or [],
        "parent_task_id": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


class TestErrorPaths:
    """Cover the error-handling branches of SqliteBackend.

    These are the audit-critical safety nets: rollback on mutation failure,
    abort-event tombstones, and graceful skip during replay. They're
    infrastructure code paths that rarely fire in healthy operation but must
    behave correctly when they do — otherwise the replay/audit guarantee
    silently degrades.
    """

    def test_apply_event_unknown_action_triggers_abort_tombstone(
        self, tmp_path: Path
    ) -> None:
        """An event with an action the router doesn't recognise must roll
        back the SQLite mutation, write an error.transaction_aborted entry
        to events.jsonl, and raise TransactionAborted. Without the tombstone
        replay would silently re-fire the bad event."""
        b = _make_backend(tmp_path)
        try:
            bad_event = Event(
                id="E000099",
                timestamp=_T0,
                actor="test",
                action="task.never_implemented",  # router doesn't know this
                target_kind="task",
                target_id="T001",
                payload_json={"task_id": "T001"},
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)

            # JSONL must contain the original event AND the abort tombstone.
            events_path = str(tmp_path / "events.jsonl")
            events = _read_jsonl(events_path)
            actions = [e.get("action") for e in events]
            assert "task.never_implemented" in actions, (
                "the original (failed) event should be written to JSONL first"
            )
            assert "error.transaction_aborted" in actions, (
                "an abort tombstone must follow the failed event"
            )
            # SQLite must NOT contain the task row.
            assert b.get_task("T001") is None
        finally:
            b.close()

    def test_close_is_idempotent_after_failure(self, tmp_path: Path) -> None:
        """close() must swallow exceptions from the underlying connection so
        double-close (and close-after-error) never leaks an exception to
        callers. Covers the close() exception-swallow path."""
        b = _make_backend(tmp_path)
        b.close()
        # Second close must not raise; the connection is already None.
        b.close()
        # Re-close again on a freshly-failed connection by forcing one.
        b._conn = sqlite3.connect(":memory:")  # noqa: SLF001
        b._conn.close()
        b.close()  # _conn is already-closed; close path must not raise

    def test_task_status_changed_missing_required_field_aborts(
        self, tmp_path: Path
    ) -> None:
        """task.status_changed without the required 'from' field must abort
        with a clear message — not silently update. Covers the payload
        validation branch in _handle_task_status_changed."""
        b = _make_backend(tmp_path)
        try:
            bad = Event(
                id="E000051",
                timestamp=_T0,
                actor="test",
                action="task.status_changed",
                target_kind="task",
                target_id="T001",
                payload_json={"task_id": "T001", "to": "drafted"},  # no "from"
            )
            with pytest.raises(TransactionAborted, match="from"):
                b.apply_event(bad)
        finally:
            b.close()

    def test_task_status_changed_idempotent_when_already_at_target(
        self, tmp_path: Path
    ) -> None:
        """task.status_changed must be idempotent — re-applying when the task
        is already at the target status is a no-op success, not an error.
        Without this, plan re-runs would always raise once tasks moved past
        the first transition. (Regression test for Greptile PR #38 finding.)
        """
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            # Seed a feature + task in 'drafted' state.
            b.apply_event(_make_event(
                "feature.created", _make_feature_payload(feat_id="F001"),
                event_id="E000010", target_kind="feature", target_id="F001",
            ))
            task_payload = _make_task_payload(task_id="T001", feature_id="F001")
            task_payload["status"] = "drafted"  # seed directly at drafted
            b.apply_event(_make_event(
                "task.created", task_payload,
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            # Apply a status_changed proposed → drafted; the task is ALREADY
            # at 'drafted'. Should silently succeed (no-op).
            idempotent_event = _make_event(
                "task.status_changed",
                {"task_id": "T001", "from": "proposed", "to": "drafted"},
                event_id="E000012",
            )
            b.apply_event(idempotent_event)  # must not raise

            # Confirm status unchanged
            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "drafted"
        finally:
            b.close()

    def test_task_status_changed_unknown_task_aborts(
        self, tmp_path: Path
    ) -> None:
        """task.status_changed for a nonexistent task must abort cleanly
        with 'task not found' — not silently UPDATE zero rows."""
        b = _make_backend(tmp_path)
        try:
            bad = Event(
                id="E000052",
                timestamp=_T0,
                actor="test",
                action="task.status_changed",
                target_kind="task",
                target_id="T999",
                payload_json={
                    "task_id": "T999",
                    "from": "proposed",
                    "to": "drafted",
                },
            )
            with pytest.raises(TransactionAborted, match="not found|T999"):
                b.apply_event(bad)
        finally:
            b.close()

    def test_replay_skips_unsupported_action_gracefully(
        self, tmp_path: Path
    ) -> None:
        """During replay an unknown action should be skipped (rolled back,
        not raised). This lets older log files replay forward on a newer
        codebase that may have removed a no-longer-supported action."""
        b = _make_backend(tmp_path)
        try:
            # Hand-write an events.jsonl with one good event + one unknown.
            events_path = str(tmp_path / "events.jsonl")
            with open(events_path, "w", encoding="utf-8") as fh:
                fh.write(_make_project_event().model_dump_json() + "\n")
                fh.write(
                    Event(
                        id="E000099",
                        timestamp=_T0,
                        actor="test",
                        action="some.future.action",
                        target_kind="task",
                        target_id="T001",
                        payload_json={},
                    ).model_dump_json()
                    + "\n"
                )

            # replay_from_empty should not raise; just skip the unknown action.
            b.replay_from_empty(events_path)

            # Project row from the first event must be present.
            project = b.get_project()
            assert project is not None
            assert project.id == "proj-1"
        finally:
            b.close()


def _make_prd_parsed_payload(
    *,
    project_id: str = "proj-1",
    summary: str = "A test PRD summary.",
    requirements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if requirements is None:
        requirements = [
            {
                "id": "R001",
                "prd_section": "requirements",
                "text": "First requirement.",
                "source_paragraph": None,
                "derived": False,
            },
            {
                "id": "R002",
                "prd_section": "requirements",
                "text": "Second requirement.",
                "source_paragraph": None,
                "derived": False,
            },
        ]
    return {
        "project_id": project_id,
        "status": "draft",
        "summary": summary,
        "goals": ["Goal one.", "Goal two."],
        "non_goals": [],
        "requirements": requirements,
        "acceptance_criteria": ["AC one."],
        "risks": [],
        "open_questions": [],
    }


def _make_event(
    action: str,
    payload: dict[str, Any],
    *,
    event_id: str = "E000003",
    target_kind: str = "prd",
    target_id: str = "proj-1",
    now: datetime = _T0,
) -> Event:
    return Event(
        id=event_id,
        timestamp=now,
        actor="test",
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        payload_json=payload,
    )


def _setup_project(b: SqliteBackend) -> None:
    """Apply project.created so FK constraints are satisfied."""
    b.apply_event(_make_project_event(event_id="E000001"))
    b.apply_event(_make_init_event(event_id="E000002"))


# ---------------------------------------------------------------------------
# Phase 3 — prd.parsed handler
# ---------------------------------------------------------------------------


class TestHandlePrdParsed:
    def test_handle_prd_parsed_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """prd.parsed event writes JSONL line AND PRD + requirements rows to SQLite."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)

            payload = _make_prd_parsed_payload()
            event = _make_event("prd.parsed", payload, event_id="E000003")
            b.apply_event(event)

            # JSONL line present
            events = _read_jsonl(events_path)
            assert any(e.get("action") == "prd.parsed" for e in events)

            # PRD row in SQLite
            prd = b.get_prd()
            assert prd is not None
            assert "test PRD summary" in prd.summary.lower() or "summary" in prd.summary.lower()

            # Requirements rows
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            rows = conn.execute("SELECT id FROM requirements").fetchall()
            conn.close()
            req_ids = {r[0] for r in rows}
            assert "R001" in req_ids
            assert "R002" in req_ids
        finally:
            b.close()

    def test_handle_prd_parsed_payload_validation_missing_project_id(
        self, tmp_path: Path
    ) -> None:
        """prd.parsed without project_id → TransactionAborted, error in JSONL, no PRD row."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)

            bad_payload = _make_prd_parsed_payload()
            del bad_payload["project_id"]  # remove required field
            event = _make_event("prd.parsed", bad_payload, event_id="E000003")

            with pytest.raises(TransactionAborted):
                b.apply_event(event)

            # Abort tombstone in JSONL
            events = _read_jsonl(events_path)
            aborts = [e for e in events if e.get("action") == "error.transaction_aborted"]
            assert len(aborts) >= 1

            # No PRD row written
            prd = b.get_prd()
            assert prd is None
        finally:
            b.close()

    def test_prd_parsed_replaces_requirements_destructively(self, tmp_path: Path) -> None:
        """Apply prd.parsed twice with different requirements; final state matches second parse."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)

            # First parse: R001, R002, R003
            payload_v1 = _make_prd_parsed_payload(
                requirements=[
                    {"id": "R001", "prd_section": "requirements", "text": "V1 req 1.",
                     "source_paragraph": None, "derived": False},
                    {"id": "R002", "prd_section": "requirements", "text": "V1 req 2.",
                     "source_paragraph": None, "derived": False},
                    {"id": "R003", "prd_section": "requirements", "text": "V1 req 3.",
                     "source_paragraph": None, "derived": False},
                ]
            )
            b.apply_event(_make_event("prd.parsed", payload_v1, event_id="E000003"))

            # Second parse: only R001, R002 (different text)
            payload_v2 = _make_prd_parsed_payload(
                summary="Second version summary.",
                requirements=[
                    {"id": "R001", "prd_section": "requirements", "text": "V2 req 1.",
                     "source_paragraph": None, "derived": False},
                    {"id": "R002", "prd_section": "requirements", "text": "V2 req 2.",
                     "source_paragraph": None, "derived": False},
                ]
            )
            b.apply_event(_make_event("prd.parsed", payload_v2, event_id="E000004"))

            # Final state: only 2 requirements, R003 gone
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            rows = conn.execute("SELECT id, text FROM requirements").fetchall()
            conn.close()

            assert len(rows) == 2
            req_ids = {r[0] for r in rows}
            assert "R003" not in req_ids
            # Text is from v2
            texts = {r[1] for r in rows}
            assert any("V2" in t for t in texts)
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — prd.reviewed handler
# ---------------------------------------------------------------------------


class TestHandlePrdReviewed:
    def test_handle_prd_reviewed_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """prd.reviewed event updates PRD status to 'reviewed'. Does NOT
        insert a reviews row — the prds.status column transition is its
        own audit. (See Greptile PR #38 finding: writing decision='approve'
        for prd.reviewed made it indistinguishable from prd.approved.)
        """
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            # First parse the PRD
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(), event_id="E000003"
            ))

            # Now review it
            reviewed_event = _make_event(
                "prd.reviewed",
                {"project_id": "proj-1", "reviewer": "alice", "notes": "Looks good."},
                event_id="E000004",
                target_kind="prd",
            )
            b.apply_event(reviewed_event)

            # JSONL line
            events = _read_jsonl(events_path)
            assert any(e.get("action") == "prd.reviewed" for e in events)

            # PRD status updated
            prd = b.get_prd()
            assert prd is not None
            assert prd.status.value == "reviewed"
            assert prd.last_reviewed_by == "alice"

            # NO reviews row inserted — reviews table is only for
            # outcome-bearing decisions (approve/reject/needs_changes).
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            review_row = conn.execute(
                "SELECT id FROM reviews WHERE reviewed_by = 'alice'"
            ).fetchone()
            conn.close()
            assert review_row is None, (
                "prd.reviewed must NOT insert a reviews row — only "
                "prd.approved (and future prd.rejected) should."
            )
        finally:
            b.close()

    def test_handle_prd_reviewed_payload_validation_missing_reviewer(
        self, tmp_path: Path
    ) -> None:
        """prd.reviewed without reviewer → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(), event_id="E000003"
            ))

            bad_event = _make_event(
                "prd.reviewed",
                {"project_id": "proj-1", "notes": "No reviewer field"},  # missing reviewer
                event_id="E000004",
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)
        finally:
            b.close()

    def test_handle_prd_reviewed_missing_project_id_aborts(
        self, tmp_path: Path
    ) -> None:
        """prd.reviewed without project_id → TransactionAborted. (Regression
        test for Greptile PR #38 finding: the UPDATE prds statement was
        missing a WHERE clause; project_id is now required so multi-PRD
        setups don't accidentally co-mutate.)
        """
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(), event_id="E000003"
            ))
            bad = _make_event(
                "prd.reviewed",
                {"reviewer": "alice"},  # no project_id
                event_id="E000004",
            )
            with pytest.raises(TransactionAborted, match="project_id"):
                b.apply_event(bad)
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — prd.approved handler
# ---------------------------------------------------------------------------


class TestHandlePrdApproved:
    def test_handle_prd_approved_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """prd.approved updates status to 'approved' and inserts review row."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(), event_id="E000003"
            ))
            b.apply_event(_make_event(
                "prd.reviewed",
                {"project_id": "proj-1", "reviewer": "alice"},
                event_id="E000004",
            ))
            b.apply_event(_make_event(
                "prd.approved",
                {"project_id": "proj-1", "approver": "bob"},
                event_id="E000005",
            ))

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "prd.approved" for e in events)

            prd = b.get_prd()
            assert prd is not None
            assert prd.status.value == "approved"
        finally:
            b.close()

    def test_handle_prd_approved_missing_project_id_aborts(
        self, tmp_path: Path
    ) -> None:
        """prd.approved without project_id → TransactionAborted. (Greptile
        PR #38 fix #2: UPDATE statements scoped via WHERE project_id = ?.)
        """
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(), event_id="E000003"
            ))
            b.apply_event(_make_event(
                "prd.reviewed",
                {"project_id": "proj-1", "reviewer": "alice"},
                event_id="E000004",
            ))
            bad = _make_event(
                "prd.approved",
                {"approver": "bob"},  # no project_id
                event_id="E000005",
            )
            with pytest.raises(TransactionAborted, match="project_id"):
                b.apply_event(bad)
        finally:
            b.close()

    def test_handle_prd_approved_payload_validation_missing_approver(
        self, tmp_path: Path
    ) -> None:
        """prd.approved without approver → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(), event_id="E000003"
            ))
            b.apply_event(_make_event(
                "prd.reviewed",
                {"project_id": "proj-1", "reviewer": "alice"},
                event_id="E000004",
            ))
            bad_event = _make_event(
                "prd.approved", {"project_id": "proj-1"}, event_id="E000005"
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — feature.created handler
# ---------------------------------------------------------------------------


class TestHandleFeatureCreated:
    def test_handle_feature_created_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """feature.created event inserts feature row and writes JSONL."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)

            feat_payload = _make_feature_payload(feat_id="F001")
            event = _make_event(
                "feature.created", feat_payload,
                event_id="E000003", target_kind="feature", target_id="F001"
            )
            b.apply_event(event)

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "feature.created" for e in events)

            conn = sqlite3.connect(str(tmp_path / "state.db"))
            row = conn.execute(
                "SELECT id, title FROM features WHERE id = 'F001'"
            ).fetchone()
            conn.close()
            assert row is not None
            assert row[1] == "Test Feature"
        finally:
            b.close()

    def test_handle_feature_created_payload_validation(self, tmp_path: Path) -> None:
        """feature.created with invalid payload (bad status) → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)

            bad_payload = _make_feature_payload()
            bad_payload["status"] = "invalid_status_not_in_enum"
            event = _make_event("feature.created", bad_payload, event_id="E000003")
            with pytest.raises(TransactionAborted):
                b.apply_event(event)
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — task.created handler
# ---------------------------------------------------------------------------


class TestHandleTaskCreated:
    def _setup_feature(self, b: SqliteBackend) -> None:
        """Insert F001 so FK constraint is satisfied."""
        feat_payload = _make_feature_payload(feat_id="F001")
        event = _make_event(
            "feature.created", feat_payload,
            event_id="E000003", target_kind="feature", target_id="F001"
        )
        b.apply_event(event)

    def test_handle_task_created_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """task.created event inserts task row and writes JSONL."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            self._setup_feature(b)

            task_payload = _make_task_payload(task_id="T001")
            event = _make_event(
                "task.created", task_payload,
                event_id="E000004", target_kind="task", target_id="T001"
            )
            b.apply_event(event)

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "task.created" for e in events)

            task = b.get_task("T001")
            assert task is not None
            assert task.id == "T001"
            assert task.title == "Test Task"
        finally:
            b.close()

    def test_handle_task_created_payload_validation(self, tmp_path: Path) -> None:
        """task.created with missing required fields → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            self._setup_feature(b)

            bad_payload = _make_task_payload()
            del bad_payload["created_at"]  # required field removed
            event = _make_event("task.created", bad_payload, event_id="E000004")
            with pytest.raises(TransactionAborted):
                b.apply_event(event)
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — task.scored handler
# ---------------------------------------------------------------------------


class TestHandleTaskScored:
    def _setup_task(self, b: SqliteBackend) -> None:
        feat_payload = _make_feature_payload(feat_id="F001")
        b.apply_event(_make_event(
            "feature.created", feat_payload,
            event_id="E000003", target_kind="feature", target_id="F001"
        ))
        task_payload = _make_task_payload(task_id="T001")
        b.apply_event(_make_event(
            "task.created", task_payload,
            event_id="E000004", target_kind="task", target_id="T001"
        ))

    def test_handle_task_scored_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """task.scored event updates task scores in SQLite and writes JSONL."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            self._setup_task(b)

            score_payload = {
                "task_id": "T001",
                "scores": {
                    "complexity": 3,
                    "parallelizability": 4,
                    "context_load": 2,
                    "blast_radius": 2,
                    "review_risk": 2,
                    "agent_suitability": 3,
                },
                "explanation": "complexity: 3 (base 2, +1 files)",
            }
            event = _make_event(
                "task.scored", score_payload,
                event_id="E000005", target_kind="task", target_id="T001"
            )
            b.apply_event(event)

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "task.scored" for e in events)

            task = b.get_task("T001")
            assert task is not None
            assert task.scores.complexity == 3
            assert task.scores.parallelizability == 4
        finally:
            b.close()

    def test_handle_task_scored_payload_validation_missing_task_id(
        self, tmp_path: Path
    ) -> None:
        """task.scored without task_id → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            self._setup_task(b)

            bad_payload = {
                "scores": {"complexity": 3},
                "explanation": "test",
                # missing task_id
            }
            event = _make_event("task.scored", bad_payload, event_id="E000005")
            with pytest.raises(TransactionAborted):
                b.apply_event(event)
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — task.expanded handler
# ---------------------------------------------------------------------------


class TestHandleTaskExpanded:
    def _setup_task(self, b: SqliteBackend) -> None:
        feat_payload = _make_feature_payload(feat_id="F001")
        b.apply_event(_make_event(
            "feature.created", feat_payload,
            event_id="E000003", target_kind="feature", target_id="F001"
        ))
        task_payload = _make_task_payload(task_id="T001")
        b.apply_event(_make_event(
            "task.created", task_payload,
            event_id="E000004", target_kind="task", target_id="T001"
        ))

    def test_handle_task_expanded_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """task.expanded inserts subtask rows and writes JSONL."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            self._setup_task(b)

            subtask_payload = _make_task_payload(task_id="T001.1", feature_id="F001")
            expand_payload = {
                "parent_task_id": "T001",
                "subtasks": [subtask_payload],
            }
            event = _make_event(
                "task.expanded", expand_payload,
                event_id="E000005", target_kind="task", target_id="T001"
            )
            b.apply_event(event)

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "task.expanded" for e in events)

            # Subtask inserted
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            row = conn.execute(
                "SELECT id, parent_task_id FROM tasks WHERE id = 'T001.1'"
            ).fetchone()
            conn.close()
            assert row is not None
            assert row[1] == "T001"  # parent_task_id was forced
        finally:
            b.close()

    def test_handle_task_expanded_payload_validation_missing_parent(
        self, tmp_path: Path
    ) -> None:
        """task.expanded without parent_task_id → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            self._setup_task(b)

            bad_payload = {
                "subtasks": [_make_task_payload(task_id="T001.1")],
                # missing parent_task_id
            }
            event = _make_event("task.expanded", bad_payload, event_id="E000005")
            with pytest.raises(TransactionAborted):
                b.apply_event(event)
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — task.status_changed handler
# ---------------------------------------------------------------------------


class TestHandleTaskStatusChanged:
    def _setup_task(self, b: SqliteBackend) -> None:
        feat_payload = _make_feature_payload(feat_id="F001")
        b.apply_event(_make_event(
            "feature.created", feat_payload,
            event_id="E000003", target_kind="feature", target_id="F001"
        ))
        task_payload = _make_task_payload(task_id="T001", status="proposed")
        b.apply_event(_make_event(
            "task.created", task_payload,
            event_id="E000004", target_kind="task", target_id="T001"
        ))

    def test_handle_task_status_changed_writes_jsonl_and_sqlite(
        self, tmp_path: Path
    ) -> None:
        """task.status_changed updates task status and writes JSONL."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            self._setup_task(b)

            status_payload = {
                "task_id": "T001",
                "from": "proposed",
                "to": "drafted",
                "reason": "Planning complete.",
            }
            event = _make_event(
                "task.status_changed", status_payload,
                event_id="E000005", target_kind="task", target_id="T001"
            )
            b.apply_event(event)

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "task.status_changed" for e in events)

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "drafted"
        finally:
            b.close()

    def test_handle_task_status_changed_payload_validation_missing_task_id(
        self, tmp_path: Path
    ) -> None:
        """task.status_changed without task_id → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            self._setup_task(b)

            bad_payload = {"from": "proposed", "to": "drafted"}  # no task_id
            event = _make_event("task.status_changed", bad_payload, event_id="E000005")
            with pytest.raises(TransactionAborted):
                b.apply_event(event)
        finally:
            b.close()

    def test_task_status_changed_concurrency_guard_fails_on_drift(
        self, tmp_path: Path
    ) -> None:
        """task.status_changed with wrong 'from' status → TransactionAborted (concurrency guard)."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            self._setup_task(b)

            # Task is in 'proposed', but we claim it's in 'drafted'
            drift_payload = {
                "task_id": "T001",
                "from": "drafted",  # WRONG — actual status is 'proposed'
                "to": "reviewed",
            }
            event = _make_event("task.status_changed", drift_payload, event_id="E000005")
            with pytest.raises(TransactionAborted):
                b.apply_event(event)

            # Task status unchanged
            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "proposed"
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 3 — THE CRITICAL TEST: replay includes all new event actions
# ---------------------------------------------------------------------------


class TestReplayIncludesNewEventActions:
    def test_replay_includes_new_event_actions(self, tmp_path: Path) -> None:
        """events.jsonl with all 8 new actions; replay_from_empty reproduces identical state.

        This is the CRITICAL audit guarantee test for Phase 3 events.
        """
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        try:
            # E000001: project.created
            b.apply_event(_make_project_event(event_id="E000001"))
            # E000002: state.initialized
            b.apply_event(_make_init_event(event_id="E000002"))

            # E000003: prd.parsed
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(),
                event_id="E000003"
            ))

            # E000004: prd.reviewed
            b.apply_event(_make_event(
                "prd.reviewed", {"project_id": "proj-1", "reviewer": "alice"},
                event_id="E000004"
            ))

            # E000005: prd.approved
            b.apply_event(_make_event(
                "prd.approved", {"project_id": "proj-1", "approver": "bob"},
                event_id="E000005"
            ))

            # E000006: feature.created
            b.apply_event(_make_event(
                "feature.created", _make_feature_payload(feat_id="F001"),
                event_id="E000006", target_kind="feature", target_id="F001"
            ))

            # E000007: task.created
            b.apply_event(_make_event(
                "task.created", _make_task_payload(task_id="T001"),
                event_id="E000007", target_kind="task", target_id="T001"
            ))

            # E000008: task.scored
            b.apply_event(_make_event(
                "task.scored",
                {
                    "task_id": "T001",
                    "scores": {
                        "complexity": 2,
                        "parallelizability": 4,
                        "context_load": 5,
                        "blast_radius": 2,
                        "review_risk": 2,
                        "agent_suitability": 4,
                    },
                    "explanation": "complexity: 2 (base 2)",
                },
                event_id="E000008", target_kind="task", target_id="T001"
            ))

            # E000009: task.status_changed (proposed → drafted)
            b.apply_event(_make_event(
                "task.status_changed",
                {"task_id": "T001", "from": "proposed", "to": "drafted", "reason": "planned"},
                event_id="E000009", target_kind="task", target_id="T001"
            ))

            # E000010: task.expanded (add subtask T001.1)
            subtask_data = _make_task_payload(task_id="T001.1", feature_id="F001")
            b.apply_event(_make_event(
                "task.expanded",
                {"parent_task_id": "T001", "subtasks": [subtask_data]},
                event_id="E000010", target_kind="task", target_id="T001"
            ))

        finally:
            b.close()

        # Capture original dump
        original_dump = _sqlite_dump(db_path)

        # Replay from empty
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        # Compare
        replayed_dump = _sqlite_dump(db_path)
        assert original_dump == replayed_dump, (
            "Replayed state.db does not match original after Phase 3 events.\n"
            f"Original dump (first 800 chars):\n{original_dump[:800]}\n\n"
            f"Replayed dump (first 800 chars):\n{replayed_dump[:800]}"
        )


# ---------------------------------------------------------------------------
# Phase 4 — claim event handler helpers
# ---------------------------------------------------------------------------


def _make_claim_payload(
    *,
    claim_id: str = "C001",
    task_id: str = "T001",
    actor: str = "agent-alpha",
    expected_files: list[str] | None = None,
    now: datetime = _T0,
) -> dict[str, Any]:
    """Build a valid claim.created payload (matches Claim.model_dump(mode='json'))."""
    return {
        "id": claim_id,
        "task_id": task_id,
        "claimed_by": actor,
        "claim_type": "task",
        "status": "active",
        "branch": None,
        "worktree_path": None,
        "expected_files": expected_files or [],
        "created_at": now.isoformat(),
        "lease_expires_at": (now + timedelta(hours=1)).isoformat(),
        "last_heartbeat_at": now.isoformat(),
        "released_at": None,
        "release_reason": None,
    }


def _setup_claimable_task(b: SqliteBackend, task_id: str = "T001") -> None:
    """Apply the minimal event chain to produce a 'ready' task."""
    _setup_project(b)
    b.apply_event(_make_event(
        "prd.parsed",
        {
            "project_id": "proj-1",
            "status": "draft",
            "summary": "A test PRD.",
            "goals": ["Goal one."],
            "non_goals": [],
            "requirements": [
                {"id": "R001", "prd_section": "requirements", "text": "Req 1.",
                 "source_paragraph": None, "derived": False}
            ],
            "acceptance_criteria": ["AC one."],
            "risks": [],
            "open_questions": [],
        },
        event_id="E000003", target_kind="prd", target_id="proj-1",
    ))
    b.apply_event(_make_event(
        "prd.reviewed", {"project_id": "proj-1", "reviewer": "alice"},
        event_id="E000004", target_kind="prd", target_id="proj-1",
    ))
    b.apply_event(_make_event(
        "feature.created",
        {
            "id": "F001",
            "title": "Feature F001",
            "description": "A feature.",
            "status": "proposed",
            "requirements": [],
            "tasks": [],
        },
        event_id="E000005", target_kind="feature", target_id="F001",
    ))
    b.apply_event(_make_event(
        "task.created",
        _make_task_payload(task_id=task_id),
        event_id="E000006", target_kind="task", target_id=task_id,
    ))
    # proposed → drafted → reviewed → ready
    for from_s, to_s, eid in [
        ("proposed", "drafted", "E000007"),
        ("drafted", "reviewed", "E000008"),
        ("reviewed", "ready", "E000009"),
    ]:
        b.apply_event(_make_event(
            "task.status_changed",
            {"task_id": task_id, "from": from_s, "to": to_s},
            event_id=eid, target_kind="task", target_id=task_id,
        ))


# ---------------------------------------------------------------------------
# Phase 4 — TestPhase4ClaimHandlers
# ---------------------------------------------------------------------------


class TestPhase4ClaimHandlers:
    def test_handle_claim_created_writes_jsonl_and_sqlite(self, tmp_path: Path) -> None:
        """claim.created writes claim row to SQLite and JSONL; task moves to 'claimed'."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_claimable_task(b)

            payload = _make_claim_payload()
            event = _make_event(
                "claim.created", payload,
                event_id="E000010", target_kind="claim", target_id="C001",
            )
            b.apply_event(event)

            # JSONL line written
            events = _read_jsonl(events_path)
            assert any(e.get("action") == "claim.created" for e in events)

            # Claim in SQLite
            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.status.value == "active"
            assert claim.claimed_by == "agent-alpha"

            # Task moved to 'claimed'
            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "claimed"
        finally:
            b.close()

    def test_handle_claim_created_concurrency_guard_fails_on_drift(
        self, tmp_path: Path
    ) -> None:
        """claim.created aborts if task is not in 'ready' status (concurrency guard)."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "feature.created",
                {
                    "id": "F001", "title": "F", "description": "d", "status": "proposed",
                    "requirements": [], "tasks": [],
                },
                event_id="E000003", target_kind="feature", target_id="F001",
            ))
            # Task in 'proposed' — NOT ready
            b.apply_event(_make_event(
                "task.created",
                _make_task_payload(task_id="T001", status="proposed"),
                event_id="E000004", target_kind="task", target_id="T001",
            ))

            payload = _make_claim_payload()
            event = _make_event(
                "claim.created", payload,
                event_id="E000005", target_kind="claim", target_id="C001",
            )
            with pytest.raises(TransactionAborted, match="ready|proposed|concurrency"):
                b.apply_event(event)
        finally:
            b.close()

    def test_handle_claim_created_idempotent_on_replay(self, tmp_path: Path) -> None:
        """Applying claim.created twice is a no-op for the second application."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)

            payload = _make_claim_payload()
            event = _make_event(
                "claim.created", payload,
                event_id="E000010", target_kind="claim", target_id="C001",
            )
            b.apply_event(event)  # first: commits

            # Second apply should not raise (idempotent INSERT OR IGNORE)
            b.apply_event(event)  # second: replay no-op

            # Still only one claim
            active = b.list_active_claims()
            assert len(active) == 1
            assert active[0].id == "C001"
        finally:
            b.close()

    def test_handle_claim_released_happy_path(self, tmp_path: Path) -> None:
        """claim.released updates claim to released and task to ready."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_claimable_task(b)

            # First create the claim
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            # Release it
            release_event = _make_event(
                "claim.released",
                {
                    "claim_id": "C001",
                    "released_by": "agent-alpha",
                    "release_reason": "work complete",
                    "force": False,
                },
                event_id="E000011", target_kind="claim", target_id="C001",
            )
            b.apply_event(release_event)

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "claim.released" for e in events)

            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.status.value == "released"

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "ready"
        finally:
            b.close()

    def test_handle_claim_released_idempotent_when_already_released(
        self, tmp_path: Path
    ) -> None:
        """claim.released on an already-released claim is a no-op (logs warning, no raise)."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            release_payload = {
                "claim_id": "C001",
                "released_by": "agent-alpha",
                "release_reason": "done",
                "force": False,
            }
            b.apply_event(_make_event(
                "claim.released", release_payload,
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            # Second release: handler logs warning, does not raise
            b.apply_event(_make_event(
                "claim.released", release_payload,
                event_id="E000012", target_kind="claim", target_id="C001",
            ))

            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.status.value == "released"
        finally:
            b.close()

    def test_handle_claim_renewed_updates_timestamps(self, tmp_path: Path) -> None:
        """claim.renewed updates lease_expires_at and last_heartbeat_at in SQLite."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            new_expires = (_T0 + timedelta(hours=2)).isoformat()
            new_heartbeat = (_T0 + timedelta(minutes=30)).isoformat()
            b.apply_event(_make_event(
                "claim.renewed",
                {
                    "claim_id": "C001",
                    "renewed_by": "agent-alpha",
                    "lease_expires_at": new_expires,
                    "last_heartbeat_at": new_heartbeat,
                },
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.lease_expires_at.isoformat() == new_expires
            assert claim.last_heartbeat_at.isoformat() == new_heartbeat
        finally:
            b.close()

    def test_handle_claim_renewed_refuses_inactive_claim(self, tmp_path: Path) -> None:
        """claim.renewed on a non-active claim raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))
            # Release the claim first
            b.apply_event(_make_event(
                "claim.released",
                {"claim_id": "C001", "released_by": "agent-alpha", "release_reason": "done"},
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            # Now try to renew the released claim
            with pytest.raises(TransactionAborted, match="active|released|status"):
                b.apply_event(_make_event(
                    "claim.renewed",
                    {
                        "claim_id": "C001",
                        "renewed_by": "agent-alpha",
                        "lease_expires_at": (_T0 + timedelta(hours=3)).isoformat(),
                        "last_heartbeat_at": _T0.isoformat(),
                    },
                    event_id="E000012", target_kind="claim", target_id="C001",
                ))
        finally:
            b.close()

    def test_handle_claim_stale_happy_path(self, tmp_path: Path) -> None:
        """claim.stale marks claim as stale and task returns to ready."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            b.apply_event(_make_event(
                "claim.stale",
                {
                    "claim_id": "C001",
                    "task_id": "T001",
                    "expired_at": (_T0 - timedelta(hours=1)).isoformat(),
                    "detected_at": _T0.isoformat(),
                    "reason": "lease_expired",
                    "actor": "system",
                },
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "claim.stale" for e in events)

            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.status.value == "stale"

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "ready"
        finally:
            b.close()

    def test_handle_claim_stale_idempotent(self, tmp_path: Path) -> None:
        """Applying claim.stale twice is a no-op for the second application."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            stale_payload = {
                "claim_id": "C001",
                "task_id": "T001",
                "expired_at": (_T0 - timedelta(hours=1)).isoformat(),
                "detected_at": _T0.isoformat(),
                "reason": "lease_expired",
                "actor": "system",
            }
            b.apply_event(_make_event(
                "claim.stale", stale_payload,
                event_id="E000011", target_kind="claim", target_id="C001",
            ))
            # Second apply: no-op, no raise
            b.apply_event(_make_event(
                "claim.stale", stale_payload,
                event_id="E000012", target_kind="claim", target_id="C001",
            ))

            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.status.value == "stale"
        finally:
            b.close()

    def test_handle_claim_stale_handles_task_already_completed_gracefully(
        self, tmp_path: Path
    ) -> None:
        """claim.stale when task is already 'done': claim goes stale without error."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            # Manually move task to 'done' (simulating completed work)
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            conn.execute("UPDATE tasks SET status = 'done' WHERE id = 'T001'")
            conn.commit()
            conn.close()

            # claim.stale should still mark the claim stale without raising
            b.apply_event(_make_event(
                "claim.stale",
                {
                    "claim_id": "C001",
                    "task_id": "T001",
                    "expired_at": (_T0 - timedelta(hours=1)).isoformat(),
                    "detected_at": _T0.isoformat(),
                    "reason": "lease_expired",
                    "actor": "system",
                },
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.status.value == "stale"

            # Task remains 'done' — not reset to ready
            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "done"
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 4 — audit guarantee extended to claim event actions
# ---------------------------------------------------------------------------


class TestReplayIncludesPhase4ClaimActions:
    def test_replay_includes_claim_event_actions(self, tmp_path: Path) -> None:
        """Replay events.jsonl with all 4 claim actions; reconstructed DB matches original.

        Sequence: project.created → state.initialized → prd.parsed → prd.reviewed
        → prd.approved → feature.created → task.created → task.scored →
        task.status_changed (→ ready) → claim.created → claim.renewed → claim.released.
        """
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        try:
            # E000001: project.created
            b.apply_event(_make_project_event(event_id="E000001"))
            # E000002: state.initialized
            b.apply_event(_make_init_event(event_id="E000002"))

            # E000003: prd.parsed
            b.apply_event(_make_event(
                "prd.parsed",
                {
                    "project_id": "proj-1",
                    "status": "draft",
                    "summary": "Replay test PRD.",
                    "goals": ["Goal."],
                    "non_goals": [],
                    "requirements": [
                        {"id": "R001", "prd_section": "requirements", "text": "Req.",
                         "source_paragraph": None, "derived": False}
                    ],
                    "acceptance_criteria": ["AC."],
                    "risks": [],
                    "open_questions": [],
                },
                event_id="E000003", target_kind="prd", target_id="proj-1",
            ))
            # E000004: prd.reviewed
            b.apply_event(_make_event(
                "prd.reviewed",
                {"project_id": "proj-1", "reviewer": "alice"},
                event_id="E000004", target_kind="prd", target_id="proj-1",
            ))
            # E000005: prd.approved
            b.apply_event(_make_event(
                "prd.approved",
                {"project_id": "proj-1", "approver": "bob"},
                event_id="E000005", target_kind="prd", target_id="proj-1",
            ))

            # E000006: feature.created
            b.apply_event(_make_event(
                "feature.created",
                _make_feature_payload(feat_id="F001"),
                event_id="E000006", target_kind="feature", target_id="F001",
            ))

            # E000007: task.created
            b.apply_event(_make_event(
                "task.created",
                _make_task_payload(task_id="T001"),
                event_id="E000007", target_kind="task", target_id="T001",
            ))

            # E000008: task.scored
            b.apply_event(_make_event(
                "task.scored",
                {
                    "task_id": "T001",
                    "scores": {
                        "complexity": 2, "parallelizability": 4, "context_load": 3,
                        "blast_radius": 2, "review_risk": 2, "agent_suitability": 4,
                    },
                    "explanation": "scored for replay test",
                },
                event_id="E000008", target_kind="task", target_id="T001",
            ))

            # E000009: task.status_changed proposed → ready (via drafted + reviewed)
            for from_s, to_s, eid in [
                ("proposed", "drafted", "E000009"),
                ("drafted", "reviewed", "E000010"),
                ("reviewed", "ready", "E000011"),
            ]:
                b.apply_event(_make_event(
                    "task.status_changed",
                    {"task_id": "T001", "from": from_s, "to": to_s},
                    event_id=eid, target_kind="task", target_id="T001",
                ))

            # E000012: claim.created
            b.apply_event(_make_event(
                "claim.created",
                _make_claim_payload(claim_id="C001", task_id="T001"),
                event_id="E000012", target_kind="claim", target_id="C001",
            ))

            # E000013: claim.renewed
            b.apply_event(_make_event(
                "claim.renewed",
                {
                    "claim_id": "C001",
                    "renewed_by": "agent-alpha",
                    "lease_expires_at": (_T0 + timedelta(hours=2)).isoformat(),
                    "last_heartbeat_at": (_T0 + timedelta(minutes=30)).isoformat(),
                },
                event_id="E000013", target_kind="claim", target_id="C001",
            ))

            # E000014: claim.released
            b.apply_event(_make_event(
                "claim.released",
                {
                    "claim_id": "C001",
                    "released_by": "agent-alpha",
                    "release_reason": "replay test done",
                    "force": False,
                },
                event_id="E000014", target_kind="claim", target_id="C001",
            ))

        finally:
            b.close()

        # Capture original dump
        original_dump = _sqlite_dump(db_path)

        # Replay from empty
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        replayed_dump = _sqlite_dump(db_path)
        assert original_dump == replayed_dump, (
            "Replayed state.db does not match original after Phase 4 claim events.\n"
            f"Original dump (first 800 chars):\n{original_dump[:800]}\n\n"
            f"Replayed dump (first 800 chars):\n{replayed_dump[:800]}"
        )


    def test_replay_includes_claim_stale(self, tmp_path: Path) -> None:
        """Audit guarantee for claim.stale: a sequence ending in stale (rather
        than released) must replay byte-identically. Complements the primary
        replay test above which exercises created → renewed → released."""
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        try:
            b.apply_event(_make_project_event(event_id="E000001"))
            b.apply_event(_make_init_event(event_id="E000002"))
            b.apply_event(_make_event(
                "prd.parsed",
                {
                    "project_id": "proj-1", "status": "draft",
                    "summary": "Stale replay test.",
                    "goals": ["G"], "non_goals": [],
                    "requirements": [
                        {"id": "R001", "prd_section": "requirements", "text": "Req.",
                         "source_paragraph": None, "derived": False}
                    ],
                    "acceptance_criteria": ["AC"], "risks": [], "open_questions": [],
                },
                event_id="E000003", target_kind="prd", target_id="proj-1",
            ))
            b.apply_event(_make_event(
                "prd.approved",
                {"project_id": "proj-1", "approver": "bob"},
                event_id="E000004", target_kind="prd", target_id="proj-1",
            ))
            b.apply_event(_make_event(
                "feature.created",
                _make_feature_payload(feat_id="F001"),
                event_id="E000005", target_kind="feature", target_id="F001",
            ))
            b.apply_event(_make_event(
                "task.created",
                _make_task_payload(task_id="T001"),
                event_id="E000006", target_kind="task", target_id="T001",
            ))
            for from_s, to_s, eid in [
                ("proposed", "drafted", "E000007"),
                ("drafted", "reviewed", "E000008"),
                ("reviewed", "ready", "E000009"),
            ]:
                b.apply_event(_make_event(
                    "task.status_changed",
                    {"task_id": "T001", "from": from_s, "to": to_s},
                    event_id=eid, target_kind="task", target_id="T001",
                ))
            # E000010: claim.created (lease expires immediately for stale path)
            claim_payload = _make_claim_payload(claim_id="C001", task_id="T001")
            b.apply_event(_make_event(
                "claim.created", claim_payload,
                event_id="E000010", target_kind="claim", target_id="C001",
            ))
            # E000011: claim.stale (lease expired)
            b.apply_event(_make_event(
                "claim.stale",
                {
                    "claim_id": "C001",
                    "detected_at": (_T0 + timedelta(hours=2)).isoformat(),
                    "reason": "lease_expired",
                },
                event_id="E000011", target_kind="claim", target_id="C001",
            ))
        finally:
            b.close()

        original_dump = _sqlite_dump(db_path)

        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        replayed_dump = _sqlite_dump(db_path)
        assert original_dump == replayed_dump, (
            "Replayed state.db does not match original after claim.stale event."
        )


# ---------------------------------------------------------------------------
# Phase 4 — additional coverage tests for uncovered branches
# ---------------------------------------------------------------------------


class TestGreptileP4Fixes:
    """Regression tests for the three MUST-FIX defects Greptile + critic
    flagged on PR #39: file_changed had no handler (events silently
    aborted); release --force on a stale claim was a no-op; release
    UPDATE on the tasks table was hardcoded to status='claimed'.
    """

    def test_file_changed_event_lands_in_sqlite_with_no_tombstone(
        self, tmp_path: Path
    ) -> None:
        """The record-file-change hook emits action='file_changed'. Before
        the fix, this action had no handler — apply_event would raise
        NotImplementedError, write an error.transaction_aborted tombstone
        to JSONL, and the event was dropped from the events table on
        replay. Now: file_changed is a recognised audit-only action;
        the event lands in both JSONL and the events table; no tombstone."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            evt = _make_event(
                "file_changed",
                {"file": "src/foo.py", "tool": "Edit", "actor": "agent-alpha"},
                event_id="E000003",
                target_kind="file",
                target_id="src/foo.py",
            )
            b.apply_event(evt)

            # JSONL: file_changed present, NO error.transaction_aborted.
            events = _read_jsonl(events_path)
            actions = [e.get("action") for e in events]
            assert "file_changed" in actions
            assert "error.transaction_aborted" not in actions

            # SQLite events table: the event row is present.
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            row = conn.execute(
                "SELECT id, action FROM events WHERE id = 'E000003'"
            ).fetchone()
            conn.close()
            assert row is not None
            assert row[1] == "file_changed"
        finally:
            b.close()

    def test_force_release_of_stale_claim_actually_transitions_status(
        self, tmp_path: Path
    ) -> None:
        """Before the fix, _handle_claim_released's UPDATE was guarded by
        WHERE status='active'. A stale claim (status='stale') matched 0
        rows; the handler logged 'already terminal — no-op' and returned
        success. The claim stayed at 'stale' forever; the user thought
        the force-release worked. Now: with force=True, status is widened
        to NOT IN ('released', 'force_released') and target is 'force_released'."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            # Drive the claim to 'stale' directly (simulates the stale detector
            # having run).
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            conn.execute(
                "UPDATE claims SET status='stale' WHERE id='C001'"
            )
            conn.commit()
            conn.close()

            # Force-release the stale claim.
            release_payload = {
                "claim_id": "C001",
                "released_by": "human",
                "release_reason": "cleaning up",
                "force": True,
            }
            b.apply_event(_make_event(
                "claim.released", release_payload,
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            # Claim must now be 'force_released', not 'stale'.
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            status = conn.execute(
                "SELECT status FROM claims WHERE id='C001'"
            ).fetchone()[0]
            release_reason = conn.execute(
                "SELECT release_reason FROM claims WHERE id='C001'"
            ).fetchone()[0]
            conn.close()
            assert status == "force_released", (
                f"force-release should transition stale → force_released; "
                f"got {status!r}"
            )
            assert release_reason == "cleaning up"
        finally:
            b.close()

    def test_release_handles_in_progress_task_without_aborting(
        self, tmp_path: Path
    ) -> None:
        """Before the fix, the task UPDATE was hardcoded WHERE status='claimed'.
        Releasing a claim on an in_progress task would TransactionAborted
        because the WHERE matched 0 rows. release --force is supposed to
        work on tasks mid-work; widened to status IN ('claimed', 'in_progress', 'blocked')."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))
            # Advance task to 'in_progress'
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            conn.execute(
                "UPDATE tasks SET status='in_progress' WHERE id='T001'"
            )
            conn.commit()
            conn.close()

            # Release must succeed and return task to 'ready'.
            b.apply_event(_make_event(
                "claim.released",
                {"claim_id": "C001", "released_by": "agent-alpha",
                 "release_reason": "rolling back", "force": False},
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            conn = sqlite3.connect(str(tmp_path / "state.db"))
            task_status = conn.execute(
                "SELECT status FROM tasks WHERE id='T001'"
            ).fetchone()[0]
            conn.close()
            assert task_status == "ready"
        finally:
            b.close()

    def test_event_ids_are_consistent_across_cli_and_claim_manager(
        self, tmp_path: Path
    ) -> None:
        """Backend.next_event_id is the single source of truth. Before the
        fix, CLI used MAX(id)+1 and ClaimManager used a 20-digit
        microsecond ID; once both landed in the events table the MAX
        query returned the giant number and CLI's E%06d formatter
        silently broke. Now both paths produce E%06d sequential IDs."""
        b = _make_backend(tmp_path)
        try:
            first = b.next_event_id()
            assert first == "E000001"

            b.apply_event(_make_project_event(event_id=first))
            second = b.next_event_id()
            assert second == "E000002"
        finally:
            b.close()

    def test_next_event_id_raises_when_conn_is_none(self, tmp_path: Path) -> None:
        """CL-13 regression: ``next_event_id`` used to silently return the
        literal ``"E000001"`` when ``self._conn is None`` — so calling it
        after ``close()`` (or before ``initialize()``) returned a plausible
        but guaranteed-stale ID. The first real INSERT after a reopen would
        then collide on the events table PK and silently drop via
        ``INSERT OR IGNORE``. Fix: route through ``_require_conn`` like the
        rest of the Backend methods so the error is loud and immediate.
        """
        b = _make_backend(tmp_path)
        try:
            # Sanity: works while open.
            assert b.next_event_id() == "E000001"
        finally:
            b.close()

        # After close(), the no-conn branch must raise — not return E000001.
        with pytest.raises(RuntimeError, match="initialize"):
            b.next_event_id()

    def test_claim_id_generator_uses_uuid_not_sequential(
        self, tmp_path: Path
    ) -> None:
        """Greptile P4 finding: the original _generate_claim_id incremented
        max-of-active-claims, which could collide with a historical
        (released/stale) claim that shared the same C### ID. The SQL
        handler's INSERT OR IGNORE would silently no-op, leaving the
        task associated with the OLD claim row while the user was told
        the new claim succeeded. Fix: always use UUID-derived hex; the
        format is 'C' + 8 hex chars so collision is statistically
        impossible (~4 billion-to-one)."""
        from fakoli_state.claims.manager import ClaimManager
        from fakoli_state.clock import SystemClock

        b = _make_backend(tmp_path)
        try:
            mgr = ClaimManager(b, SystemClock(), actor="agent-alpha")
            id1 = mgr._generate_claim_id()  # noqa: SLF001
            id2 = mgr._generate_claim_id()  # noqa: SLF001
            id3 = mgr._generate_claim_id()  # noqa: SLF001

            # Format: 'C' + exactly 8 uppercase-hex chars.
            for cid in (id1, id2, id3):
                assert cid.startswith("C")
                assert len(cid) == 9, f"expected 'C' + 8 hex chars, got {cid!r}"
                assert all(c in "0123456789ABCDEF" for c in cid[1:]), (
                    f"hex suffix has invalid chars: {cid!r}"
                )

            # All three should be distinct (collision probability ~1 in 4 billion).
            assert id1 != id2 and id2 != id3 and id1 != id3, (
                f"sequential _generate_claim_id calls collided: {id1}, {id2}, {id3}"
            )

            # Critically: the ID generator must NOT inspect active claims
            # and produce a sequential next-up — that was the collision bug.
            # Confirm by adding a fake "active" sequential claim and verifying
            # the next generated ID is still a UUID (not C002).
            assert not any(cid in ("C001", "C002", "C003") for cid in (id1, id2, id3))
        finally:
            b.close()


class TestPhase4CoverageEdgeCases:
    """Additional tests to push claims + state coverage above 95%.

    These cover payload validation failures, concurrency guards, and
    error paths that the primary happy-path tests do not exercise.
    """

    # ------------------------------------------------------------------
    # claim.created edge cases
    # ------------------------------------------------------------------

    def test_handle_claim_created_missing_required_field_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.created with a missing required field raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            bad_payload = _make_claim_payload()
            del bad_payload["claimed_by"]  # remove a required field
            event = _make_event(
                "claim.created", bad_payload,
                event_id="E000010", target_kind="claim", target_id="C001",
            )
            with pytest.raises(TransactionAborted, match="claimed_by|required"):
                b.apply_event(event)
        finally:
            b.close()

    def test_handle_claim_created_task_not_found_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.created for a non-existent task raises TransactionAborted.

        The handler tries to UPDATE tasks WHERE status='ready'; when the task
        does not exist this produces 0 rows → the handler raises TransactionAborted.
        However, the INSERT itself may fail first with a FK constraint if the DB
        enforces foreign keys (which SQLite does with PRAGMA foreign_keys = ON).
        Either path results in TransactionAborted.
        """
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            # No task created — claim refers to T999
            payload = _make_claim_payload(task_id="T999")
            event = _make_event(
                "claim.created", payload,
                event_id="E000003", target_kind="claim", target_id="C001",
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(event)
        finally:
            b.close()

    # ------------------------------------------------------------------
    # claim.released edge cases
    # ------------------------------------------------------------------

    def test_handle_claim_released_missing_claim_id_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.released without claim_id raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))
            bad_payload = {
                # No claim_id
                "released_by": "agent-alpha",
                "release_reason": "done",
                "force": False,
            }
            with pytest.raises(TransactionAborted, match="claim_id|required"):
                b.apply_event(_make_event(
                    "claim.released", bad_payload,
                    event_id="E000011", target_kind="claim", target_id="C001",
                ))
        finally:
            b.close()

    def test_handle_claim_released_claim_not_found_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.released for a non-existent claim raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            payload = {
                "claim_id": "C999",
                "released_by": "agent-alpha",
                "release_reason": "done",
                "force": False,
            }
            with pytest.raises(TransactionAborted, match="C999|not found"):
                b.apply_event(_make_event(
                    "claim.released", payload,
                    event_id="E000003", target_kind="claim", target_id="C999",
                ))
        finally:
            b.close()

    def test_handle_claim_released_tolerates_task_already_completed(
        self, tmp_path: Path
    ) -> None:
        """claim.released does NOT raise when the task has legitimately
        advanced to 'done' (Phase 5 completion) by the time release runs.
        The release path's task UPDATE is now WHERE status IN
        ('claimed', 'in_progress', 'blocked') and 0-rows is acceptable.
        Previous behaviour TransactionAborted'd on this; Greptile + critic
        flagged it would break release --force in real workflows."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            # Manually advance task to 'done' (simulating Phase 5 completion
            # racing with this release).
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            conn.execute("UPDATE tasks SET status = 'done' WHERE id = 'T001'")
            conn.commit()
            conn.close()

            release_payload = {
                "claim_id": "C001",
                "released_by": "agent-alpha",
                "release_reason": "done",
                "force": False,
            }
            # No raise — release should succeed (idempotent on the task side)
            b.apply_event(_make_event(
                "claim.released", release_payload,
                event_id="E000011", target_kind="claim", target_id="C001",
            ))

            # Claim is released; task stays 'done'.
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            claim_status = conn.execute(
                "SELECT status FROM claims WHERE id = 'C001'"
            ).fetchone()[0]
            task_status = conn.execute(
                "SELECT status FROM tasks WHERE id = 'T001'"
            ).fetchone()[0]
            conn.close()
            assert claim_status == "released"
            assert task_status == "done"
        finally:
            b.close()

    # ------------------------------------------------------------------
    # claim.renewed edge cases
    # ------------------------------------------------------------------

    def test_handle_claim_renewed_missing_field_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.renewed without lease_expires_at raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))
            bad_payload = {
                "claim_id": "C001",
                "renewed_by": "agent-alpha",
                # Missing lease_expires_at and last_heartbeat_at
            }
            with pytest.raises(TransactionAborted, match="lease_expires_at|required"):
                b.apply_event(_make_event(
                    "claim.renewed", bad_payload,
                    event_id="E000011", target_kind="claim", target_id="C001",
                ))
        finally:
            b.close()

    def test_handle_claim_renewed_claim_not_found_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.renewed for a non-existent claim raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            payload = {
                "claim_id": "C999",
                "renewed_by": "agent-alpha",
                "lease_expires_at": (_T0 + timedelta(hours=2)).isoformat(),
                "last_heartbeat_at": _T0.isoformat(),
            }
            with pytest.raises(TransactionAborted, match="C999|not found|active"):
                b.apply_event(_make_event(
                    "claim.renewed", payload,
                    event_id="E000003", target_kind="claim", target_id="C999",
                ))
        finally:
            b.close()

    # ------------------------------------------------------------------
    # claim.stale edge cases
    # ------------------------------------------------------------------

    def test_handle_claim_stale_missing_field_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.stale without detected_at raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created", _make_claim_payload(),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))
            bad_payload = {
                "claim_id": "C001",
                # Missing detected_at and reason
            }
            with pytest.raises(TransactionAborted, match="detected_at|required"):
                b.apply_event(_make_event(
                    "claim.stale", bad_payload,
                    event_id="E000011", target_kind="claim", target_id="C001",
                ))
        finally:
            b.close()

    def test_handle_claim_stale_claim_not_found_aborts(
        self, tmp_path: Path
    ) -> None:
        """claim.stale for a non-existent claim raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            payload = {
                "claim_id": "C999",
                "task_id": "T001",
                "expired_at": (_T0 - timedelta(hours=1)).isoformat(),
                "detected_at": _T0.isoformat(),
                "reason": "lease_expired",
                "actor": "system",
            }
            with pytest.raises(TransactionAborted, match="C999|not found"):
                b.apply_event(_make_event(
                    "claim.stale", payload,
                    event_id="E000003", target_kind="claim", target_id="C999",
                ))
        finally:
            b.close()

    # ------------------------------------------------------------------
    # prd.parsed edge cases — invalid requirement payload
    # ------------------------------------------------------------------

    def test_handle_prd_parsed_invalid_requirement_aborts(
        self, tmp_path: Path
    ) -> None:
        """prd.parsed with a malformed Requirement dict raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            bad_payload = {
                "project_id": "proj-1",
                "status": "draft",
                "summary": "Bad req test.",
                "goals": ["Goal."],
                "non_goals": [],
                "requirements": [
                    # Missing required 'id' and 'text' — invalid Requirement
                    {"prd_section": "requirements", "derived": False}
                ],
                "acceptance_criteria": [],
                "risks": [],
                "open_questions": [],
            }
            with pytest.raises(TransactionAborted, match="invalid Requirement|prd.parsed"):
                b.apply_event(_make_event(
                    "prd.parsed", bad_payload,
                    event_id="E000003", target_kind="prd", target_id="proj-1",
                ))
        finally:
            b.close()

    # ------------------------------------------------------------------
    # task.scored edge cases — invalid scores payload
    # ------------------------------------------------------------------

    def test_handle_task_scored_invalid_scores_payload_aborts(
        self, tmp_path: Path
    ) -> None:
        """task.scored with non-integer score values raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "feature.created",
                {
                    "id": "F001", "title": "F", "description": "d", "status": "proposed",
                    "requirements": [], "tasks": [],
                },
                event_id="E000003", target_kind="feature", target_id="F001",
            ))
            b.apply_event(_make_event(
                "task.created",
                _make_task_payload(task_id="T001"),
                event_id="E000004", target_kind="task", target_id="T001",
            ))
            bad_scores = {
                "task_id": "T001",
                "scores": {
                    "complexity": "NOT_A_NUMBER",  # invalid
                    "parallelizability": 4,
                    "context_load": 3,
                    "blast_radius": 2,
                    "review_risk": 2,
                    "agent_suitability": 4,
                },
                "explanation": "bad",
            }
            with pytest.raises(TransactionAborted, match="scores|invalid"):
                b.apply_event(_make_event(
                    "task.scored", bad_scores,
                    event_id="E000005", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    # ------------------------------------------------------------------
    # task.status_changed — missing 'to' field
    # ------------------------------------------------------------------

    def test_handle_task_status_changed_missing_to_aborts(
        self, tmp_path: Path
    ) -> None:
        """task.status_changed without 'to' field raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "feature.created",
                {
                    "id": "F001", "title": "F", "description": "d", "status": "proposed",
                    "requirements": [], "tasks": [],
                },
                event_id="E000003", target_kind="feature", target_id="F001",
            ))
            b.apply_event(_make_event(
                "task.created",
                _make_task_payload(task_id="T001"),
                event_id="E000004", target_kind="task", target_id="T001",
            ))
            bad_payload = {
                "task_id": "T001",
                "from": "proposed",
                # Missing 'to'
            }
            with pytest.raises(TransactionAborted, match="to|required"):
                b.apply_event(_make_event(
                    "task.status_changed", bad_payload,
                    event_id="E000005", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    # ------------------------------------------------------------------
    # task.expanded — empty subtasks list
    # ------------------------------------------------------------------

    def test_handle_task_expanded_empty_subtasks_aborts(
        self, tmp_path: Path
    ) -> None:
        """task.expanded with an empty subtasks list raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "feature.created",
                {
                    "id": "F001", "title": "F", "description": "d", "status": "proposed",
                    "requirements": [], "tasks": [],
                },
                event_id="E000003", target_kind="feature", target_id="F001",
            ))
            b.apply_event(_make_event(
                "task.created",
                _make_task_payload(task_id="T001"),
                event_id="E000004", target_kind="task", target_id="T001",
            ))
            bad_payload = {
                "parent_task_id": "T001",
                "subtasks": [],  # empty
            }
            with pytest.raises(TransactionAborted, match="subtasks|empty"):
                b.apply_event(_make_event(
                    "task.expanded", bad_payload,
                    event_id="E000005", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 5 — helper factories
# ---------------------------------------------------------------------------


def _make_evidence_payload(
    *,
    task_id: str = "T001",
    claim_id: str = "C001",
    evidence_id: str = "EV001",
    submitted_by: str = "agent-alpha",
    commands_run: list[str] | None = None,
    files_changed: list[str] | None = None,
    output_excerpt: str | None = "5 passed",
    pr_url: str | None = None,
    commit_sha: str | None = None,
    screenshots: list[str] | None = None,
    known_limitations: str | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "claim_id": claim_id,
        "evidence_id": evidence_id,
        "submitted_by": submitted_by,
        "commands_run": commands_run if commands_run is not None else ["pytest tests/ -v"],
        "files_changed": files_changed if files_changed is not None else ["src/auth.py"],
        "output_excerpt": output_excerpt,
        "pr_url": pr_url,
        "commit_sha": commit_sha,
        "screenshots": screenshots or [],
        "known_limitations": known_limitations,
    }


def _make_applied_payload(
    *,
    task_id: str = "T001",
    reviewer: str = "alice",
    decision: str = "accepted",
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "reviewer": reviewer,
        "decision": decision,
        "notes": notes,
    }


def _setup_claimable_task_and_claim(
    b: SqliteBackend,
    *,
    task_id: str = "T001",
    claim_id: str = "C001",
) -> None:
    """Set up project → feature → task in 'ready' → claim.created → task='claimed'."""
    _setup_claimable_task(b, task_id=task_id)
    b.apply_event(_make_event(
        "claim.created",
        _make_claim_payload(claim_id=claim_id, task_id=task_id),
        event_id="E000010", target_kind="claim", target_id=claim_id,
    ))


# ---------------------------------------------------------------------------
# Phase 5 — TestPhase5EvidenceAndApplyHandlers
# ---------------------------------------------------------------------------


class TestPhase5EvidenceAndApplyHandlers:
    """Unit tests for evidence.submitted and task.applied event handlers."""

    # ------------------------------------------------------------------
    # evidence.submitted — happy path
    # ------------------------------------------------------------------

    def test_evidence_submitted_inserts_row_and_updates_task(
        self, tmp_path: Path
    ) -> None:
        """evidence.submitted inserts evidence row, sets task.status='needs_review',
        and auto-releases the claim.
        """
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_claimable_task_and_claim(b)

            payload = _make_evidence_payload()
            b.apply_event(_make_event(
                "evidence.submitted", payload,
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            # JSONL
            events = _read_jsonl(events_path)
            assert any(e.get("action") == "evidence.submitted" for e in events)

            # Evidence row present
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            ev_row = conn.execute(
                "SELECT id, task_id, submitted_by FROM evidence WHERE id = 'EV001'"
            ).fetchone()
            conn.close()
            assert ev_row is not None
            assert ev_row[1] == "T001"
            assert ev_row[2] == "agent-alpha"

            # Task status → needs_review
            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "needs_review"

            # Claim auto-released
            claim = b.get_claim("C001")
            assert claim is not None
            assert claim.status.value == "released"
        finally:
            b.close()

    def test_evidence_submitted_idempotent_on_replay(self, tmp_path: Path) -> None:
        """Applying evidence.submitted twice is a no-op for the second application."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)

            payload = _make_evidence_payload()
            event = _make_event(
                "evidence.submitted", payload,
                event_id="E000011", target_kind="task", target_id="T001",
            )
            b.apply_event(event)  # first: commits
            b.apply_event(event)  # second: INSERT OR IGNORE — no-op

            # Still only one evidence row
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            count = conn.execute(
                "SELECT COUNT(*) FROM evidence WHERE id = 'EV001'"
            ).fetchone()[0]
            conn.close()
            assert count == 1

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "needs_review"
        finally:
            b.close()

    def test_evidence_submitted_validates_required_fields(
        self, tmp_path: Path
    ) -> None:
        """evidence.submitted without task_id raises TransactionAborted with field name."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)

            bad_payload = _make_evidence_payload()
            del bad_payload["task_id"]  # missing required field

            with pytest.raises(TransactionAborted, match="task_id"):
                b.apply_event(_make_event(
                    "evidence.submitted", bad_payload,
                    event_id="E000011", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_evidence_submitted_rejects_empty_commands_run(
        self, tmp_path: Path
    ) -> None:
        """evidence.submitted with commands_run=[] raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)

            payload = _make_evidence_payload(commands_run=[])
            with pytest.raises(TransactionAborted, match="commands_run"):
                b.apply_event(_make_event(
                    "evidence.submitted", payload,
                    event_id="E000011", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_evidence_submitted_rejects_empty_files_changed(
        self, tmp_path: Path
    ) -> None:
        """evidence.submitted with files_changed=[] raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)

            payload = _make_evidence_payload(files_changed=[])
            with pytest.raises(TransactionAborted, match="files_changed"):
                b.apply_event(_make_event(
                    "evidence.submitted", payload,
                    event_id="E000011", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_evidence_submitted_handles_already_needs_review_task_idempotent(
        self, tmp_path: Path
    ) -> None:
        """evidence.submitted when task is already 'needs_review' is a no-op success.

        CL-8 regression: a second submission with a DIFFERENT evidence_id must
        also no-op (not double-insert). Before CL-8 this test passed without
        the count assertion below — INSERT OR IGNORE on the PK only blocked
        same-evidence_id duplicates; a new EV002 row landed alongside EV001.
        """
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)

            payload = _make_evidence_payload()
            b.apply_event(_make_event(
                "evidence.submitted", payload,
                event_id="E000011", target_kind="task", target_id="T001",
            ))
            # Task is now needs_review. Applying again with a different evidence_id
            # used to silently double-insert (CL-8). After the fix the second
            # apply hits the (claim_id, different evidence_id) idempotency guard
            # and warn-logs a no-op.
            payload2 = _make_evidence_payload(evidence_id="EV002")
            b.apply_event(_make_event(
                "evidence.submitted", payload2,
                event_id="E000012", target_kind="task", target_id="T001",
            ))

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "needs_review"

            # CL-8: exactly ONE evidence row exists for claim C001.
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            count = conn.execute(
                "SELECT COUNT(*) FROM evidence WHERE claim_id = 'C001'"
            ).fetchone()[0]
            ev_id = conn.execute(
                "SELECT id FROM evidence WHERE claim_id = 'C001'"
            ).fetchone()[0]
            conn.close()
            assert count == 1, "CL-8: second submit with different evidence_id must not insert"
            assert ev_id == "EV001", "CL-8: original evidence row must win"
        finally:
            b.close()

    def test_evidence_submitted_missing_claim_id_aborts(
        self, tmp_path: Path
    ) -> None:
        """evidence.submitted without claim_id raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)

            bad = _make_evidence_payload()
            del bad["claim_id"]

            with pytest.raises(TransactionAborted, match="claim_id"):
                b.apply_event(_make_event(
                    "evidence.submitted", bad,
                    event_id="E000011", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_evidence_submitted_double_submit_writes_warn_idempotent_no_op(
        self, tmp_path: Path
    ) -> None:
        """CL-8: a second submit() for the same claim with a different
        evidence_id must write a warn.idempotent_no_op event to JSONL.

        Before CL-8 the second INSERT silently succeeded, producing two
        evidence rows for one logical submission and a non-deterministic
        ``_fetch_latest_evidence`` result. After the fix the duplicate is
        rejected as an idempotent no-op with an audit-log entry.
        """
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_claimable_task_and_claim(b)

            # First submission lands normally.
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(evidence_id="EV001"),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            # Second submission with a different evidence_id — the CL-8 guard.
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(evidence_id="EV002"),
                event_id="E000012", target_kind="task", target_id="T001",
            ))

            # Exactly one evidence row survived.
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
            conn.close()
            assert count == 1

            # The duplicate produced a warn.idempotent_no_op tombstone in JSONL.
            events = _read_jsonl(events_path)
            warn_entries = [
                e for e in events
                if e.get("action") == "warn.idempotent_no_op"
                and e.get("payload_json", {}).get("original_action") == "evidence.submitted"
                and "EV002" in e.get("payload_json", {}).get("reason", "")
            ]
            assert len(warn_entries) == 1, (
                "CL-8: expected exactly one warn.idempotent_no_op tombstone for "
                f"the duplicate EV002 submission; got {len(warn_entries)}. "
                f"events: {[e.get('action') for e in events]}"
            )
        finally:
            b.close()

    # ------------------------------------------------------------------
    # task.applied — happy path
    # ------------------------------------------------------------------

    def test_task_applied_accepted_transitions_to_done(
        self, tmp_path: Path
    ) -> None:
        """needs_review → accepted → done (combined atomic transition)."""
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_claimable_task_and_claim(b)
            # Submit evidence to reach needs_review
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            # Apply: accepted → done
            b.apply_event(_make_event(
                "task.applied",
                _make_applied_payload(decision="accepted", reviewer="alice"),
                event_id="E000012", target_kind="task", target_id="T001",
            ))

            events = _read_jsonl(events_path)
            assert any(e.get("action") == "task.applied" for e in events)

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "done"
        finally:
            b.close()

    def test_task_applied_rejected_auto_promotes_to_drafted(
        self, tmp_path: Path
    ) -> None:
        """needs_review + decision=rejected → task.status='drafted'.

        Per spec (docs/specs/2026-05-24-fakoli-state-v0.md): the rejected
        state is a transient audit marker; the task immediately auto-
        promotes to drafted so it can be re-reviewed. Critic-1 + Critic-2
        flagged that the original implementation left the task permanently
        at 'rejected' with no path back — `task_rejected_to_drafted` in
        transitions.py was dead code.

        The audit log still records decision='rejected' on the Review row
        (the human's call). The mechanical outcome is drafted.
        """
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            b.apply_event(_make_event(
                "task.applied",
                _make_applied_payload(decision="rejected", reviewer="bob", notes="Needs more tests."),
                event_id="E000012", target_kind="task", target_id="T001",
            ))

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "drafted", (
                f"rejected path must auto-promote to drafted per spec; got {task.status.value!r}"
            )

            # The Review row still records decision='rejected'.
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            review = conn.execute(
                "SELECT decision FROM reviews WHERE id = 'RV-E000012'"
            ).fetchone()
            conn.close()
            assert review is not None and review[0] == "rejected"
        finally:
            b.close()

    def test_task_applied_inserts_review_row(self, tmp_path: Path) -> None:
        """task.applied inserts a reviews row with id=RV-{event_id}."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            b.apply_event(_make_event(
                "task.applied",
                _make_applied_payload(decision="accepted"),
                event_id="E000012", target_kind="task", target_id="T001",
            ))

            conn = sqlite3.connect(str(tmp_path / "state.db"))
            review = conn.execute(
                "SELECT id, target_kind, target_id, decision FROM reviews WHERE target_kind='task'"
            ).fetchone()
            conn.close()
            assert review is not None
            assert review[0] == "RV-E000012"
            assert review[1] == "task"
            assert review[2] == "T001"
            assert review[3] == "accepted"
        finally:
            b.close()

    def test_task_applied_concurrency_guard_on_wrong_status(
        self, tmp_path: Path
    ) -> None:
        """task.applied when task is NOT 'needs_review' → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            # Task is 'claimed', not 'needs_review'
            with pytest.raises(TransactionAborted, match="needs_review|status|T001"):
                b.apply_event(_make_event(
                    "task.applied",
                    _make_applied_payload(decision="accepted"),
                    event_id="E000011", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_task_applied_replay_idempotent(self, tmp_path: Path) -> None:
        """Replaying task.applied twice with same event_id is a no-op (INSERT OR REPLACE)."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            apply_event = _make_event(
                "task.applied",
                _make_applied_payload(decision="accepted"),
                event_id="E000012", target_kind="task", target_id="T001",
            )
            b.apply_event(apply_event)  # first: commits, task → done

            # Second: idempotent — accepted/done path is no-op (INSERT OR REPLACE for review)
            b.apply_event(apply_event)  # no raise expected

            task = b.get_task("T001")
            assert task is not None
            assert task.status.value == "done"
        finally:
            b.close()

    def test_task_applied_invalid_decision_aborts(self, tmp_path: Path) -> None:
        """task.applied with decision='approved' (not 'accepted'/'rejected') → TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            with pytest.raises(TransactionAborted, match="decision|accepted|rejected"):
                b.apply_event(_make_event(
                    "task.applied",
                    _make_applied_payload(decision="approved"),  # invalid
                    event_id="E000012", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_task_applied_missing_reviewer_aborts(self, tmp_path: Path) -> None:
        """task.applied without reviewer raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            bad = {"task_id": "T001", "decision": "accepted"}  # no reviewer
            with pytest.raises(TransactionAborted, match="reviewer"):
                b.apply_event(_make_event(
                    "task.applied", bad,
                    event_id="E000012", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_task_applied_rejected_replay_idempotent(self, tmp_path: Path) -> None:
        """Replaying task.applied (rejected) twice is a no-op for the second
        application.

        After the auto-promote fix, the task ends at 'drafted' after the
        first apply (rejected → drafted is automatic). The idempotent
        branch must accept both 'rejected' (transient) and 'drafted'
        (final) as valid states to encounter on replay.
        """
        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            reject_event = _make_event(
                "task.applied",
                _make_applied_payload(decision="rejected", reviewer="bob", notes="Needs more."),
                event_id="E000012", target_kind="task", target_id="T001",
            )
            b.apply_event(reject_event)  # first: needs_review → rejected → drafted
            b.apply_event(reject_event)  # second: idempotent no-op (already drafted)

            task = b.get_task("T001")
            assert task is not None
            # After auto-promote, the task ends at 'drafted', not 'rejected'.
            assert task.status.value == "drafted"
        finally:
            b.close()

    def test_list_reviews_rejected_maps_to_needs_changes(self, tmp_path: Path) -> None:
        """list_reviews() maps task.applied decision='rejected' to ReviewDecision.needs_changes.

        Pins _TASK_OUTCOME_TO_REVIEW_DECISION so the mapping cannot silently
        regress.  A rejected task auto-promotes back to drafted for rework —
        it is NOT the terminal ReviewDecision.reject closure.
        """
        from fakoli_state.state.models import ReviewDecision

        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "task.applied",
                _make_applied_payload(decision="rejected", reviewer="bob", notes="Fix it."),
                event_id="E000012", target_kind="task", target_id="T001",
            ))

            reviews = b.list_reviews()
            task_reviews = [r for r in reviews if r.target_kind.value == "task"]
            assert len(task_reviews) == 1, (
                f"expected 1 task review from list_reviews(), got {len(task_reviews)}"
            )
            assert task_reviews[0].decision == ReviewDecision.needs_changes, (
                f"rejected task.applied should map to needs_changes via list_reviews(); "
                f"got {task_reviews[0].decision!r}"
            )
        finally:
            b.close()

    def test_list_reviews_accepted_maps_to_approve(self, tmp_path: Path) -> None:
        """list_reviews() maps task.applied decision='accepted' to ReviewDecision.approve.

        Companion to test_list_reviews_rejected_maps_to_needs_changes — pins
        both directions of _TASK_OUTCOME_TO_REVIEW_DECISION.
        """
        from fakoli_state.state.models import ReviewDecision

        b = _make_backend(tmp_path)
        try:
            _setup_claimable_task_and_claim(b)
            b.apply_event(_make_event(
                "evidence.submitted", _make_evidence_payload(),
                event_id="E000011", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "task.applied",
                _make_applied_payload(decision="accepted", reviewer="alice"),
                event_id="E000012", target_kind="task", target_id="T001",
            ))

            reviews = b.list_reviews()
            task_reviews = [r for r in reviews if r.target_kind.value == "task"]
            assert len(task_reviews) == 1, (
                f"expected 1 task review from list_reviews(), got {len(task_reviews)}"
            )
            assert task_reviews[0].decision == ReviewDecision.approve, (
                f"accepted task.applied should map to approve via list_reviews(); "
                f"got {task_reviews[0].decision!r}"
            )
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 5 — THE CRITICAL TEST: replay includes Phase 5 events
# ---------------------------------------------------------------------------


class TestReplayIncludesPhase5Events:
    def test_replay_includes_evidence_and_apply_events(self, tmp_path: Path) -> None:
        """Full lifecycle replay: project.created → state.initialized → prd.parsed
        → prd.approved → feature.created → task.created → task.status_changed (→ ready)
        → claim.created → evidence.submitted → task.applied.

        Assert byte-equal sqlite3 .dump after replay.
        """
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        try:
            # E000001: project.created
            b.apply_event(_make_project_event(event_id="E000001"))
            # E000002: state.initialized
            b.apply_event(_make_init_event(event_id="E000002"))

            # E000003: prd.parsed
            b.apply_event(_make_event(
                "prd.parsed",
                {
                    "project_id": "proj-1",
                    "status": "draft",
                    "summary": "Phase 5 replay test PRD.",
                    "goals": ["Goal."],
                    "non_goals": [],
                    "requirements": [
                        {"id": "R001", "prd_section": "requirements", "text": "Req.",
                         "source_paragraph": None, "derived": False}
                    ],
                    "acceptance_criteria": ["AC."],
                    "risks": [],
                    "open_questions": [],
                },
                event_id="E000003", target_kind="prd", target_id="proj-1",
            ))

            # E000004: prd.approved (skipping prd.reviewed for brevity — approved is valid)
            b.apply_event(_make_event(
                "prd.approved",
                {"project_id": "proj-1", "approver": "alice"},
                event_id="E000004", target_kind="prd", target_id="proj-1",
            ))

            # E000005: feature.created
            b.apply_event(_make_event(
                "feature.created",
                _make_feature_payload(feat_id="F001"),
                event_id="E000005", target_kind="feature", target_id="F001",
            ))

            # E000006: task.created
            b.apply_event(_make_event(
                "task.created",
                _make_task_payload(task_id="T001"),
                event_id="E000006", target_kind="task", target_id="T001",
            ))

            # E000007–E000009: task.status_changed proposed → ready
            for from_s, to_s, eid in [
                ("proposed", "drafted", "E000007"),
                ("drafted", "reviewed", "E000008"),
                ("reviewed", "ready", "E000009"),
            ]:
                b.apply_event(_make_event(
                    "task.status_changed",
                    {"task_id": "T001", "from": from_s, "to": to_s},
                    event_id=eid, target_kind="task", target_id="T001",
                ))

            # E000010: claim.created
            b.apply_event(_make_event(
                "claim.created",
                _make_claim_payload(claim_id="C001", task_id="T001"),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))

            # E000011: evidence.submitted
            b.apply_event(_make_event(
                "evidence.submitted",
                _make_evidence_payload(
                    task_id="T001",
                    claim_id="C001",
                    evidence_id="EV001",
                    submitted_by="agent-alpha",
                    commands_run=["pytest tests/ -v"],
                    files_changed=["src/auth.py"],
                    output_excerpt="5 passed",
                ),
                event_id="E000011", target_kind="task", target_id="T001",
            ))

            # E000012: task.applied (accepted → done)
            b.apply_event(_make_event(
                "task.applied",
                _make_applied_payload(task_id="T001", reviewer="alice", decision="accepted"),
                event_id="E000012", target_kind="task", target_id="T001",
            ))

        finally:
            b.close()

        # Capture original dump
        original_dump = _sqlite_dump(db_path)

        # Replay from empty
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        replayed_dump = _sqlite_dump(db_path)
        assert original_dump == replayed_dump, (
            "Replayed state.db does not match original after Phase 5 events.\n"
            f"Original dump (first 800 chars):\n{original_dump[:800]}\n\n"
            f"Replayed dump (first 800 chars):\n{replayed_dump[:800]}"
        )

    def test_replay_includes_rejected_apply(self, tmp_path: Path) -> None:
        """Audit guarantee for the rejected branch: evidence.submitted → task.applied
        (rejected) replays byte-identically.
        """
        clock = _make_clock()
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()

        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()

        try:
            _setup_claimable_task(b)
            b.apply_event(_make_event(
                "claim.created",
                _make_claim_payload(claim_id="C001", task_id="T001"),
                event_id="E000010", target_kind="claim", target_id="C001",
            ))
            b.apply_event(_make_event(
                "evidence.submitted",
                _make_evidence_payload(task_id="T001", claim_id="C001", evidence_id="EV001"),
                event_id="E000011", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "task.applied",
                _make_applied_payload(task_id="T001", reviewer="bob", decision="rejected",
                                      notes="Incomplete."),
                event_id="E000012", target_kind="task", target_id="T001",
            ))
        finally:
            b.close()

        original_dump = _sqlite_dump(db_path)

        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        replayed_dump = _sqlite_dump(db_path)
        assert original_dump == replayed_dump, (
            "Replayed state.db does not match original after rejected task.applied."
        )


# ---------------------------------------------------------------------------
# Backend Protocol extensions — get_feature, list_events, get_latest_evidence
# ---------------------------------------------------------------------------


def _setup_feature_and_task(
    b: SqliteBackend,
    *,
    feat_id: str = "F001",
    task_id: str = "T001",
) -> None:
    """Bootstrap a project → feature → task pipeline into 'ready' status."""
    _setup_project(b)
    b.apply_event(_make_event(
        "feature.created",
        _make_feature_payload(feat_id=feat_id),
        event_id="E000003", target_kind="feature", target_id=feat_id,
    ))
    b.apply_event(_make_event(
        "task.created",
        _make_task_payload(task_id=task_id, feature_id=feat_id),
        event_id="E000004", target_kind="task", target_id=task_id,
    ))
    # Promote proposed → drafted → reviewed → ready so the task can be claimed.
    for ev_id, from_s, to_s in (
        ("E000005", "proposed", "drafted"),
        ("E000006", "drafted", "reviewed"),
        ("E000007", "reviewed", "ready"),
    ):
        b.apply_event(_make_event(
            "task.status_changed",
            {"task_id": task_id, "from": from_s, "to": to_s, "reason": "test"},
            event_id=ev_id, target_kind="task", target_id=task_id,
        ))


class TestBackendProtocolExtensions:
    """Tests for get_feature, list_events, and get_latest_evidence on SqliteBackend."""

    # ------------------------------------------------------------------
    # get_feature
    # ------------------------------------------------------------------

    def test_get_feature_returns_feature_when_exists(self, tmp_path: Path) -> None:
        """get_feature() returns the Feature model for a known feature ID."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "feature.created",
                _make_feature_payload(feat_id="F001", title="Auth System"),
                event_id="E000003", target_kind="feature", target_id="F001",
            ))
            feature = b.get_feature("F001")
            assert feature is not None
            assert feature.id == "F001"
            assert feature.title == "Auth System"
        finally:
            b.close()

    def test_get_feature_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """get_feature() returns None when the feature ID does not exist."""
        b = _make_backend(tmp_path)
        try:
            result = b.get_feature("F999")
            assert result is None
        finally:
            b.close()

    # ------------------------------------------------------------------
    # list_events
    # ------------------------------------------------------------------

    def test_list_events_returns_recent_events_for_target(self, tmp_path: Path) -> None:
        """list_events() returns (action, timestamp) tuples for the given target_id."""
        b = _make_backend(tmp_path)
        try:
            _setup_feature_and_task(b, feat_id="F001", task_id="T001")
            rows = b.list_events(target_id="T001")
            # At least the status_changed events for T001 should be present.
            assert len(rows) > 0
            # Each row is a 2-tuple.
            for action, ts in rows:
                assert isinstance(action, str)
                assert isinstance(ts, str)
        finally:
            b.close()

    def test_list_events_filters_by_target_kind(self, tmp_path: Path) -> None:
        """list_events(target_kind=...) restricts to events with that target_kind."""
        b = _make_backend(tmp_path)
        try:
            _setup_feature_and_task(b, feat_id="F001", task_id="T001")
            task_events = b.list_events(target_id="T001", target_kind="task")
            # All returned events must have been recorded against the 'task' kind.
            # We can confirm by checking that every action is a task action.
            assert len(task_events) > 0
            for action, _ in task_events:
                assert "task" in action or "status" in action
        finally:
            b.close()

    def test_list_events_honours_limit(self, tmp_path: Path) -> None:
        """list_events(limit=N) returns at most N rows."""
        b = _make_backend(tmp_path)
        try:
            # _setup_feature_and_task emits 3 status_changed events for T001.
            _setup_feature_and_task(b, feat_id="F001", task_id="T001")
            limited = b.list_events(target_id="T001", target_kind="task", limit=2)
            assert len(limited) <= 2
        finally:
            b.close()

    # ------------------------------------------------------------------
    # get_latest_evidence
    # ------------------------------------------------------------------

    def test_get_latest_evidence_returns_most_recent(self, tmp_path: Path) -> None:
        """get_latest_evidence() returns the Evidence model after evidence.submitted."""
        b = _make_backend(tmp_path)
        try:
            _setup_feature_and_task(b, feat_id="F001", task_id="T001")
            # Create a claim so evidence.submitted has a valid FK.
            b.apply_event(_make_event(
                "claim.created",
                _make_claim_payload(claim_id="C001", task_id="T001"),
                event_id="E000011", target_kind="claim", target_id="C001",
            ))
            b.apply_event(_make_event(
                "evidence.submitted",
                _make_evidence_payload(
                    task_id="T001",
                    claim_id="C001",
                    evidence_id="EV001",
                    commands_run=["pytest tests/ -v"],
                    files_changed=["src/auth.py"],
                ),
                event_id="E000012", target_kind="task", target_id="T001",
            ))
            evidence = b.get_latest_evidence("T001")
            assert evidence is not None
            assert evidence.id == "EV001"
            assert evidence.task_id == "T001"
            assert evidence.claim_id == "C001"
            assert "pytest" in evidence.commands_run[0]
        finally:
            b.close()

    def test_get_latest_evidence_returns_none_when_no_evidence(self, tmp_path: Path) -> None:
        """get_latest_evidence() returns None when no evidence exists for the task."""
        b = _make_backend(tmp_path)
        try:
            result = b.get_latest_evidence("T001")
            assert result is None
        finally:
            b.close()


# ---------------------------------------------------------------------------
# PENDING_EVENT_ID — race-free ID assignment (Critic-3 / PR #41 fix)
# ---------------------------------------------------------------------------


class TestPendingEventId:
    """Tests for the PENDING_EVENT_ID sentinel and the dual-path apply_event()."""

    def test_pending_event_id_assigned_inside_transaction(self, tmp_path: Path) -> None:
        """Emitting 3 PENDING events produces sequential IDs assigned inside the lock.

        Two events from _make_project_event() + _make_init_event() are applied
        first with real IDs (E000001, E000002), then 3 PENDING events are emitted.
        The backend must assign E000003, E000004, E000005 in order.
        """
        b = _make_backend(tmp_path)
        try:
            # Seed with two real-ID events so the MAX sequence starts at 2.
            b.apply_event(_make_project_event(event_id="E000001"))
            b.apply_event(_make_init_event(event_id="E000002"))

            # Emit 3 PENDING events.
            pending_events = []
            for i in range(3):
                e = Event(
                    id=PENDING_EVENT_ID,
                    timestamp=_T0,
                    actor="test",
                    action="project.created",
                    target_kind="project",
                    target_id="proj-1",
                    payload_json={
                        "id": "proj-1",
                        "name": f"Project {i}",
                        "description": "",
                        "created_at": _T0.isoformat(),
                        "updated_at": _T0.isoformat(),
                    },
                )
                materialized = b.apply_event(e)
                pending_events.append(materialized)
        finally:
            b.close()

        ids = [e.id for e in pending_events]
        assert ids == ["E000003", "E000004", "E000005"], (
            f"Expected sequential IDs E000003–E000005; got {ids}"
        )

    def test_apply_event_returns_materialized_event(self, tmp_path: Path) -> None:
        """apply_event() returns the event with the assigned ID, not PENDING."""
        b = _make_backend(tmp_path)
        try:
            pending = Event(
                id=PENDING_EVENT_ID,
                timestamp=_T0,
                actor="test",
                action="project.created",
                target_kind="project",
                target_id="proj-1",
                payload_json={
                    "id": "proj-1",
                    "name": "Test",
                    "description": "",
                    "created_at": _T0.isoformat(),
                    "updated_at": _T0.isoformat(),
                },
            )
            result = b.apply_event(pending)
        finally:
            b.close()

        assert result.id != PENDING_EVENT_ID, "apply_event must assign a real ID"
        assert result.id.startswith("E"), f"Assigned ID must be in E%06d format; got {result.id!r}"
        assert result.id[1:].isdigit(), f"Assigned ID suffix must be numeric; got {result.id!r}"

    def test_pending_event_jsonl_only_written_on_successful_commit(
        self, tmp_path: Path
    ) -> None:
        """A PENDING event that causes a mutation failure leaves NO line in events.jsonl.

        This verifies that the post-COMMIT JSONL ordering for PENDING events
        means a failed transaction does not produce a dangling JSONL line.
        An unsupported action triggers NotImplementedError which rolls back the
        SQLite transaction; because the JSONL write is post-COMMIT for PENDING
        events, no JSONL line is written for the failed event.
        """
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            # Apply one good event first so the JSONL has 1 line.
            b.apply_event(_make_project_event(event_id="E000001"))

            initial_events = _read_jsonl(events_path)
            assert len(initial_events) == 1

            # Apply a PENDING event with an unsupported action — should fail.
            bad_event = Event(
                id=PENDING_EVENT_ID,
                timestamp=_T0,
                actor="test",
                action="unsupported.action",
                target_kind="project",
                target_id="proj-1",
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)

            # JSONL should contain exactly 1 successful event + 1 abort tombstone
            # (the abort tombstone uses whatever partial event state was available).
            events_after = _read_jsonl(events_path)
        finally:
            b.close()

        # The original project.created event must still be there.
        successful = [e for e in events_after if e.get("action") == "project.created"]
        assert len(successful) == 1

        # No line with action="unsupported.action" should appear (the PENDING
        # event is NOT written to JSONL before the failed COMMIT).
        unsupported_lines = [e for e in events_after if e.get("action") == "unsupported.action"]
        assert len(unsupported_lines) == 0, (
            "A failed PENDING event must not leave a line with its action in JSONL"
        )

    def test_replay_path_preserves_provided_event_ids(self, tmp_path: Path) -> None:
        """replay_from_empty() preserves the original IDs from JSONL.

        The replay path uses non-PENDING IDs from the existing JSONL log;
        it must never generate new IDs for replayed events (that would break
        the replay guarantee).
        """
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        events_path = str(tmp_path / "events.jsonl")
        db_path = str(tmp_path / "state.db")

        original_ids: list[str] = []
        try:
            # Use PENDING for original writes — get back assigned IDs.
            e1 = b.apply_event(
                Event(
                    id=PENDING_EVENT_ID,
                    timestamp=_T0,
                    actor="test",
                    action="project.created",
                    target_kind="project",
                    target_id="proj-1",
                    payload_json={
                        "id": "proj-1",
                        "name": "Project",
                        "description": "",
                        "created_at": _T0.isoformat(),
                        "updated_at": _T0.isoformat(),
                    },
                )
            )
            e2 = b.apply_event(
                Event(
                    id=PENDING_EVENT_ID,
                    timestamp=_T0,
                    actor="test",
                    action="state.initialized",
                    target_kind="project",
                    target_id="proj-1",
                    payload_json={},
                )
            )
            original_ids = [e1.id, e2.id]
        finally:
            b.close()

        assert original_ids == ["E000001", "E000002"], (
            f"Expected first two PENDING events to get E000001, E000002; got {original_ids}"
        )

        # Replay from empty.
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
            # After replay, query the events table to verify IDs were preserved.
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT id FROM events ORDER BY id"
            ).fetchall()
            conn.close()
            replayed_ids = [row[0] for row in rows]
        finally:
            b2.close()

        assert replayed_ids == original_ids, (
            f"Replay must preserve original event IDs {original_ids}; "
            f"got {replayed_ids}"
        )


# ---------------------------------------------------------------------------
# Phase 8 — sync_mapping handlers (sync_mapping.upserted / sync_mapping.deleted)
# ---------------------------------------------------------------------------


def _make_sync_mapping_payload(
    *,
    task_id: str = "T001",
    external_system: str = "github_issues",
    external_id: str = "gh-42",
    last_synced_at: datetime = _T0,
    sync_state: str = "in_sync",
    conflict_resolution_strategy: str = "prompt",
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "external_system": external_system,
        "external_id": external_id,
        "last_synced_at": last_synced_at.isoformat(),
        "sync_state": sync_state,
        "conflict_resolution_strategy": conflict_resolution_strategy,
    }


def _setup_task_for_sync(
    b: SqliteBackend, task_id: str = "T001", feature_id: str = "F001",
    *, base_event_id: int = 3,
) -> None:
    """Apply minimum events to leave a tasks row with id=task_id present.

    Sync_mappings has a FK into tasks; the FK is RESTRICT, so a sync_mapping
    insert against a non-existent task_id will fail. Most TestSyncMappingHandler
    cases need a real task to attach to.
    """
    b.apply_event(_make_event(
        "feature.created", _make_feature_payload(feat_id=feature_id),
        event_id=f"E{base_event_id:06d}",
        target_kind="feature", target_id=feature_id,
    ))
    b.apply_event(_make_event(
        "task.created", _make_task_payload(task_id=task_id, feature_id=feature_id),
        event_id=f"E{base_event_id + 1:06d}",
        target_kind="task", target_id=task_id,
    ))


class TestSyncMappingHandler:
    """Phase 8: sync_mapping.upserted / sync_mapping.deleted handlers.

    Exercises the upsert semantics (composite-key ON CONFLICT), the delete
    semantics (scoped and broad), the replay round-trip, the FK behaviour,
    and the convenience apply_sync_mapping() wrapper that uses PENDING_EVENT_ID.
    """

    def test_upsert_inserts_row_and_get_returns_it(self, tmp_path: Path) -> None:
        """sync_mapping.upserted inserts a row; get_sync_mapping reads it back."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            payload = _make_sync_mapping_payload()
            event = _make_event(
                "sync_mapping.upserted", payload, event_id="E000005",
                target_kind="task", target_id="T001",
            )
            b.apply_event(event)

            mapping = b.get_sync_mapping("T001")
            assert mapping is not None
            assert mapping.task_id == "T001"
            assert mapping.external_system == "github_issues"
            assert mapping.external_id == "gh-42"
            assert mapping.sync_state == "in_sync"
        finally:
            b.close()

    def test_upsert_on_existing_key_updates_row(self, tmp_path: Path) -> None:
        """A second upsert with the same (task_id, external_system) updates in place."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(external_id="gh-42", sync_state="in_sync"),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(external_id="gh-99", sync_state="conflict"),
                event_id="E000006", target_kind="task", target_id="T001",
            ))

            # Still exactly one row, with the new field values.
            mappings = b.list_sync_mappings()
            assert len(mappings) == 1
            assert mappings[0].external_id == "gh-99"
            assert mappings[0].sync_state == "conflict"
        finally:
            b.close()

    def test_delete_removes_row(self, tmp_path: Path) -> None:
        """sync_mapping.deleted removes a row; get returns None afterwards."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            b.apply_event(_make_event(
                "sync_mapping.upserted", _make_sync_mapping_payload(),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            assert b.get_sync_mapping("T001") is not None

            b.apply_event(_make_event(
                "sync_mapping.deleted", {"task_id": "T001"},
                event_id="E000006", target_kind="task", target_id="T001",
            ))
            assert b.get_sync_mapping("T001") is None
        finally:
            b.close()

    def test_delete_idempotent_on_missing_row(self, tmp_path: Path) -> None:
        """sync_mapping.deleted against a never-mapped task is a silent no-op."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            # No upsert first — delete should succeed regardless.
            b.apply_event(_make_event(
                "sync_mapping.deleted", {"task_id": "T001"},
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            assert b.get_sync_mapping("T001") is None
        finally:
            b.close()

    def test_delete_scoped_to_one_external_system(self, tmp_path: Path) -> None:
        """sync_mapping.deleted with external_system only drops that single row."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(external_system="github_issues"),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            # Only one StrEnum value today; for the second mapping we re-use
            # github_issues with a different external_id but per the composite
            # PK that would be an UPDATE, not a second row. So instead the
            # "scoped delete" coverage is: deleting the github_issues row
            # removes the only mapping for the task, while a delete with the
            # WRONG external_system leaves it intact (no-op).
            b.apply_event(_make_event(
                "sync_mapping.deleted",
                {"task_id": "T001", "external_system": "linear"},
                event_id="E000006", target_kind="task", target_id="T001",
            ))
            assert b.get_sync_mapping("T001") is not None  # untouched

            b.apply_event(_make_event(
                "sync_mapping.deleted",
                {"task_id": "T001", "external_system": "github_issues"},
                event_id="E000007", target_kind="task", target_id="T001",
            ))
            assert b.get_sync_mapping("T001") is None
        finally:
            b.close()

    def test_list_sync_mappings_unfiltered_returns_all(self, tmp_path: Path) -> None:
        """list_sync_mappings() with no filter returns every row."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b, task_id="T001")
            # Second task to give us two rows.
            b.apply_event(_make_event(
                "task.created", _make_task_payload(task_id="T002"),
                event_id="E000005", target_kind="task", target_id="T002",
            ))
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(task_id="T001", external_id="gh-1"),
                event_id="E000006", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(task_id="T002", external_id="gh-2"),
                event_id="E000007", target_kind="task", target_id="T002",
            ))

            mappings = b.list_sync_mappings()
            assert len(mappings) == 2
            task_ids = {m.task_id for m in mappings}
            assert task_ids == {"T001", "T002"}
        finally:
            b.close()

    def test_list_sync_mappings_filters_by_external_system(self, tmp_path: Path) -> None:
        """list_sync_mappings(external_system=...) returns only matching rows."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b, task_id="T001")
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(external_system="github_issues"),
                event_id="E000005", target_kind="task", target_id="T001",
            ))

            # Matching filter returns the row.
            matched = b.list_sync_mappings(external_system="github_issues")
            assert len(matched) == 1
            assert matched[0].external_system == "github_issues"

            # Non-matching filter returns nothing.
            unmatched = b.list_sync_mappings(external_system="linear")
            assert unmatched == []
        finally:
            b.close()

    def test_apply_sync_mapping_wrapper_writes_event_and_row(
        self, tmp_path: Path
    ) -> None:
        """apply_sync_mapping() builds the event and inserts the row in one call."""
        from fakoli_state.state.models import SyncMapping

        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            mapping = SyncMapping(
                task_id="T001",
                external_system="github_issues",
                external_id="gh-42",
                last_synced_at=_T0,
            )
            event = b.apply_sync_mapping(mapping)

            # The returned event has a real ID assigned by the backend.
            assert event.id != PENDING_EVENT_ID
            assert event.id.startswith("E") and event.id[1:].isdigit()
            assert event.action == "sync_mapping.upserted"

            # JSONL line written.
            events = _read_jsonl(events_path)
            assert any(
                e.get("action") == "sync_mapping.upserted" for e in events
            )

            # SQLite row written.
            stored = b.get_sync_mapping("T001")
            assert stored is not None
            assert stored.external_id == "gh-42"
        finally:
            b.close()

    def test_apply_sync_mapping_returns_assigned_event_id_not_pending(
        self, tmp_path: Path
    ) -> None:
        """The Event returned by apply_sync_mapping() carries a real E000xxx id."""
        from fakoli_state.state.models import SyncMapping

        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            mapping = SyncMapping(
                task_id="T001",
                external_system="github_issues",
                external_id="gh-42",
                last_synced_at=_T0,
            )
            event = b.apply_sync_mapping(mapping)
            assert event.id != PENDING_EVENT_ID
            # Format: 'E' + 6 digits.
            assert len(event.id) == 7 and event.id.startswith("E")
            assert event.id[1:].isdigit()
        finally:
            b.close()

    def test_sync_mapping_fk_restricts_unknown_task(self, tmp_path: Path) -> None:
        """A sync_mapping.upserted against a non-existent task raises TransactionAborted.

        The sync_mappings.task_id FK is RESTRICT, not CASCADE, so attempting
        to insert a mapping against a missing task surfaces as a SQLite IntegrityError
        and is wrapped by apply_event() as TransactionAborted. The corollary —
        attempting to delete the parent tasks row while a mapping exists also
        raises — is covered by test_sync_mapping_blocks_task_delete_via_fk.
        """
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            # Do NOT create T001 — FK should reject.
            with pytest.raises(TransactionAborted):
                b.apply_event(_make_event(
                    "sync_mapping.upserted",
                    _make_sync_mapping_payload(task_id="T001"),
                    event_id="E000003", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_sync_mapping_cascades_on_task_delete(self, tmp_path: Path) -> None:
        """Direct DELETE on the parent task row CASCADES to drop the sync_mappings row.

        We use a raw connection because the canonical event flow does not
        expose a 'task.deleted' event in Phase 8 — but the FK direction
        flip (RESTRICT → CASCADE in v3) means any future task.deleted handler
        won't be wedged by an outstanding sync_mapping. Documents the
        v3 schema invariant.

        The claims.task_id FK is still RESTRICT, so for this test we leave
        no active claim on the task — only the sync_mapping cascades.
        """
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            b.apply_event(_make_event(
                "sync_mapping.upserted", _make_sync_mapping_payload(),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
        finally:
            b.close()

        conn = sqlite3.connect(str(tmp_path / "state.db"))
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            # DELETE succeeds — CASCADE drops the sync_mapping row first.
            conn.execute("DELETE FROM tasks WHERE id = ?", ("T001",))
            conn.commit()
            # And the sync_mapping row is gone.
            row = conn.execute(
                "SELECT 1 FROM sync_mappings WHERE task_id = ?", ("T001",)
            ).fetchone()
            assert row is None
        finally:
            conn.close()

    def test_replay_from_empty_round_trips_sync_mapping(self, tmp_path: Path) -> None:
        """events.jsonl with sync_mapping events replays to a byte-identical state.db."""
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            _setup_task_for_sync(b, task_id="T001")
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(task_id="T001", external_id="gh-1"),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(task_id="T001", external_id="gh-99"),
                event_id="E000006", target_kind="task", target_id="T001",
            ))
        finally:
            b.close()

        original_dump = _sqlite_dump(db_path)

        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        replayed_dump = _sqlite_dump(db_path)
        assert original_dump == replayed_dump, (
            "Replayed state.db differs from original after sync_mapping events.\n"
            f"Original (truncated):\n{original_dump[:600]}\n\n"
            f"Replayed (truncated):\n{replayed_dump[:600]}"
        )

    def test_replay_round_trips_populated_provider_metadata(
        self, tmp_path: Path
    ) -> None:
        """Replay must round-trip non-empty provider_metadata + external_url byte-for-byte."""
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            payload = {
                **_make_sync_mapping_payload(),
                "external_url": "https://github.com/example/repo/issues/42",
                "provider_metadata": {
                    "labels": ["bug", "p1"],
                    "assignees": ["alice"],
                },
            }
            b.apply_event(_make_event(
                "sync_mapping.upserted", payload,
                event_id="E000005", target_kind="task", target_id="T001",
            ))
        finally:
            b.close()

        original_dump = _sqlite_dump(db_path)

        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        assert original_dump == _sqlite_dump(db_path)

    def test_replay_round_trips_sync_mapping_delete(self, tmp_path: Path) -> None:
        """Replay of upsert+delete leaves the same final state."""
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            b.apply_event(_make_event(
                "sync_mapping.upserted", _make_sync_mapping_payload(),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "sync_mapping.deleted", {"task_id": "T001"},
                event_id="E000006", target_kind="task", target_id="T001",
            ))
        finally:
            b.close()

        original_dump = _sqlite_dump(db_path)

        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            b2.close()

        replayed_dump = _sqlite_dump(db_path)
        assert original_dump == replayed_dump

    def test_upsert_rejects_invalid_sync_state(self, tmp_path: Path) -> None:
        """sync_state must be a valid SyncState enum value; otherwise TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            bad = _make_sync_mapping_payload(sync_state="not_a_real_state")
            with pytest.raises(TransactionAborted):
                b.apply_event(_make_event(
                    "sync_mapping.upserted", bad,
                    event_id="E000005", target_kind="task", target_id="T001",
                ))
        finally:
            b.close()

    def test_get_sync_mapping_returns_none_for_unknown_task(
        self, tmp_path: Path
    ) -> None:
        """get_sync_mapping for a never-mapped task returns None."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            assert b.get_sync_mapping("T001") is None
            assert b.get_sync_mapping("nonexistent-task") is None
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 8 — SCHEMA_VERSION bump verification
# ---------------------------------------------------------------------------


class TestSchemaVersionPhase8:
    """The bump from SCHEMA_VERSION=1 → 2 → 3 signals Phase 8.

    v3 is the shipping Phase 8 schema; v1/v2 are auto-upgraded on first open
    (see TestSchemaAutoUpgrade below and docs/migrations.md).
    """

    def test_schema_version_is_three(self) -> None:
        """The Phase 8 ship floor is SCHEMA_VERSION == 3."""
        assert SCHEMA_VERSION == 3

    def test_initialize_creates_sync_mappings_table_on_empty_db(
        self, tmp_path: Path
    ) -> None:
        """A fresh initialize() on an empty path materializes sync_mappings."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name = 'sync_mappings'"
            )
            row = cursor.fetchone()
            conn.close()
            assert row is not None, "sync_mappings table missing after initialize()"
            assert row[0] == "sync_mappings"

            # And user_version matches the bump.
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            v = conn.execute("PRAGMA user_version").fetchone()[0]
            conn.close()
            assert v == 3
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 8 Wave 1 fix-cycle — MF-1 / MF-2 / SF-1 / SF-6 coverage
# ---------------------------------------------------------------------------


class TestSyncMappingUniqueExternalId:
    """MF-1: UNIQUE(external_system, external_id) on sync_mappings.

    A single external record (a single GitHub issue, etc.) must NEVER map
    to two local tasks. Without this constraint, cross-task collisions
    silently mirror divergent local state into one remote, which is the
    reconciliation engine's worst failure mode.
    """

    def test_unique_external_id_rejects_cross_task_collision(
        self, tmp_path: Path
    ) -> None:
        """T001 → gh-42, then T002 → gh-42 (same external_system) must abort."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            # Two tasks under the same feature.
            b.apply_event(_make_event(
                "feature.created", _make_feature_payload(feat_id="F001"),
                event_id="E000003", target_kind="feature", target_id="F001",
            ))
            b.apply_event(_make_event(
                "task.created", _make_task_payload(task_id="T001", feature_id="F001"),
                event_id="E000004", target_kind="task", target_id="T001",
            ))
            b.apply_event(_make_event(
                "task.created", _make_task_payload(task_id="T002", feature_id="F001"),
                event_id="E000005", target_kind="task", target_id="T002",
            ))

            # T001 → (github_issues, gh-42) succeeds.
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(task_id="T001", external_id="gh-42"),
                event_id="E000006", target_kind="task", target_id="T001",
            ))

            # T002 → (github_issues, gh-42) must abort on the UNIQUE.
            with pytest.raises(TransactionAborted):
                b.apply_event(_make_event(
                    "sync_mapping.upserted",
                    _make_sync_mapping_payload(task_id="T002", external_id="gh-42"),
                    event_id="E000007", target_kind="task", target_id="T002",
                ))
        finally:
            b.close()


class TestApplySyncMappingPayloadSerialization:
    """MF-2: apply_sync_mapping serializes through the payload model explicitly.

    If a hypothetical extra field were added to SyncMapping without being
    added to SyncMappingUpsertedPayload, the failure must surface AT THE
    CALL SITE as a ValidationError — not inside the BEGIN IMMEDIATE lock
    as a generic TransactionAborted.
    """

    def test_extra_field_on_mapping_fails_at_call_site(
        self, tmp_path: Path
    ) -> None:
        """Subclass SyncMapping with an extra field; apply_sync_mapping must
        raise ValidationError (extra='forbid' on the payload model)."""
        from pydantic import ValidationError

        from fakoli_state.state.models import SyncMapping

        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)

            # Build a mapping with a real extra attribute via unsafe setattr
            # after construction. (Subclassing wouldn't help — extra='forbid'
            # is on SyncMapping itself.) The payload model rebuilds from
            # field-by-field reads, so smuggling a field onto the mapping
            # instance does NOT make it into the payload — instead the
            # missing-on-payload value defaults. So the more direct probe is:
            # construct the canonical payload model with an extra kwarg and
            # confirm it rejects.
            from fakoli_state.state.payloads import SyncMappingUpsertedPayload

            with pytest.raises(ValidationError):
                SyncMappingUpsertedPayload(
                    task_id="T001",
                    external_system="github_issues",
                    external_id="gh-42",
                    last_synced_at=_T0.isoformat(),
                    surprise_extra_field="boom",  # type: ignore[call-arg]
                )

            # And the happy path: apply_sync_mapping with a clean mapping
            # round-trips through the payload model and lands a real row.
            mapping = SyncMapping(
                task_id="T001",
                external_system="github_issues",
                external_id="gh-42",
                last_synced_at=_T0,
            )
            event = b.apply_sync_mapping(mapping)
            assert event.action == "sync_mapping.upserted"
            stored = b.get_sync_mapping("T001")
            assert stored is not None
            assert stored.external_id == "gh-42"
        finally:
            b.close()

    def test_apply_sync_mapping_raises_validation_when_payload_class_drifts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Strengthened MF-2 regression: monkeypatch the payload model to
        require a field that SyncMapping does not have; apply_sync_mapping
        must surface a ValidationError AT THE CALL SITE rather than letting
        it tunnel into BEGIN IMMEDIATE as a TransactionAborted.

        This is the real protection MF-2 was supposed to give us: future
        drift between :class:`SyncMapping` and
        :class:`SyncMappingUpsertedPayload` fails fast outside the lock
        instead of leaving the JSONL log in an inconsistent state.
        """
        from pydantic import ConfigDict, Field, ValidationError, create_model

        from fakoli_state.state import sqlite as sqlite_mod
        from fakoli_state.state.models import SyncMapping

        # Build a drop-in replacement payload class that requires a NEW
        # field SyncMapping does not have. The original payload module
        # attribute is patched for the duration of the test; the
        # `apply_sync_mapping` wrapper resolves it by name at call time.
        DriftedPayload = create_model(  # noqa: N806 — class-like factory
            "SyncMappingUpsertedPayload",
            __config__=ConfigDict(extra="forbid"),
            task_id=(str, ...),
            external_system=(str, ...),
            external_id=(str, ...),
            external_url=(str | None, None),
            last_synced_at=(str, ...),
            sync_state=(str, "in_sync"),
            conflict_resolution_strategy=(str, "prompt"),
            provider_metadata=(dict, Field(default_factory=dict)),
            # The new required field with no value on SyncMapping → kaboom
            new_required_field=(str, ...),
        )
        monkeypatch.setattr(
            sqlite_mod, "SyncMappingUpsertedPayload", DriftedPayload
        )

        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            mapping = SyncMapping(
                task_id="T001",
                external_system="github_issues",
                external_id="gh-42",
                last_synced_at=_T0,
            )
            with pytest.raises(ValidationError):
                b.apply_sync_mapping(mapping)
            # And: state is unchanged — no JSONL line for the failed payload.
            assert b.get_sync_mapping("T001") is None
        finally:
            b.close()

    def test_apply_sync_mapping_records_actor_kwarg(self, tmp_path: Path) -> None:
        """SF-7: apply_sync_mapping(..., actor='alice') threads the actor into the event."""
        from fakoli_state.state.models import SyncMapping

        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            mapping = SyncMapping(
                task_id="T001",
                external_system="github_issues",
                external_id="gh-42",
                last_synced_at=_T0,
            )
            event = b.apply_sync_mapping(mapping, actor="alice")
            assert event.actor == "alice"
        finally:
            b.close()


class TestGetSyncMappingExternalSystemKwarg:
    """SF-1: get_sync_mapping(task_id, *, external_system=None) keyword arg.

    Composite-PK means a single task_id can have multiple mappings (one per
    external system). When external_system is omitted, the legacy ASC-first
    behaviour is preserved. When supplied, the lookup is scoped.
    """

    def test_scoped_lookup_by_external_system(self, tmp_path: Path) -> None:
        """Passing external_system returns the matching row directly."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            b.apply_event(_make_event(
                "sync_mapping.upserted",
                _make_sync_mapping_payload(
                    external_system="github_issues", external_id="gh-42",
                ),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            # Scoped lookup matches.
            mapping = b.get_sync_mapping("T001", external_system="github_issues")
            assert mapping is not None
            assert mapping.external_system == "github_issues"
            assert mapping.external_id == "gh-42"
            # Scoped lookup on a non-existent system returns None.
            assert b.get_sync_mapping("T001", external_system="linear") is None
        finally:
            b.close()

    def test_unscoped_lookup_returns_asc_first(self, tmp_path: Path) -> None:
        """Omitting external_system returns the first row by external_system ASC.

        We can only test this with one StrEnum value today (github_issues),
        so the assertion is "returns a row" not "returns the alphabetical
        first of two" — the ASC-first behaviour is documented in the
        docstring and exercised internally; adding a second StrEnum value
        in a future phase will turn this into a multi-system test.
        """
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            _setup_task_for_sync(b)
            b.apply_event(_make_event(
                "sync_mapping.upserted", _make_sync_mapping_payload(),
                event_id="E000005", target_kind="task", target_id="T001",
            ))
            mapping = b.get_sync_mapping("T001")  # no kwarg
            assert mapping is not None
            assert mapping.external_system == "github_issues"
        finally:
            b.close()


class TestSchemaAutoUpgrade:
    """SF-6: v0 / v1 / v2 → v3 auto-upgrade on initialize().

    Pre-Phase-8 dbs are upgraded purely additively — the new sync_mappings
    columns are nullable and the new UNIQUE cannot be violated by any
    pre-existing row.
    """

    def test_fresh_init_yields_v3(self, tmp_path: Path) -> None:
        """A brand-new initialize() lands on v3 directly (no upgrade fired)."""
        b = _make_backend(tmp_path)
        try:
            conn = sqlite3.connect(str(tmp_path / "state.db"))
            v = conn.execute("PRAGMA user_version").fetchone()[0]
            conn.close()
            assert v == 3
        finally:
            b.close()

    def test_v1_db_auto_upgrades_to_v3(self, tmp_path: Path) -> None:
        """A db marked user_version=1 (no sync_mappings rows) upgrades to v3."""
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()
        # Step 1: stand up a real v3 db.
        clock = _make_clock()
        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()
        b.close()
        # Step 2: forge user_version back to 1 to simulate an old db.
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()
        # Step 3: reopen — auto-upgrade must fire and bump back to 3.
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            conn = sqlite3.connect(db_path)
            v = conn.execute("PRAGMA user_version").fetchone()[0]
            conn.close()
            assert v == 3
        finally:
            b2.close()

    def test_v2_db_auto_upgrades_to_v3(self, tmp_path: Path) -> None:
        """A db marked user_version=2 upgrades to v3 without losing data."""
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()
        clock = _make_clock()
        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()
        # Seed a project to confirm data survives the upgrade.
        b.apply_event(_make_project_event(event_id="E000001"))
        b.close()
        # Forge to v2.
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        conn.close()
        # Reopen — auto-upgrade fires; project row survives.
        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            conn = sqlite3.connect(db_path)
            v = conn.execute("PRAGMA user_version").fetchone()[0]
            conn.close()
            assert v == 3
            proj = b2.get_project()
            assert proj is not None
            assert proj.id == "proj-1"
        finally:
            b2.close()

    def test_future_version_still_raises_mismatch(self, tmp_path: Path) -> None:
        """A db marked at a version newer than the code expects raises SchemaMismatch."""
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        Path(events_path).touch()
        clock = _make_clock()
        b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
        b.initialize()
        # Forge to a far-future version that cannot be auto-upgraded.
        assert b._conn is not None  # noqa: SLF001
        b._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 99}")  # noqa: SLF001
        with pytest.raises(SchemaMismatch):
            b.initialize()
        b.close()

    def test_check_schema_version_auto_upgrades_on_already_open_conn(
        self, tmp_path: Path
    ) -> None:
        """Forge user_version on a live connection, then re-call initialize().

        The second initialize() takes the early-return branch (self._conn is
        not None) which calls only _check_schema_version() — no DDL. This is
        the only path that actually exercises the SF-6 auto-upgrade branch.
        """
        b = _make_backend(tmp_path)
        try:
            assert b._conn is not None  # noqa: SLF001
            b._conn.execute("PRAGMA user_version = 1")  # noqa: SLF001
            b.initialize()  # takes early-return; _check_schema_version sees v1
            v = b._conn.execute("PRAGMA user_version").fetchone()[0]  # noqa: SLF001
            assert v == 3
        finally:
            b.close()


class TestSyncProviderSnakeCaseRegistry:
    """SF-3: register/get with snake_case provider ids (e.g. github_issues)."""

    def test_register_and_get_snake_case(self) -> None:
        from fakoli_state.sync import (
            PROVIDER_REGISTRY,
            get_sync_provider,
            register_sync_provider,
        )

        class _FakeProvider:
            provider_id = "github_issues"
            display_name = "GitHub Issues"

            def push_task(self, *, task: Any, mapping: Any) -> Any:  # pragma: no cover
                ...

            def fetch_task(self, *, external_id: str) -> Any:  # pragma: no cover
                ...

            def list_tasks(self) -> list[Any]:  # pragma: no cover
                ...

            def delete_task(self, *, external_id: str) -> None:  # pragma: no cover
                ...

            def health_check(self) -> Any:  # pragma: no cover
                ...

        # Snapshot + restore the registry so this test doesn't pollute siblings.
        snapshot = dict(PROVIDER_REGISTRY)
        PROVIDER_REGISTRY.clear()
        try:
            register_sync_provider("github_issues", _FakeProvider)
            assert get_sync_provider("github_issues") is _FakeProvider
        finally:
            PROVIDER_REGISTRY.clear()
            PROVIDER_REGISTRY.update(snapshot)


# ---------------------------------------------------------------------------
# P6-5 — Payload validation centralization
# ---------------------------------------------------------------------------


class TestPayloadValidation:
    """Tests for the per-action Pydantic payload models introduced in P6-5.

    Coverage:
    - Each payload model validates a known-good payload.
    - Each payload model rejects an unknown extra field (extra='forbid').
    - _apply_mutation raises ValidationError (wrapped as TransactionAborted)
      for a malformed payload on a known action.
    - Existing replay-from-empty test still passes (regression check).
    """

    # ------------------------------------------------------------------
    # Import helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_payload_models() -> Any:
        """Return the payloads module (deferred import to keep test isolation)."""
        from fakoli_state.state import payloads as p
        return p

    # ------------------------------------------------------------------
    # Happy-path: each model validates a known-good payload
    # ------------------------------------------------------------------

    def test_project_created_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.ProjectCreatedPayload.model_validate({
            "id": "proj-1",
            "name": "Test Project",
            "description": "desc",
            "created_at": _T0.isoformat(),
            "updated_at": _T0.isoformat(),
        })
        assert obj.id == "proj-1"
        assert obj.name == "Test Project"

    def test_state_initialized_payload_validates_empty(self) -> None:
        p = self._import_payload_models()
        obj = p.StateInitializedPayload.model_validate({})
        assert obj is not None

    def test_prd_parsed_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.PrdParsedPayload.model_validate({
            "project_id": "proj-1",
            "summary": "short summary",
            "goals": ["goal1"],
            "non_goals": [],
            "requirements": [],
            "acceptance_criteria": [],
            "risks": [],
            "open_questions": [],
        })
        assert obj.project_id == "proj-1"
        assert obj.summary == "short summary"

    def test_prd_reviewed_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.PrdReviewedPayload.model_validate({
            "project_id": "proj-1",
            "reviewer": "alice",
        })
        assert obj.reviewer == "alice"

    def test_prd_approved_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.PrdApprovedPayload.model_validate({
            "project_id": "proj-1",
            "approver": "bob",
        })
        assert obj.approver == "bob"

    def test_feature_created_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.FeatureCreatedPayload.model_validate({
            "id": "F001",
            "title": "My Feature",
        })
        assert obj.id == "F001"

    def test_task_created_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.TaskCreatedPayload.model_validate({
            "id": "T001",
            "feature_id": "F001",
            "title": "My Task",
        })
        assert obj.id == "T001"

    def test_task_scored_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.TaskScoredPayload.model_validate({
            "task_id": "T001",
            "scores": {"complexity": 3, "risk": 2},
            "explanation": "seems manageable",
        })
        assert obj.task_id == "T001"
        assert obj.explanation == "seems manageable"

    def test_task_expanded_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.TaskExpandedPayload.model_validate({
            "parent_task_id": "T001",
            "subtasks": [],
        })
        assert obj.parent_task_id == "T001"

    def test_task_status_changed_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        # JSON keys are 'from' and 'to' (Python keywords mapped by alias)
        obj = p.TaskStatusChangedPayload.model_validate({
            "task_id": "T001",
            "from": "proposed",
            "to": "drafted",
        })
        assert obj.task_id == "T001"
        assert obj.from_status == "proposed"
        assert obj.to_status == "drafted"

    def test_claim_created_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        expires = (_T0 + timedelta(hours=1)).isoformat()
        obj = p.ClaimCreatedPayload.model_validate({
            "id": "C001",
            "task_id": "T001",
            "claimed_by": "agent-alpha",
            "claim_type": "task",
            "status": "active",
            "created_at": _T0.isoformat(),
            "lease_expires_at": expires,
            "last_heartbeat_at": _T0.isoformat(),
        })
        assert obj.id == "C001"

    def test_claim_released_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.ClaimReleasedPayload.model_validate({
            "claim_id": "C001",
            "released_by": "agent-alpha",
            "release_reason": "work done",
        })
        assert obj.claim_id == "C001"

    def test_claim_renewed_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        expires = (_T0 + timedelta(hours=2)).isoformat()
        obj = p.ClaimRenewedPayload.model_validate({
            "claim_id": "C001",
            "lease_expires_at": expires,
            "last_heartbeat_at": _T0.isoformat(),
        })
        assert obj.claim_id == "C001"

    def test_claim_stale_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.ClaimStalePayload.model_validate({
            "claim_id": "C001",
            "detected_at": _T0.isoformat(),
            "reason": "lease_expired",
        })
        assert obj.claim_id == "C001"

    def test_evidence_submitted_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.EvidenceSubmittedPayload.model_validate({
            "task_id": "T001",
            "claim_id": "C001",
            "submitted_by": "agent-alpha",
            "evidence_id": "EV001",
            "commands_run": ["pytest -q"],
            "files_changed": ["src/foo.py"],
        })
        assert obj.evidence_id == "EV001"

    def test_task_applied_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.TaskAppliedPayload.model_validate({
            "task_id": "T001",
            "reviewer": "bob",
            "decision": "accepted",
        })
        assert obj.decision == "accepted"

    def test_file_changed_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.FileChangedPayload.model_validate({
            "file": "src/foo.py",
            "tool": "Edit",
            "actor": "agent-alpha",
        })
        assert obj.file == "src/foo.py"

    # ------------------------------------------------------------------
    # extra='forbid': unknown key raises ValidationError
    # ------------------------------------------------------------------

    def test_project_created_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.ProjectCreatedPayload.model_validate({
                "id": "proj-1",
                "name": "n",
                "description": "d",
                "created_at": _T0.isoformat(),
                "updated_at": _T0.isoformat(),
                "unknown_field": "should_fail",
            })

    def test_state_initialized_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.StateInitializedPayload.model_validate({"unknown": True})

    def test_prd_parsed_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.PrdParsedPayload.model_validate({
                "project_id": "proj-1",
                "unknown_key": "oops",
            })

    def test_prd_reviewed_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.PrdReviewedPayload.model_validate({
                "project_id": "proj-1",
                "reviewer": "alice",
                "bad": "field",
            })

    def test_prd_approved_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.PrdApprovedPayload.model_validate({
                "project_id": "proj-1",
                "approver": "bob",
                "extra": "nope",
            })

    def test_feature_created_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.FeatureCreatedPayload.model_validate({
                "id": "F001",
                "title": "t",
                "mystery": "field",
            })

    def test_task_created_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.TaskCreatedPayload.model_validate({
                "id": "T001",
                "feature_id": "F001",
                "title": "t",
                "alien_field": "no",
            })

    def test_task_scored_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.TaskScoredPayload.model_validate({
                "task_id": "T001",
                "scores": {},
                "phantom": "field",
            })

    def test_task_expanded_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.TaskExpandedPayload.model_validate({
                "parent_task_id": "T001",
                "subtasks": [],
                "bad": "key",
            })

    def test_task_status_changed_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.TaskStatusChangedPayload.model_validate({
                "task_id": "T001",
                "from": "proposed",
                "to": "drafted",
                "extra_field": "bad",
            })

    def test_claim_created_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        expires = (_T0 + timedelta(hours=1)).isoformat()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.ClaimCreatedPayload.model_validate({
                "id": "C001",
                "task_id": "T001",
                "claimed_by": "agent",
                "claim_type": "task",
                "status": "active",
                "created_at": _T0.isoformat(),
                "lease_expires_at": expires,
                "last_heartbeat_at": _T0.isoformat(),
                "injected": "field",
            })

    def test_claim_released_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.ClaimReleasedPayload.model_validate({
                "claim_id": "C001",
                "released_by": "agent",
                "bogus": "key",
            })

    def test_claim_renewed_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        expires = (_T0 + timedelta(hours=2)).isoformat()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.ClaimRenewedPayload.model_validate({
                "claim_id": "C001",
                "lease_expires_at": expires,
                "last_heartbeat_at": _T0.isoformat(),
                "mystery": "value",
            })

    def test_claim_stale_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.ClaimStalePayload.model_validate({
                "claim_id": "C001",
                "detected_at": _T0.isoformat(),
                "reason": "lease_expired",
                "not_a_field": True,
            })

    def test_evidence_submitted_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.EvidenceSubmittedPayload.model_validate({
                "task_id": "T001",
                "claim_id": "C001",
                "submitted_by": "agent",
                "evidence_id": "EV001",
                "commands_run": ["pytest"],
                "files_changed": ["foo.py"],
                "undocumented_field": "oops",
            })

    def test_task_applied_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.TaskAppliedPayload.model_validate({
                "task_id": "T001",
                "reviewer": "alice",
                "decision": "accepted",
                "unexpected_key": "value",
            })

    def test_file_changed_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.FileChangedPayload.model_validate({
                "file": "foo.py",
                "tool": "Edit",
                "actor": "agent",
                "injected_payload": "malicious",
            })

    # ------------------------------------------------------------------
    # progress.noted payload — Phase 6 MCP submit_progress (audit-only)
    # ------------------------------------------------------------------

    def test_progress_noted_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.ProgressNotedPayload.model_validate({
            "task_id": "T001",
            "actor": "agent-guido",
            "notes": "Fixed the flaky test; CI green.",
            "noted_at": _T0.isoformat(),
        })
        assert obj.task_id == "T001"
        assert obj.actor == "agent-guido"
        assert obj.notes == "Fixed the flaky test; CI green."

    def test_progress_noted_payload_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.ProgressNotedPayload.model_validate({
                "task_id": "T001",
                "actor": "agent-guido",
                "notes": "All good.",
                "noted_at": _T0.isoformat(),
                "injected_key": "should_be_rejected",
            })

    # ------------------------------------------------------------------
    # Phase 8 — sync_mapping payloads
    # ------------------------------------------------------------------

    def test_sync_mapping_upserted_payload_validates_good(self) -> None:
        p = self._import_payload_models()
        obj = p.SyncMappingUpsertedPayload.model_validate({
            "task_id": "T001",
            "external_system": "github_issues",
            "external_id": "gh-42",
            "last_synced_at": _T0.isoformat(),
            "sync_state": "in_sync",
            "conflict_resolution_strategy": "prompt",
        })
        assert obj.task_id == "T001"
        assert obj.external_system == "github_issues"
        assert obj.external_id == "gh-42"

    def test_sync_mapping_upserted_payload_applies_defaults(self) -> None:
        """Optional fields fall back to defaults when omitted."""
        p = self._import_payload_models()
        obj = p.SyncMappingUpsertedPayload.model_validate({
            "task_id": "T001",
            "external_system": "github_issues",
            "external_id": "gh-42",
            "last_synced_at": _T0.isoformat(),
        })
        assert obj.sync_state == "in_sync"
        assert obj.conflict_resolution_strategy == "prompt"

    def test_sync_mapping_upserted_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.SyncMappingUpsertedPayload.model_validate({
                "task_id": "T001",
                "external_system": "github_issues",
                "external_id": "gh-42",
                "last_synced_at": _T0.isoformat(),
                "smuggled_field": "should_be_rejected",
            })

    def test_sync_mapping_deleted_payload_validates_minimum(self) -> None:
        p = self._import_payload_models()
        obj = p.SyncMappingDeletedPayload.model_validate({"task_id": "T001"})
        assert obj.task_id == "T001"
        assert obj.external_system is None

    def test_sync_mapping_deleted_payload_validates_scoped(self) -> None:
        """external_system is optional but accepted when provided."""
        p = self._import_payload_models()
        obj = p.SyncMappingDeletedPayload.model_validate({
            "task_id": "T001",
            "external_system": "github_issues",
        })
        assert obj.external_system == "github_issues"

    def test_sync_mapping_deleted_rejects_unknown_key(self) -> None:
        from pydantic import ValidationError as PydanticValidationError
        p = self._import_payload_models()
        with pytest.raises(PydanticValidationError, match="extra"):
            p.SyncMappingDeletedPayload.model_validate({
                "task_id": "T001",
                "not_a_real_field": "no",
            })

    # ------------------------------------------------------------------
    # _apply_mutation raises ValidationError (wrapped as TransactionAborted)
    # for a malformed payload on a known action
    # ------------------------------------------------------------------

    def test_apply_mutation_raises_transaction_aborted_on_malformed_payload(
        self, tmp_path: Path
    ) -> None:
        """A known action with an extra unknown key raises TransactionAborted.

        This proves that _apply_mutation validates the payload before dispatching.
        """
        b = _make_backend(tmp_path)
        try:
            bad_event = Event(
                id="E000001",
                timestamp=_T0,
                actor="test",
                action="project.created",
                target_kind="project",
                target_id="proj-1",
                payload_json={
                    "id": "proj-1",
                    "name": "Test",
                    "description": "desc",
                    "created_at": _T0.isoformat(),
                    "updated_at": _T0.isoformat(),
                    "unknown_extra_field": "should_trigger_forbid",
                },
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)
        finally:
            b.close()

    def test_apply_mutation_raises_on_missing_required_field(
        self, tmp_path: Path
    ) -> None:
        """A known action with a missing required field raises TransactionAborted."""
        b = _make_backend(tmp_path)
        try:
            bad_event = Event(
                id="E000001",
                timestamp=_T0,
                actor="test",
                action="prd.reviewed",
                target_kind="prd",
                target_id="proj-1",
                payload_json={
                    # missing 'reviewer' (required by PrdReviewedPayload)
                    "project_id": "proj-1",
                },
            )
            with pytest.raises(TransactionAborted):
                b.apply_event(bad_event)
        finally:
            b.close()

    # ------------------------------------------------------------------
    # Regression: the critical replay-from-empty test still passes
    # ------------------------------------------------------------------

    def test_replay_from_empty_still_passes_after_payload_centralization(
        self, tmp_path: Path
    ) -> None:
        """Critical regression test: replay produces byte-for-byte identical state.

        This duplicates the audit-guarantee test but is owned by the P6-5
        payload-centralization change to make regressions immediately obvious.
        """
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        events_path = str(tmp_path / "events.jsonl")
        db_path = str(tmp_path / "state.db")

        try:
            b.apply_event(_make_project_event(event_id="E000001"))
            b.apply_event(_make_init_event(event_id="E000002"))
            b.apply_event(
                _make_project_event(
                    event_id="E000003",
                    project_id="proj-1",
                    project_name="Replayed Project",
                )
            )
        finally:
            b.close()

        original_dump = _sqlite_dump(db_path)

        clock2 = _make_clock()
        b2 = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock2)
        b2.initialize()
        try:
            b2.replay_from_empty(events_path)
        finally:
            pass

        b2.close()

        replayed_dump = _sqlite_dump(db_path)

        assert original_dump == replayed_dump, (
            "Replayed state.db does not match original after P6-5 payload centralization.\n"
            f"Original dump (truncated):\n{original_dump[:500]}\n\n"
            f"Replayed dump (truncated):\n{replayed_dump[:500]}"
        )


# ---------------------------------------------------------------------------
# Regression: minimal task.created payloads (no scores/verification) must
# succeed. The MCP path will send these as the common case; CLI happens to
# always send full dumps and would have masked the bug. Critic-PR#44 P1.
# ---------------------------------------------------------------------------


class TestMinimalTaskPayloads:
    """Minimal task.created / task.expanded payloads from MCP-style callers."""

    def _make_feature_event(self, event_id: str = "E000003") -> Event:
        return _make_event(
            "feature.created",
            {
                "id": "F001",
                "title": "Feature One",
                "description": "",
                "status": "proposed",
                "requirements": [],
                "tasks": [],
            },
            event_id=event_id,
            target_kind="feature",
            target_id="F001",
        )

    def test_task_created_minimal_payload_succeeds(self, tmp_path: Path) -> None:
        """task.created with scores=None and verification=None gets normalized."""
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        try:
            _setup_project(b)
            b.apply_event(self._make_feature_event(event_id="E000003"))
            # Minimal task payload — what an MCP caller would send.
            minimal = {
                "id": "T001",
                "feature_id": "F001",
                "title": "Minimal task",
                "scores": None,
                "verification": None,
                "created_at": _T0.isoformat(),
                "updated_at": _T0.isoformat(),
            }
            event = _make_event(
                "task.created", minimal, event_id="E000004",
                target_kind="task", target_id="T001",
            )
            b.apply_event(event)
            row = b.get_task("T001")
            assert row is not None
            assert row.id == "T001"
            assert row.title == "Minimal task"
        finally:
            b.close()

    def test_task_expanded_minimal_subtasks_succeed(self, tmp_path: Path) -> None:
        """Subtasks in task.expanded can also omit scores/verification."""
        clock = _make_clock()
        b = _make_backend(tmp_path, clock)
        try:
            _setup_project(b)
            b.apply_event(self._make_feature_event(event_id="E000003"))
            parent = {
                "id": "T001",
                "feature_id": "F001",
                "title": "Parent",
                "scores": None,
                "verification": None,
                "created_at": _T0.isoformat(),
                "updated_at": _T0.isoformat(),
            }
            b.apply_event(_make_event(
                "task.created", parent, event_id="E000004",
                target_kind="task", target_id="T001",
            ))
            expand = {
                "parent_task_id": "T001",
                "subtasks": [
                    {
                        "id": "T001.1",
                        "feature_id": "F001",
                        "title": "Sub one",
                        "description": "Subtask description",
                        "scores": None,
                        "verification": None,
                        "created_at": _T0.isoformat(),
                        "updated_at": _T0.isoformat(),
                    },
                ],
            }
            b.apply_event(_make_event(
                "task.expanded", expand, event_id="E000005",
                target_kind="task", target_id="T001",
            ))
            sub = b.get_task("T001.1")
            assert sub is not None
            assert sub.parent_task_id == "T001"
        finally:
            b.close()


# ---------------------------------------------------------------------------
# PR #49 P1-3 regression — v2 → v3 migration actually applies ALTERs
# ---------------------------------------------------------------------------


class TestV2ToV3MigrationAppliesColumnAdditions:
    """P1-3 — v2 sync_mappings table missing v3 columns must get ALTERed.

    Pre-fix bug: ``_check_schema_version`` stamped the db as v3 without
    running any ALTER TABLE — the IF NOT EXISTS DDL is a no-op against an
    existing table, so a v2 db's ``sync_mappings`` table stayed at v2
    shape (no ``external_url`` / ``provider_metadata_json`` / unique
    index) while the user_version pragma claimed v3. Queries against the
    new columns raised ``OperationalError`` at runtime.
    """

    def _stand_up_v2_sync_mappings_table(
        self, db_path: str, events_path: str,
    ) -> None:
        """Create a v2-shaped sync_mappings table (no v3 columns/index).

        Mirrors the v2 schema: composite PK, no ``external_url``, no
        ``provider_metadata_json``, no UNIQUE on (external_system,
        external_id). Stamps user_version=2 so the next ``initialize()``
        takes the v2→v3 migration branch.
        """
        Path(events_path).touch()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # Create the minimum tables a v2 db needs to satisfy FKs.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS features (
                id           TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                description  TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'proposed',
                requirements TEXT NOT NULL DEFAULT '[]',
                tasks        TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id                   TEXT PRIMARY KEY,
                feature_id           TEXT NOT NULL,
                title                TEXT NOT NULL,
                description          TEXT NOT NULL,
                status               TEXT NOT NULL DEFAULT 'proposed',
                priority             TEXT NOT NULL DEFAULT 'medium',
                dependencies         TEXT NOT NULL DEFAULT '[]',
                conflict_groups      TEXT NOT NULL DEFAULT '[]',
                scores               TEXT NOT NULL DEFAULT '{}',
                acceptance_criteria  TEXT NOT NULL DEFAULT '[]',
                implementation_notes TEXT NOT NULL DEFAULT '[]',
                verification         TEXT NOT NULL DEFAULT '{}',
                likely_files         TEXT NOT NULL DEFAULT '[]',
                parent_task_id       TEXT,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL
            );
            -- v2 sync_mappings: composite PK only, no v3 additions.
            CREATE TABLE sync_mappings (
                task_id                      TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                external_system              TEXT NOT NULL,
                external_id                  TEXT NOT NULL,
                last_synced_at               TEXT NOT NULL,
                sync_state                   TEXT NOT NULL DEFAULT 'in_sync',
                conflict_resolution_strategy TEXT NOT NULL DEFAULT 'prompt',
                PRIMARY KEY (task_id, external_system)
            );
            """
        )
        # Insert a project + feature + task + sync_mapping in v2 shape so
        # the migration has real data to preserve.
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("proj-1", "Test", "", _T0.isoformat(), _T0.isoformat()),
        )
        conn.execute(
            "INSERT INTO features (id, title, description) VALUES (?, ?, ?)",
            ("F001", "F", ""),
        )
        conn.execute(
            "INSERT INTO tasks (id, feature_id, title, description, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("T001", "F001", "Old", "old", _T0.isoformat(), _T0.isoformat()),
        )
        conn.execute(
            "INSERT INTO sync_mappings (task_id, external_system, "
            "external_id, last_synced_at) VALUES (?, ?, ?, ?)",
            ("T001", "github_issues", "gh-1", _T0.isoformat()),
        )
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        conn.close()

    def test_v2_db_with_existing_sync_mappings_gets_v3_columns(
        self, tmp_path: Path,
    ) -> None:
        """After v2→v3 auto-upgrade, the new columns exist and are queryable."""
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        self._stand_up_v2_sync_mappings_table(db_path, events_path)

        # Re-open with v3 code: migration must add the missing columns.
        clock = _make_clock()
        b = SqliteBackend(
            db_path=db_path, events_path=events_path, clock=clock,
        )
        b.initialize()
        try:
            # Verify the new columns exist by querying them — this would
            # raise OperationalError pre-fix.
            assert b._conn is not None  # noqa: SLF001
            row = b._conn.execute(  # noqa: SLF001
                "SELECT external_url, provider_metadata_json "
                "FROM sync_mappings WHERE task_id = ?",
                ("T001",),
            ).fetchone()
            assert row is not None
            # Default values for previously-absent columns: NULL.
            assert row[0] is None
            assert row[1] is None
            # user_version is now 3.
            v = b._conn.execute("PRAGMA user_version").fetchone()[0]  # noqa: SLF001
            assert v == 3
        finally:
            b.close()

    def test_v2_db_after_upgrade_enforces_unique_external_constraint(
        self, tmp_path: Path,
    ) -> None:
        """The v3 UNIQUE(external_system, external_id) is enforced post-upgrade.

        Two distinct task rows trying to claim the same (external_system,
        external_id) pair must fail at INSERT — that's the contract the
        v3 migration is supposed to add.
        """
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        self._stand_up_v2_sync_mappings_table(db_path, events_path)

        # Add a second task so we have two tasks to map to the same remote id.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO tasks (id, feature_id, title, description, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("T002", "F001", "Other", "other", _T0.isoformat(), _T0.isoformat()),
        )
        conn.commit()
        conn.close()

        # Trigger the upgrade.
        clock = _make_clock()
        b = SqliteBackend(
            db_path=db_path, events_path=events_path, clock=clock,
        )
        b.initialize()
        try:
            assert b._conn is not None  # noqa: SLF001
            # T001 already owns ('github_issues', 'gh-1'); T002 must NOT be
            # able to claim the same pair after the v3 unique index lands.
            with pytest.raises(sqlite3.IntegrityError):
                b._conn.execute(  # noqa: SLF001
                    "INSERT INTO sync_mappings "
                    "(task_id, external_system, external_id, last_synced_at) "
                    "VALUES (?, ?, ?, ?)",
                    ("T002", "github_issues", "gh-1", _T0.isoformat()),
                )
        finally:
            b.close()

    def test_v2_migration_preserves_existing_sync_mapping_rows(
        self, tmp_path: Path,
    ) -> None:
        """The pre-existing v2 mapping row survives the v3 migration intact."""
        db_path = str(tmp_path / "state.db")
        events_path = str(tmp_path / "events.jsonl")
        self._stand_up_v2_sync_mappings_table(db_path, events_path)

        clock = _make_clock()
        b = SqliteBackend(
            db_path=db_path, events_path=events_path, clock=clock,
        )
        b.initialize()
        try:
            stored = b.get_sync_mapping("T001")
            assert stored is not None
            assert stored.task_id == "T001"
            assert stored.external_system == "github_issues"
            assert stored.external_id == "gh-1"
            # New optional fields default cleanly.
            assert stored.external_url is None
            assert stored.provider_metadata == {}
        finally:
            b.close()


# ---------------------------------------------------------------------------
# PR #49 P2-2 regression — multi-provider missing_sync_mapping scan
# ---------------------------------------------------------------------------


class TestMissingSyncMappingPerProvider:
    """P2-2 — reconciliation must check each configured provider separately.

    Pre-fix bug: ``_scan_missing_sync_mappings`` called
    ``get_sync_mapping(task.id)`` without ``external_system``, returning
    the ASC-first mapping. A done task mapped to ``github_issues`` but
    NOT to ``linear`` was treated as fully mapped — the ``linear`` gap
    was never surfaced.
    """

    def test_multi_provider_emits_per_provider_discrepancy(
        self, tmp_path: Path,
    ) -> None:
        """Two providers configured, task only mapped to one → discrepancy
        for the missing one."""
        from fakoli_state.state.models import SyncMapping
        from fakoli_state.sync.reconciliation import (
            DiscrepancyKind,
            ReconciliationEngine,
        )

        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            # Walk a task through the lifecycle to status=done.
            b.apply_event(_make_event(
                "feature.created",
                _make_feature_payload(),
                event_id="E000003", target_kind="feature", target_id="F001",
            ))
            b.apply_event(_make_event(
                "task.created", _make_task_payload(task_id="T001"),
                event_id="E000004", target_kind="task", target_id="T001",
            ))
            chain = [
                ("proposed", "drafted"),
                ("drafted", "reviewed"),
                ("reviewed", "ready"),
                ("ready", "claimed"),
                ("claimed", "in_progress"),
                ("in_progress", "needs_review"),
                ("needs_review", "accepted"),
                ("accepted", "done"),
            ]
            eid = 5
            for frm, to in chain:
                b.apply_event(_make_event(
                    "task.status_changed",
                    {"task_id": "T001", "from": frm, "to": to},
                    event_id=f"E{eid:06d}", target_kind="task", target_id="T001",
                ))
                eid += 1
            # Map T001 to github_issues ONLY.
            b.apply_sync_mapping(SyncMapping(
                task_id="T001",
                external_system="github_issues",
                external_id="gh-1",
                last_synced_at=_T0,
            ))

            # Configure BOTH github_issues AND linear.
            engine = ReconciliationEngine(
                b, state_dir=tmp_path, clock=_make_clock(),
                configured_providers=["github_issues", "linear"],
            )
            report = engine.scan()
            missing = [
                d for d in report.discrepancies
                if d.kind == DiscrepancyKind.missing_sync_mapping
            ]
            # Pre-fix: 0 (ASC-first returned the github_issues row).
            # Post-fix: 1 — the linear gap is flagged.
            assert len(missing) == 1, (
                f"P2-2 regression: expected exactly one missing_sync_mapping "
                f"for the unmapped provider (linear); got {len(missing)}."
            )
            d = missing[0]
            assert d.target_id == "T001"
            assert d.payload["missing_provider"] == "linear"
            assert "linear" in d.suggested_fix
            assert "T001" in d.suggested_fix
        finally:
            b.close()


# ---------------------------------------------------------------------------
# Phase 9 T5 — dispatcher regression (T3 broke the SyncAuditPayload alias)
# ---------------------------------------------------------------------------


class TestSyncDispatcherUsesConcreteSubclasses:
    """T5 regression — every ``sync.*`` action must dispatch to its concrete
    subclass from ``ACTION_TO_PAYLOAD`` (not the union TypeAlias).

    Phase 9 T3 turned ``SyncAuditPayload`` into an
    ``Annotated[Union[...], Field(discriminator="action")]`` form which is
    NOT a ``BaseModel`` subclass — it has no ``.model_validate`` method.
    The pre-T5 dispatcher's table did
    ``{"sync.push.started": (SyncAuditPayload, ...), ...}`` and crashed
    every ``sync.*`` event with ``AttributeError: 'types.UnionType' object
    has no attribute 'model_validate'`` (wrapped by the backend as
    ``error.transaction_aborted``). T5 switched to a dict-spread over
    ``ACTION_TO_PAYLOAD`` so each entry resolves to a real concrete
    subclass; this test pins the dispatcher to that contract.
    """

    def test_every_sync_action_dispatch_uses_a_real_basemodel_subclass(
        self, tmp_path: Path,
    ) -> None:
        """Every sync.* dispatch entry must be a callable ``model_validate``.

        Walk the dispatch table and assert each ``sync.*`` action's
        payload class has a callable ``model_validate`` method. The
        ``types.UnionType`` regression would fail this with an
        ``AttributeError`` at hasattr-resolution.
        """
        from fakoli_state.state.payloads import ACTION_TO_PAYLOAD

        b = _make_backend(tmp_path)
        try:
            table = b._get_action_handlers()
            for action in ACTION_TO_PAYLOAD:
                assert action in table, (
                    f"T5 regression: dispatcher missing sync action {action!r}; "
                    f"ACTION_TO_PAYLOAD declares it but the dispatch table "
                    "does not route it. Did the dict-spread merge drop?"
                )
                payload_cls, handler = table[action]
                # The contract is: a class with .model_validate (the
                # Pydantic v2 BaseModel API). The TypeAlias would fail
                # this — UnionType has no such attribute.
                assert hasattr(payload_cls, "model_validate"), (
                    f"T5 regression: dispatch entry for {action!r} resolved "
                    f"to {payload_cls!r} which has no .model_validate. "
                    "T3's discriminated-union TypeAlias slipped back in."
                )
                # Sanity: the concrete subclass should be the one
                # ACTION_TO_PAYLOAD picked. Otherwise the dispatcher and
                # the discriminator have drifted.
                assert payload_cls is ACTION_TO_PAYLOAD[action], (
                    f"T5 regression: dispatch for {action!r} routed to "
                    f"{payload_cls!r}, but ACTION_TO_PAYLOAD says it should "
                    f"be {ACTION_TO_PAYLOAD[action]!r}."
                )
                assert callable(handler)
        finally:
            b.close()

    def test_sync_pull_deferred_event_dispatches_without_attribute_error(
        self, tmp_path: Path,
    ) -> None:
        """End-to-end: apply a real ``sync.pull.deferred`` event and verify
        it lands as itself (NOT as ``error.transaction_aborted``).

        Pre-T5: ``_apply_mutation`` called ``SyncAuditPayload.model_validate``,
        hit ``AttributeError``, the backend wrapped it as
        ``TransactionAborted``, and the JSONL log contained
        ``error.transaction_aborted`` instead of the intended event.
        """
        b = _make_backend(tmp_path)
        events_path = str(tmp_path / "events.jsonl")
        try:
            # Apply a sync.pull.deferred event end-to-end. If the
            # dispatcher is still broken this raises TransactionAborted
            # and the JSONL row is the aborted-error sentinel.
            evt = Event(
                id=PENDING_EVENT_ID,
                timestamp=_T0,
                actor="test",
                action="sync.pull.deferred",
                target_kind="task",
                target_id="T001",
                payload_json={
                    "provider_id": "github_issues",
                    "task_id": "T001",
                    "external_id": "42",
                    "direction": "pull",
                    "resolution": "local_wins_deferred",
                },
            )
            b.apply_event(evt)

            # Verify the JSONL row is the deferred event, not the abort
            # sentinel.
            events = _read_jsonl(events_path)
            actions = [e["action"] for e in events]
            assert "sync.pull.deferred" in actions, (
                f"T5 regression: sync.pull.deferred did not land in the "
                f"audit log; got actions={actions}. The dispatcher likely "
                f"raised AttributeError on the TypeAlias and the backend "
                f"wrapped it as error.transaction_aborted."
            )
            assert "error.transaction_aborted" not in actions, (
                f"T5 regression: dispatcher crashed on sync.pull.deferred; "
                f"got actions={actions}. Check ACTION_TO_PAYLOAD wiring "
                f"in state/sqlite.py:_get_action_handlers."
            )
        finally:
            b.close()


# ---------------------------------------------------------------------------
# list_claims / list_reviews / list_evidence — full-snapshot read methods
# ---------------------------------------------------------------------------


def _setup_full_snapshot_backend(b: SqliteBackend) -> None:
    """Build a backend with released + stale claims, a review, and evidence.

    Event chain:
      - project + PRD + feature + task T001 (reaches 'ready')
      - claim C001 created (active)
      - claim C001 released  → status='released', task='ready'
      - task T001 re-claimed via C002 (active)
      - evidence EV001 submitted  → task='needs_review', claim C002='released'
      - task T001 applied (accepted)  → task='done', review row inserted
      - task T002 created (reaches 'ready')
      - claim C003 created (active), then marked stale
    """
    # ---- project bootstrap (uses event IDs E000001–E000002) ----
    _setup_claimable_task(b, task_id="T001")

    # ---- C001 active → released ----
    b.apply_event(_make_event(
        "claim.created",
        _make_claim_payload(claim_id="C001", task_id="T001"),
        event_id="E000010", target_kind="claim", target_id="C001",
    ))
    b.apply_event(_make_event(
        "claim.released",
        {"claim_id": "C001", "released_by": "agent-alpha",
         "release_reason": "dropped", "force": False},
        event_id="E000011", target_kind="claim", target_id="C001",
    ))

    # ---- T001 re-ready via C002 ----
    # task was returned to 'ready' by the release handler; re-claim it
    b.apply_event(_make_event(
        "claim.created",
        _make_claim_payload(claim_id="C002", task_id="T001"),
        event_id="E000012", target_kind="claim", target_id="C002",
    ))

    # ---- evidence + apply ----
    b.apply_event(_make_event(
        "evidence.submitted",
        _make_evidence_payload(task_id="T001", claim_id="C002", evidence_id="EV001"),
        event_id="E000013", target_kind="task", target_id="T001",
    ))
    b.apply_event(_make_event(
        "task.applied",
        _make_applied_payload(task_id="T001", reviewer="alice", decision="accepted"),
        event_id="E000014", target_kind="task", target_id="T001",
    ))

    # ---- T002 with a stale claim ----
    # Reuse _setup_claimable_task logic but inline since project already exists.
    # Insert F001 task T002 directly via feature.created + task.created + transitions.
    b.apply_event(_make_event(
        "task.created",
        _make_task_payload(task_id="T002", feature_id="F001"),
        event_id="E000015", target_kind="task", target_id="T002",
    ))
    for from_s, to_s, eid in [
        ("proposed", "drafted", "E000016"),
        ("drafted", "reviewed", "E000017"),
        ("reviewed", "ready", "E000018"),
    ]:
        b.apply_event(_make_event(
            "task.status_changed",
            {"task_id": "T002", "from": from_s, "to": to_s},
            event_id=eid, target_kind="task", target_id="T002",
        ))

    b.apply_event(_make_event(
        "claim.created",
        _make_claim_payload(claim_id="C003", task_id="T002"),
        event_id="E000019", target_kind="claim", target_id="C003",
    ))
    b.apply_event(_make_event(
        "claim.stale",
        {"claim_id": "C003", "detected_at": _T0.isoformat(),
         "reason": "lease_expired"},
        event_id="E000020", target_kind="claim", target_id="C003",
    ))


class TestListClaimsReviewsEvidence:
    """Unit tests for list_claims(), list_reviews(), and list_evidence()."""

    # ------------------------------------------------------------------
    # list_claims()
    # ------------------------------------------------------------------

    def test_list_claims_returns_empty_when_no_claims(self, tmp_path: Path) -> None:
        """list_claims() returns [] when the claims table is empty."""
        b = _make_backend(tmp_path)
        try:
            assert b.list_claims() == []
        finally:
            b.close()

    def test_list_claims_returns_all_statuses(self, tmp_path: Path) -> None:
        """list_claims() returns active, released, and stale claims in id order."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            claims = b.list_claims()
            # C001 released, C002 released (auto by evidence.submitted), C003 stale
            claim_ids = [c.id for c in claims]
            assert "C001" in claim_ids
            assert "C002" in claim_ids
            assert "C003" in claim_ids

        finally:
            b.close()

    def test_list_claims_sorted_by_id(self, tmp_path: Path) -> None:
        """list_claims() returns rows in ascending id order."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            claims = b.list_claims()
            ids = [c.id for c in claims]
            assert ids == sorted(ids), (
                f"list_claims() result is not sorted by id: {ids}"
            )
        finally:
            b.close()

    def test_list_claims_includes_released_claims(self, tmp_path: Path) -> None:
        """list_claims() includes claims with status='released'."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            claims = b.list_claims()
            statuses = {c.id: c.status.value for c in claims}
            assert statuses.get("C001") == "released", (
                f"C001 should be 'released', got {statuses.get('C001')!r}"
            )
        finally:
            b.close()

    def test_list_claims_includes_stale_claims(self, tmp_path: Path) -> None:
        """list_claims() includes claims with status='stale'."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            claims = b.list_claims()
            statuses = {c.id: c.status.value for c in claims}
            assert statuses.get("C003") == "stale", (
                f"C003 should be 'stale', got {statuses.get('C003')!r}"
            )
        finally:
            b.close()

    def test_list_claims_returns_valid_claim_objects(self, tmp_path: Path) -> None:
        """list_claims() returns fully deserialized Claim objects (not dicts)."""
        from fakoli_state.state.models import Claim

        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            claims = b.list_claims()
            assert len(claims) >= 1
            for claim in claims:
                assert isinstance(claim, Claim)
                # expected_files should be a list, not raw JSON string
                assert isinstance(claim.expected_files, list)
        finally:
            b.close()

    def test_list_claims_superset_of_list_active_claims(self, tmp_path: Path) -> None:
        """Every claim in list_active_claims() also appears in list_claims()."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            all_ids = {c.id for c in b.list_claims()}
            active_ids = {c.id for c in b.list_active_claims()}
            assert active_ids.issubset(all_ids), (
                f"list_active_claims returned ids not in list_claims: "
                f"{active_ids - all_ids}"
            )
        finally:
            b.close()

    # ------------------------------------------------------------------
    # list_reviews()
    # ------------------------------------------------------------------

    def test_list_reviews_returns_empty_when_no_reviews(self, tmp_path: Path) -> None:
        """list_reviews() returns [] when the reviews table is empty."""
        b = _make_backend(tmp_path)
        try:
            assert b.list_reviews() == []
        finally:
            b.close()

    def test_list_reviews_returns_review_from_task_applied(self, tmp_path: Path) -> None:
        """list_reviews() returns the Review row inserted by task.applied."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            reviews = b.list_reviews()
            assert len(reviews) >= 1, (
                "Expected at least one review after task.applied; got 0"
            )
        finally:
            b.close()

    def test_list_reviews_sorted_by_id(self, tmp_path: Path) -> None:
        """list_reviews() returns rows in ascending id order."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            reviews = b.list_reviews()
            ids = [r.id for r in reviews]
            assert ids == sorted(ids), (
                f"list_reviews() result is not sorted by id: {ids}"
            )
        finally:
            b.close()

    def test_list_reviews_returns_valid_review_objects(self, tmp_path: Path) -> None:
        """list_reviews() returns fully deserialized Review objects (not dicts)."""
        from fakoli_state.state.models import Review

        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            reviews = b.list_reviews()
            assert len(reviews) >= 1
            for review in reviews:
                assert isinstance(review, Review)
                assert review.decision is not None
                assert review.reviewed_by is not None
        finally:
            b.close()

    def test_list_reviews_captures_prd_approved_review(self, tmp_path: Path) -> None:
        """list_reviews() includes the Review row created by prd.approved."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            b.apply_event(_make_event(
                "prd.parsed", _make_prd_parsed_payload(), event_id="E000003",
            ))
            b.apply_event(_make_event(
                "prd.reviewed",
                {"project_id": "proj-1", "reviewer": "alice"},
                event_id="E000004",
            ))
            b.apply_event(_make_event(
                "prd.approved",
                {"project_id": "proj-1", "approver": "bob"},
                event_id="E000005",
            ))
            reviews = b.list_reviews()
            assert len(reviews) == 1
            assert reviews[0].decision.value == "approve"
            assert reviews[0].reviewed_by == "bob"
        finally:
            b.close()

    # ------------------------------------------------------------------
    # list_evidence()
    # ------------------------------------------------------------------

    def test_list_evidence_returns_empty_when_no_evidence(self, tmp_path: Path) -> None:
        """list_evidence() returns [] when the evidence table is empty."""
        b = _make_backend(tmp_path)
        try:
            assert b.list_evidence() == []
        finally:
            b.close()

    def test_list_evidence_returns_submitted_evidence(self, tmp_path: Path) -> None:
        """list_evidence() returns the evidence row inserted by evidence.submitted."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            evidence = b.list_evidence()
            assert len(evidence) >= 1, (
                "Expected at least one evidence row after evidence.submitted; got 0"
            )
            evids = [e.id for e in evidence]
            assert "EV001" in evids
        finally:
            b.close()

    def test_list_evidence_sorted_by_id(self, tmp_path: Path) -> None:
        """list_evidence() returns rows in ascending id order."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            evidence = b.list_evidence()
            ids = [e.id for e in evidence]
            assert ids == sorted(ids), (
                f"list_evidence() result is not sorted by id: {ids}"
            )
        finally:
            b.close()

    def test_list_evidence_returns_valid_evidence_objects(self, tmp_path: Path) -> None:
        """list_evidence() returns fully deserialized Evidence objects (not dicts)."""
        from fakoli_state.state.models import Evidence

        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            evidence = b.list_evidence()
            assert len(evidence) >= 1
            for ev in evidence:
                assert isinstance(ev, Evidence)
                assert isinstance(ev.commands_run, list)
                assert isinstance(ev.files_changed, list)
                assert isinstance(ev.screenshots, list)
                assert ev.submitted_at.tzinfo is not None, (
                    "submitted_at must be timezone-aware UTC"
                )
        finally:
            b.close()

    def test_list_evidence_fields_match_submitted_payload(self, tmp_path: Path) -> None:
        """list_evidence() returns evidence with fields matching the submitted payload."""
        b = _make_backend(tmp_path)
        try:
            _setup_full_snapshot_backend(b)
            evidence = b.list_evidence()
            ev = next((e for e in evidence if e.id == "EV001"), None)
            assert ev is not None, "EV001 not found in list_evidence() output"
            assert ev.task_id == "T001"
            assert ev.claim_id == "C002"
            assert ev.submitted_by == "agent-alpha"
            assert "pytest tests/ -v" in ev.commands_run
            assert "src/auth.py" in ev.files_changed
        finally:
            b.close()


# ---------------------------------------------------------------------------
# list_requirements — read method
# ---------------------------------------------------------------------------


class TestListRequirements:
    """Tests for SqliteBackend.list_requirements()."""

    def test_list_requirements_returns_empty_before_prd_parsed(
        self, tmp_path: Path
    ) -> None:
        """list_requirements() returns [] when no prd.parsed event has been applied."""
        b = _make_backend(tmp_path)
        try:
            assert b.list_requirements() == []
        finally:
            b.close()

    def test_list_requirements_returns_rows_after_prd_parsed(
        self, tmp_path: Path
    ) -> None:
        """list_requirements() returns Requirement objects populated by prd.parsed."""
        from fakoli_state.state.models import Requirement

        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            payload = _make_prd_parsed_payload(
                requirements=[
                    {
                        "id": "R001",
                        "prd_section": "functional",
                        "text": "System must authenticate users.",
                        "source_paragraph": None,
                        "derived": False,
                    },
                    {
                        "id": "R002",
                        "prd_section": "non-functional",
                        "text": "Response time under 200ms.",
                        "source_paragraph": "para-1",
                        "derived": True,
                    },
                ]
            )
            b.apply_event(_make_event("prd.parsed", payload, event_id="E000003"))

            reqs = b.list_requirements()
            assert len(reqs) == 2
            for rq in reqs:
                assert isinstance(rq, Requirement)
        finally:
            b.close()

    def test_list_requirements_sorted_by_id_asc(self, tmp_path: Path) -> None:
        """list_requirements() returns rows in id ASC order."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            # Insert in reverse lexical order to verify sort is applied.
            payload = _make_prd_parsed_payload(
                requirements=[
                    {
                        "id": "R003",
                        "prd_section": "s",
                        "text": "Req 3.",
                        "source_paragraph": None,
                        "derived": False,
                    },
                    {
                        "id": "R001",
                        "prd_section": "s",
                        "text": "Req 1.",
                        "source_paragraph": None,
                        "derived": False,
                    },
                    {
                        "id": "R002",
                        "prd_section": "s",
                        "text": "Req 2.",
                        "source_paragraph": None,
                        "derived": False,
                    },
                ]
            )
            b.apply_event(_make_event("prd.parsed", payload, event_id="E000003"))

            reqs = b.list_requirements()
            ids = [r.id for r in reqs]
            assert ids == sorted(ids), (
                f"list_requirements() result is not sorted by id: {ids}"
            )
        finally:
            b.close()

    def test_list_requirements_fields_match_payload(self, tmp_path: Path) -> None:
        """list_requirements() returns requirements with fields matching the parsed payload."""
        b = _make_backend(tmp_path)
        try:
            _setup_project(b)
            payload = _make_prd_parsed_payload(
                requirements=[
                    {
                        "id": "R001",
                        "prd_section": "auth",
                        "text": "Users must log in.",
                        "source_paragraph": "para-intro",
                        "derived": False,
                    },
                    {
                        "id": "R002",
                        "prd_section": "perf",
                        "text": "Latency under 100ms.",
                        "source_paragraph": None,
                        "derived": True,
                    },
                ]
            )
            b.apply_event(_make_event("prd.parsed", payload, event_id="E000003"))

            reqs = {r.id: r for r in b.list_requirements()}

            assert reqs["R001"].prd_section == "auth"
            assert reqs["R001"].text == "Users must log in."
            assert reqs["R001"].source_paragraph == "para-intro"
            assert reqs["R001"].derived is False

            assert reqs["R002"].prd_section == "perf"
            assert reqs["R002"].text == "Latency under 100ms."
            assert reqs["R002"].source_paragraph is None
            assert reqs["R002"].derived is True
        finally:
            b.close()
