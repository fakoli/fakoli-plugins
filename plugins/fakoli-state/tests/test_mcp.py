"""Integration tests for the fakoli-state MCP server (13 tools).

All tests use the FastMCP in-process Client — no HTTP, no mocking.
Each test runs against a real SqliteBackend in a per-test tmp_path.

The server resolves state via Path.cwd() / ".fakoli-state", so every
test uses monkeypatch.chdir(tmp_path) to isolate cwd.

FastMCP 3.3.1 in-memory transport: Client(mcp) passes the server directly.

Return-value access:
  - Pydantic model returns:  result.structured_content  → dict
  - None returns:             result.data               → None
  - list returns:             result.data               → list
  - dict returns:             result.data / result.structured_content → dict

We use a unified _data() helper that covers all four cases cleanly.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from fastmcp import Client
from fastmcp.exceptions import ToolError

from fakoli_state.mcp_server import mcp

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UTC = UTC
_T0 = datetime(2026, 5, 24, 18, 0, 0, tzinfo=_UTC)

# ---------------------------------------------------------------------------
# Result accessor
# ---------------------------------------------------------------------------


def _data(result: Any) -> Any:
    """Unified accessor for FastMCP call_tool() results.

    FastMCP 3.3.1 behavior:
    - Pydantic model return → result.data is a Root object (not subscriptable);
      result.structured_content is a plain dict.
    - list return           → result.data is a Python list (subscriptable).
    - dict return           → result.data is a Python dict (subscriptable).
    - None return           → result.data is None; result.content is [].

    This helper normalises everything to a plain Python value.
    """
    if result.data is None:
        return None
    d = result.data
    # Root objects are not dicts/lists; fall back to structured_content
    if not isinstance(d, (dict, list, str, int, float, bool)):
        return result.structured_content
    return d


# ---------------------------------------------------------------------------
# State-setup helpers (no mocking — real SQLite)
# ---------------------------------------------------------------------------


def _init_state_dir(tmp_path: Path, project_name: str = "Test Project") -> Path:
    """Create .fakoli-state/ in tmp_path with project + events initialised.

    Mirrors what `fakoli-state init` does; reuses SqliteBackend + event
    factories from the sqlite test layer so we don't duplicate CLI coupling.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.backend import PENDING_EVENT_ID
    from fakoli_state.state.models import Event
    from fakoli_state.state.sqlite import SqliteBackend

    state_dir = tmp_path / ".fakoli-state"
    state_dir.mkdir()
    (state_dir / "packets").mkdir()
    (state_dir / "snapshots").mkdir()
    (state_dir / "events.jsonl").touch()

    clock = SystemClock()
    now = clock.now()

    b = SqliteBackend(
        db_path=str(state_dir / "state.db"),
        events_path=str(state_dir / "events.jsonl"),
        clock=clock,
    )
    b.initialize()

    project_id = "proj-test"
    b.apply_event(Event(
        id=PENDING_EVENT_ID,
        timestamp=now,
        actor="test",
        action="project.created",
        target_kind="project",
        target_id=project_id,
        payload_json={
            "id": project_id,
            "name": project_name,
            "description": "A test project.",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    ))
    b.apply_event(Event(
        id=PENDING_EVENT_ID,
        timestamp=now,
        actor="test",
        action="state.initialized",
        target_kind="project",
        target_id=project_id,
        payload_json={},
    ))
    b.close()
    return state_dir


def _add_prd(state_dir: Path, status: str = "reviewed") -> None:
    """Insert a PRD row directly via SQLite.

    status options: 'draft', 'reviewed', 'approved'
    """
    db_path = str(state_dir / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO prds
        (project_id, status, summary, goals, non_goals, requirements,
         acceptance_criteria, risks, open_questions)
        VALUES ('proj-test', ?, 'Test summary.', '[]', '[]', '[]', '[]', '[]', '[]')
    """, (status,))
    conn.commit()
    conn.close()


def _add_feature(state_dir: Path, feat_id: str = "F001", title: str = "Test Feature") -> None:
    """Insert a feature row directly via SQLite."""
    db_path = str(state_dir / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO features "
        "(id, title, description, status, requirements, tasks) "
        "VALUES (?, ?, 'desc', 'proposed', '[]', '[]')",
        (feat_id, title),
    )
    conn.commit()
    conn.close()


def _add_task(
    state_dir: Path,
    *,
    task_id: str = "T001",
    feature_id: str = "F001",
    title: str = "Test Task",
    status: str = "ready",
    priority: str = "medium",
    dependencies: list[str] | None = None,
    conflict_groups: list[str] | None = None,
    scores: dict[str, Any] | None = None,
    likely_files: list[str] | None = None,
) -> None:
    """Insert a task row directly via SQLite."""
    db_path = str(state_dir / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO tasks
        (id, feature_id, title, description, status, priority,
         dependencies, conflict_groups, scores, acceptance_criteria,
         implementation_notes, verification, likely_files,
         created_at, updated_at)
        VALUES (?, ?, ?, 'A test task.', ?, ?,
         ?, ?, ?, '["Tests pass."]', '[]', '{}', ?,
         ?, ?)""",
        (
            task_id,
            feature_id,
            title,
            status,
            priority,
            json.dumps(dependencies or []),
            json.dumps(conflict_groups or []),
            json.dumps(scores or {}),
            json.dumps(likely_files or []),
            _T0.isoformat(),
            _T0.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _add_active_claim(
    state_dir: Path,
    *,
    claim_id: str = "C001",
    task_id: str = "T001",
    claimed_by: str = "agent-x",
    expected_files: list[str] | None = None,
    minutes_until_expiry: int = 30,
) -> None:
    """Insert an active claim row directly via SQLite."""
    db_path = str(state_dir / "state.db")
    now = datetime.now(UTC)
    expires = (now + timedelta(minutes=minutes_until_expiry)).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO claims
        (id, task_id, claimed_by, claim_type, status, expected_files,
         created_at, lease_expires_at, last_heartbeat_at)
        VALUES (?, ?, ?, 'task', 'active', ?, ?, ?, ?)""",
        (
            claim_id,
            task_id,
            claimed_by,
            json.dumps(expected_files or []),
            now.isoformat(),
            expires,
            now.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sync runner — bridges pytest sync to async FastMCP client
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:
    """Run a coroutine synchronously (pytest without pytest-asyncio)."""
    return asyncio.run(coro)


# ===========================================================================
# Test: list_tools — all 13 registered
# ===========================================================================

class TestListTools:
    def test_list_tools_returns_all_thirteen(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> set[str]:
            async with Client(mcp) as c:
                tools = await c.list_tools()
                return {t.name for t in tools}

        names = _run(run())
        expected = {
            "get_project_summary", "list_tasks", "get_task", "get_next_task",
            "claim_task", "release_task", "renew_claim",
            "generate_work_packet", "submit_progress", "submit_completion_evidence",
            "check_conflicts", "get_dependency_graph", "update_task_status",
        }
        assert expected <= names, f"Missing tools: {expected - names}"


# ===========================================================================
# Tool 1: get_project_summary
# ===========================================================================

class TestGetProjectSummary:
    def test_happy_path_returns_project_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path, "My Project")
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_task(state_dir, task_id="T002", status="blocked")
        _add_prd(state_dir, status="reviewed")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_project_summary", {}))

        data = _run(run())
        assert data["project_name"] == "My Project"
        assert data["project_id"] == "proj-test"
        assert data["prd_status"] == "reviewed"
        assert data["ready_task_count"] == 1
        assert data["blocked_task_count"] == 1
        assert "task_counts" in data

    def test_error_when_not_initialized(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ToolError raised when .fakoli-state/ is absent."""
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("get_project_summary", {})

        with pytest.raises(ToolError, match="not initialized|fakoli-state"):
            _run(run())

    def test_task_counts_all_statuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        for i, status in enumerate(["ready", "blocked", "done", "proposed"]):
            _add_task(state_dir, task_id=f"T{i+1:03}", status=status)
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_project_summary", {}))

        data = _run(run())
        counts = data["task_counts"]
        assert counts["ready"] == 1
        assert counts["blocked"] == 1
        assert counts["done"] == 1
        assert counts["proposed"] == 1


# ===========================================================================
# Tool 2: list_tasks
# ===========================================================================

class TestListTasks:
    def test_happy_path_returns_all_tasks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_task(state_dir, task_id="T002", status="blocked")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("list_tasks", {}))

        tasks = _run(run())
        assert len(tasks) == 2
        ids = {t["id"] for t in tasks}
        assert ids == {"T001", "T002"}

    def test_filter_by_status(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_task(state_dir, task_id="T002", status="blocked")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("list_tasks", {"status": "ready"}))

        tasks = _run(run())
        assert len(tasks) == 1
        assert tasks[0]["id"] == "T001"

    def test_filter_by_claimed_by(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        _add_task(state_dir, task_id="T002", status="claimed")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-a")
        _add_active_claim(state_dir, claim_id="C002", task_id="T002", claimed_by="agent-b")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("list_tasks", {"claimed_by": "agent-a"}))

        tasks = _run(run())
        assert len(tasks) == 1
        assert tasks[0]["id"] == "T001"

    def test_returns_empty_when_no_tasks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("list_tasks", {}))

        tasks = _run(run())
        assert tasks == []


# ===========================================================================
# Tool 3: get_task
# ===========================================================================

class TestGetTask:
    def test_happy_path_returns_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", title="My Task", status="ready", priority="high")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_task", {"task_id": "T001"}))

        task = _run(run())
        assert task["id"] == "T001"
        assert task["title"] == "My Task"
        assert task["status"] == "ready"
        assert task["priority"] == "high"

    def test_error_on_unknown_task_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("get_task", {"task_id": "nonexistent"})

        with pytest.raises(ToolError, match="not found|nonexistent"):
            _run(run())


# ===========================================================================
# Tool 4: get_next_task
# ===========================================================================

class TestGetNextTask:
    def test_happy_path_returns_highest_priority_ready_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready", priority="low")
        _add_task(state_dir, task_id="T002", status="ready", priority="high")
        _add_task(state_dir, task_id="T003", status="ready", priority="medium")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_next_task", {}))

        task = _run(run())
        assert task is not None
        assert task["id"] == "T002"
        assert task["priority"] == "high"

    def test_returns_none_when_no_ready_tasks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="blocked")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_next_task", {}))

        task = _run(run())
        assert task is None

    def test_priority_ordering_high_over_medium_over_low(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """HIGH > MEDIUM > LOW — same feature, different priorities."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        for task_id, priority in [("T001", "low"), ("T002", "medium"), ("T003", "high")]:
            _add_task(state_dir, task_id=task_id, status="ready", priority=priority)
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_next_task", {}))

        task = _run(run())
        assert task["id"] == "T003"

    def test_skips_task_with_unmet_dependency(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ready task whose dep is not done must not be returned."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready", priority="high",
                  dependencies=["T002"])
        _add_task(state_dir, task_id="T002", status="ready", priority="low")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_next_task", {}))

        # T001 has unmet dep; T002 has no deps — T002 is the only eligible task
        task = _run(run())
        assert task is not None
        assert task["id"] == "T002"

    def test_tiebreak_by_id_asc_when_same_priority_and_suitability(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same priority + no scores → tiebreak by id ascending."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        for task_id in ["T003", "T001", "T002"]:
            _add_task(state_dir, task_id=task_id, status="ready", priority="medium")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_next_task", {}))

        task = _run(run())
        assert task["id"] == "T001"


# ===========================================================================
# Tool 5: claim_task
# ===========================================================================

class TestClaimTask:
    def test_happy_path_returns_claim_response(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_prd(state_dir, status="reviewed")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("claim_task", {
                    "task_id": "T001",
                    "claimed_by": "agent-x",
                    "expected_files": ["src/foo.py"],
                }))

        claim = _run(run())
        assert claim["task_id"] == "T001"
        assert claim["claimed_by"] == "agent-x"
        assert "id" in claim
        assert "lease_expires_at" in claim
        assert claim["expected_files"] == ["src/foo.py"]

    def test_error_when_prd_is_draft(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Gate: PRD in 'draft' status → ToolError."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_prd(state_dir, status="draft")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("claim_task", {
                    "task_id": "T001",
                    "claimed_by": "agent-x",
                })

        with pytest.raises(ToolError, match="draft|PRD"):
            _run(run())

    def test_error_when_prd_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Gate: no PRD at all → ToolError."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("claim_task", {
                    "task_id": "T001",
                    "claimed_by": "agent-x",
                })

        with pytest.raises(ToolError, match="missing|draft|PRD"):
            _run(run())

    def test_error_on_double_claim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claiming an already-claimed task raises ToolError (ClaimError bubble)."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_prd(state_dir, status="reviewed")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("claim_task", {"task_id": "T001", "claimed_by": "agent-x"})
                await c.call_tool("claim_task", {"task_id": "T001", "claimed_by": "agent-y"})

        with pytest.raises(ToolError):
            _run(run())


# ===========================================================================
# Tool 6: release_task
# ===========================================================================

class TestReleaseTask:
    def test_happy_path_releases_claim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("release_task", {
                    "task_id": "T001",
                    "actor": "agent-x",
                }))

        resp = _run(run())
        assert resp["released"] is True
        assert resp["claim_id"] == "C001"

    def test_error_when_no_active_claim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("release_task", {
                    "task_id": "T001",
                    "actor": "agent-x",
                })

        with pytest.raises(ToolError, match="No active claim|released|never claimed"):
            _run(run())

    def test_error_when_actor_does_not_own_claim(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Critic-PR#45 regression: foreign actor must not be able to release."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("release_task", {
                    "task_id": "T001",
                    "actor": "agent-y",
                })

        with pytest.raises(ToolError):
            _run(run())


# ===========================================================================
# Tool 7: renew_claim
# ===========================================================================

class TestRenewClaim:
    def test_happy_path_returns_updated_lease(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x",
                          minutes_until_expiry=5)
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("renew_claim", {
                    "task_id": "T001",
                    "actor": "agent-x",
                    "extend_seconds": 900,
                }))

        resp = _run(run())
        assert "lease_expires_at" in resp
        new_expiry = datetime.fromisoformat(resp["lease_expires_at"])
        assert new_expiry > datetime.now(UTC)

    def test_error_when_no_active_claim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("renew_claim", {
                    "task_id": "T001",
                    "actor": "agent-x",
                })

        with pytest.raises(ToolError, match="No active claim|released|expired"):
            _run(run())

    def test_error_when_actor_does_not_own_claim(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Critic-PR#45 regression: foreign actor must not be able to renew."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x",
                          minutes_until_expiry=5)
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("renew_claim", {
                    "task_id": "T001",
                    "actor": "agent-y",
                })

        with pytest.raises(ToolError):
            _run(run())


# ===========================================================================
# Tool 8: generate_work_packet
# ===========================================================================

class TestGenerateWorkPacket:
    def test_markdown_format_returns_string_content(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", title="Build Widget", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("generate_work_packet", {
                    "task_id": "T001",
                    "format": "markdown",
                }))

        resp = _run(run())
        assert resp["format"] == "markdown"
        assert isinstance(resp["content"], str)
        assert "Build Widget" in resp["content"]

    def test_json_format_returns_dict_content(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", title="Build Widget", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("generate_work_packet", {
                    "task_id": "T001",
                    "format": "json",
                }))

        resp = _run(run())
        assert resp["format"] == "json"
        assert isinstance(resp["content"], dict)

    def test_error_on_unknown_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("generate_work_packet", {"task_id": "NOPE"})

        with pytest.raises(ToolError, match="not found|NOPE"):
            _run(run())


# ===========================================================================
# Tool 9: submit_progress
# ===========================================================================

class TestSubmitProgress:
    def test_happy_path_returns_recorded_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("submit_progress", {
                    "task_id": "T001",
                    "actor": "agent-x",
                    "notes": "Half done.",
                }))

        resp = _run(run())
        assert resp["recorded"] is True

    def test_does_not_change_task_status(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """submit_progress records a note but must not change the task status."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                await c.call_tool("submit_progress", {
                    "task_id": "T001",
                    "actor": "agent-x",
                    "notes": "Still in progress.",
                })
                return _data(await c.call_tool("get_task", {"task_id": "T001"}))

        task = _run(run())
        assert task["status"] == "claimed"

    def test_error_on_unknown_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("submit_progress", {
                    "task_id": "NOPE",
                    "actor": "agent-x",
                    "notes": "n/a",
                })

        with pytest.raises(ToolError, match="not found|NOPE"):
            _run(run())


# ===========================================================================
# Tool 10: submit_completion_evidence
# ===========================================================================

class TestSubmitCompletionEvidence:
    def test_happy_path_transitions_task_to_needs_review(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="in_progress")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("submit_completion_evidence", {
                    "task_id": "T001",
                    "actor": "agent-x",
                    "commands_run": ["pytest tests/ -v"],
                    "files_changed": ["src/foo.py"],
                    "output_excerpt": "3 passed",
                }))

        resp = _run(run())
        assert "evidence_id" in resp
        assert resp["evidence_id"].startswith("EV")
        assert resp["task_status"] == "needs_review"

    def test_error_when_no_active_claim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Must have an active claim before submitting evidence."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("submit_completion_evidence", {
                    "task_id": "T001",
                    "actor": "agent-x",
                    "commands_run": ["pytest"],
                    "files_changed": [],
                })

        with pytest.raises(ToolError, match="No active claim|Claim"):
            _run(run())

    def test_error_on_unknown_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("submit_completion_evidence", {
                    "task_id": "NOPE",
                    "actor": "agent-x",
                    "commands_run": [],
                    "files_changed": [],
                })

        with pytest.raises(ToolError, match="not found|NOPE"):
            _run(run())

    def test_error_when_actor_does_not_own_claim(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Critic-PR#45 P1 regression: foreign actor cannot force-complete a claim."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="in_progress")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("submit_completion_evidence", {
                    "task_id": "T001",
                    "actor": "agent-y",  # owner is agent-x
                    "commands_run": ["pytest"],
                    "files_changed": ["src/foo.py"],
                })

        with pytest.raises(ToolError, match="claim owner|claimed by"):
            _run(run())

    def test_error_when_commands_run_is_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Critic-PR#45 regression: backend rejects empty commands_run on active claim."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="in_progress")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("submit_completion_evidence", {
                    "task_id": "T001",
                    "actor": "agent-x",
                    "commands_run": [],  # backend should reject
                    "files_changed": ["src/foo.py"],
                })

        with pytest.raises(ToolError):
            _run(run())


# ===========================================================================
# Tool 11: check_conflicts
# ===========================================================================

class TestCheckConflicts:
    def test_no_conflicts_when_no_active_claims(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("check_conflicts", {
                    "task_id": "T001",
                    "proposed_files": ["src/foo.py"],
                }))

        resp = _run(run())
        assert resp["conflicts"] == []

    def test_conflict_detected_when_file_overlaps_other_claim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Prior claim on T002 touching src/foo.py conflicts with T001's proposed_files."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_task(state_dir, task_id="T002", status="claimed")
        _add_active_claim(state_dir, claim_id="C002", task_id="T002", claimed_by="agent-b",
                          expected_files=["src/foo.py", "src/bar.py"])
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("check_conflicts", {
                    "task_id": "T001",
                    "proposed_files": ["src/foo.py"],
                }))

        resp = _run(run())
        assert len(resp["conflicts"]) == 1
        conflict = resp["conflicts"][0]
        assert conflict["file"] == "src/foo.py"
        assert conflict["task_id"] == "T002"
        assert conflict["claimed_by"] == "agent-b"
        assert "claim_id" in conflict

    def test_own_claim_excluded_from_conflicts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T001's own active claim must not appear as a conflict for T001."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="claimed")
        _add_active_claim(state_dir, claim_id="C001", task_id="T001", claimed_by="agent-x",
                          expected_files=["src/foo.py"])
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("check_conflicts", {
                    "task_id": "T001",
                    "proposed_files": ["src/foo.py"],
                }))

        resp = _run(run())
        assert resp["conflicts"] == []


# ===========================================================================
# Tool 12: get_dependency_graph
# ===========================================================================

class TestGetDependencyGraph:
    def test_happy_path_all_scope_returns_nodes_and_edges(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="done")
        _add_task(state_dir, task_id="T002", status="ready", dependencies=["T001"])
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_dependency_graph", {"scope": "all"}))

        resp = _run(run())
        node_ids = {n["id"] for n in resp["nodes"]}
        assert "T001" in node_ids
        assert "T002" in node_ids
        assert any(e["from"] == "T001" and e["to"] == "T002" for e in resp["edges"])

    def test_ready_to_claim_excludes_tasks_with_unmet_deps(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        # T001 ready but dep T002 not done → NOT ready_to_claim
        _add_task(state_dir, task_id="T001", status="ready", dependencies=["T002"])
        # T002 ready, no deps → ready_to_claim
        _add_task(state_dir, task_id="T002", status="ready")
        # T003 ready, dep T004 (done) → ready_to_claim
        _add_task(state_dir, task_id="T003", status="ready", dependencies=["T004"])
        _add_task(state_dir, task_id="T004", status="done")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_dependency_graph", {"scope": "all"}))

        resp = _run(run())
        ready = set(resp["ready_to_claim"])
        assert "T001" not in ready
        assert "T002" in ready
        assert "T003" in ready
        assert "T004" not in ready

    def test_error_feature_scope_without_target_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("get_dependency_graph", {"scope": "feature"})

        with pytest.raises(ToolError, match="target_id"):
            _run(run())

    def test_task_scope_returns_transitive_deps(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """scope='task' returns the target task plus all transitive dependencies."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="done")
        _add_task(state_dir, task_id="T002", status="done", dependencies=["T001"])
        _add_task(state_dir, task_id="T003", status="ready", dependencies=["T002"])
        _add_task(state_dir, task_id="T004", status="ready")  # unrelated
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_dependency_graph", {
                    "scope": "task",
                    "target_id": "T003",
                }))

        resp = _run(run())
        node_ids = {n["id"] for n in resp["nodes"]}
        assert "T001" in node_ids
        assert "T002" in node_ids
        assert "T003" in node_ids
        assert "T004" not in node_ids


# ===========================================================================
# Tool 13: update_task_status
# ===========================================================================

class TestUpdateTaskStatus:
    def test_drafted_to_ready(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="drafted")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("update_task_status", {
                    "task_id": "T001",
                    "to_status": "ready",
                    "actor": "agent-x",
                }))

        resp = _run(run())
        assert resp["from_status"] == "drafted"
        assert resp["to_status"] == "ready"

    def test_ready_to_drafted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("update_task_status", {
                    "task_id": "T001",
                    "to_status": "drafted",
                    "actor": "agent-x",
                }))

        resp = _run(run())
        assert resp["from_status"] == "ready"
        assert resp["to_status"] == "drafted"

    def test_in_progress_to_blocked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="in_progress")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("update_task_status", {
                    "task_id": "T001",
                    "to_status": "blocked",
                    "actor": "agent-x",
                    "reason": "Waiting for dependency.",
                }))

        resp = _run(run())
        assert resp["from_status"] == "in_progress"
        assert resp["to_status"] == "blocked"

    def test_blocked_to_in_progress(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """blocked → in_progress is allowed (blocked toggle for claimed/in_progress tasks)."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="blocked")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("update_task_status", {
                    "task_id": "T001",
                    "to_status": "in_progress",
                    "actor": "agent-x",
                }))

        resp = _run(run())
        assert resp["from_status"] == "blocked"
        assert resp["to_status"] == "in_progress"

    def test_error_disallowed_transition(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """proposed → ready is not in the allowed set → ToolError."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="proposed")
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("update_task_status", {
                    "task_id": "T001",
                    "to_status": "ready",
                    "actor": "agent-x",
                })

        with pytest.raises(ToolError, match="Cannot transition|proposed|none"):
            _run(run())

    def test_error_on_unknown_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_state_dir(tmp_path)
        monkeypatch.chdir(tmp_path)

        async def run() -> None:
            async with Client(mcp) as c:
                await c.call_tool("update_task_status", {
                    "task_id": "NOPE",
                    "to_status": "ready",
                    "actor": "agent-x",
                })

        with pytest.raises(ToolError, match="not found|NOPE"):
            _run(run())


# ===========================================================================
# End-to-end: full agent lifecycle
# ===========================================================================

class TestFullAgentLifecycle:
    """claim_task → renew_claim → submit_progress → submit_completion_evidence.

    After evidence submission the claim is auto-released; a subsequent
    release_task call must fail with "no active claim".
    """

    def test_full_lifecycle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_prd(state_dir, status="approved")
        monkeypatch.chdir(tmp_path)

        async def run() -> bool:
            async with Client(mcp) as c:
                # 1. Claim
                claim = _data(await c.call_tool("claim_task", {
                    "task_id": "T001",
                    "claimed_by": "agent-lifecycle",
                    "expected_files": ["src/widget.py"],
                }))
                assert claim["task_id"] == "T001"
                assert claim["claimed_by"] == "agent-lifecycle"

                # 2. Renew
                renew = _data(await c.call_tool("renew_claim", {
                    "task_id": "T001",
                    "actor": "agent-lifecycle",
                    "extend_seconds": 600,
                }))
                assert "lease_expires_at" in renew

                # 3. Submit progress
                progress = _data(await c.call_tool("submit_progress", {
                    "task_id": "T001",
                    "actor": "agent-lifecycle",
                    "notes": "50% complete.",
                }))
                assert progress["recorded"] is True

                # 4. Submit completion evidence — auto-releases claim
                evidence = _data(await c.call_tool("submit_completion_evidence", {
                    "task_id": "T001",
                    "actor": "agent-lifecycle",
                    "commands_run": ["pytest tests/"],
                    "files_changed": ["src/widget.py"],
                    "output_excerpt": "All tests pass.",
                }))
                assert evidence["task_status"] == "needs_review"
                assert evidence["evidence_id"].startswith("EV")
            return True

        assert _run(run()) is True

        # After evidence submission the claim is auto-released.
        # Attempting release again must fail with "no active claim".
        async def verify_released() -> None:
            async with Client(mcp) as c:
                with pytest.raises(ToolError, match="No active claim|released"):
                    await c.call_tool("release_task", {
                        "task_id": "T001",
                        "actor": "agent-lifecycle",
                    })

        _run(verify_released())


# ===========================================================================
# End-to-end: check_conflicts sees conflict created by claim_task
# ===========================================================================

class TestConflictsAfterClaim:
    def test_conflict_appears_after_claim_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """claim_task populates expected_files in the active claim; check_conflicts sees them."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="ready")
        _add_task(state_dir, task_id="T002", status="ready")
        _add_prd(state_dir, status="reviewed")
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                # Agent A claims T001 with src/shared.py
                await c.call_tool("claim_task", {
                    "task_id": "T001",
                    "claimed_by": "agent-a",
                    "expected_files": ["src/shared.py"],
                })
                # Agent B checks conflicts for T002 also touching src/shared.py
                return _data(await c.call_tool("check_conflicts", {
                    "task_id": "T002",
                    "proposed_files": ["src/shared.py"],
                }))

        resp = _run(run())
        assert len(resp["conflicts"]) == 1
        assert resp["conflicts"][0]["file"] == "src/shared.py"
        assert resp["conflicts"][0]["task_id"] == "T001"


# ===========================================================================
# End-to-end: get_dependency_graph ready_to_claim after seeding deps
# ===========================================================================

class TestDependencyGraphReadyToClaim:
    def test_ready_to_claim_correct_after_dep_seeding(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T001", status="done")
        _add_task(state_dir, task_id="T002", status="ready", dependencies=["T001"])
        _add_task(state_dir, task_id="T003", status="ready", dependencies=["T002"])
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_dependency_graph", {"scope": "all"}))

        resp = _run(run())
        ready = set(resp["ready_to_claim"])
        assert "T002" in ready      # dep T001 is done
        assert "T003" not in ready  # dep T002 is not done
        assert "T001" not in ready  # done tasks are not ready_to_claim


# ===========================================================================
# End-to-end: get_next_task priority ordering with sequential claiming
# ===========================================================================

class TestGetNextTaskPriorityOrdering:
    def test_priority_high_over_medium_over_low(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T_LOW",  status="ready", priority="low")
        _add_task(state_dir, task_id="T_MED",  status="ready", priority="medium")
        _add_task(state_dir, task_id="T_HIGH", status="ready", priority="high")
        _add_prd(state_dir, status="reviewed")
        monkeypatch.chdir(tmp_path)

        results: list[str] = []

        async def run() -> None:
            async with Client(mcp) as c:
                for _ in range(3):
                    next_task = _data(await c.call_tool("get_next_task", {}))
                    if next_task is None:
                        break
                    results.append(next_task["id"])
                    await c.call_tool("claim_task", {
                        "task_id": next_task["id"],
                        "claimed_by": "ordering-agent",
                    })

        _run(run())
        assert results[0] == "T_HIGH", f"Expected T_HIGH first, got {results}"
        assert results[1] == "T_MED",  f"Expected T_MED second, got {results}"
        assert results[2] == "T_LOW",  f"Expected T_LOW third, got {results}"

    def test_tiebreak_agent_suitability_desc_then_id_asc(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same priority: agent_suitability desc tiebreak, then id asc."""
        state_dir = _init_state_dir(tmp_path)
        _add_feature(state_dir)
        _add_task(state_dir, task_id="T_A", status="ready", priority="medium",
                  scores={"agent_suitability": 5})
        _add_task(state_dir, task_id="T_B", status="ready", priority="medium",
                  scores={"agent_suitability": 2})
        monkeypatch.chdir(tmp_path)

        async def run() -> Any:
            async with Client(mcp) as c:
                return _data(await c.call_tool("get_next_task", {}))

        task = _run(run())
        assert task["id"] == "T_A"
