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
from fakoli_state.state.backend import SchemaMismatch, TransactionAborted
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
