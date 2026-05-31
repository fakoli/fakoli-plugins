"""Replay-equivalence: prove the audit guarantee on a realistic event stream.

SL-1 (docs/roadmap.md). The existing ``test_sqlite.py`` audit test replays
THREE hand-built synthetic events. That is necessary but not sufficient: it
does not prove replay determinism for the event stream a real project produces.

This module drives the actual CLI through a full lifecycle
(``init → prd parse → plan → score → claim → submit → apply``) in a temp
project — the same path production uses — then:

  1. injects an aborted-transaction tombstone (``error.transaction_aborted``)
     so the replay tombstone-skip branch (``sqlite.py``) is exercised on a
     realistic log, and
  2. replays the resulting ``events.jsonl`` into a scratch database and asserts
     the replayed ``state.db`` is byte-for-byte equivalent (full SQLite dump) to
     the live one.

It also covers the ``fakoli-state replay`` CLI surface itself: the equivalence
check, the divergence exit code, and the safety guard that refuses to rebuild
over the active ``.fakoli-state`` directory.

The ``replay`` marker lets CI surface the equivalence check as its own named
step (see ``.github/workflows/fakoli-state-tests.yml``).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fakoli_state.cli import app

runner = CliRunner()

# A PRD with two features and two tasks — enough to produce a non-trivial event
# stream (features, requirements, tasks, scores, claims, evidence, acceptance).
_FULL_PRD_CONTENT = """\
# Project: Replay Equivalence Project

## Summary

A project used to prove deterministic replay over a realistic event stream.

## Goals

- Convert files correctly.
- Handle errors gracefully.

## Non-Goals

- Support all formats.

## Requirements

- R001: Accept file input.
- R002: Produce file output.
- R003: Handle errors.

## Acceptance Criteria

- Converts files correctly.

## Features

### F001: File Conversion

Convert input files to output format.

**Requirements:** R001, R002

### F002: Error Handling

Handle errors gracefully.

**Requirements:** R003

## Tasks

### T001: Implement converter

**Feature:** F001
**Priority:** high
**Likely files:** src/app/converter.py, src/app/utils.py

**Acceptance criteria:**

- Conversion succeeds for valid input.
- Invalid input raises an error.

**Verification:**

- `pytest tests/test_converter.py -v`

### T002: Implement error handler

**Feature:** F002
**Priority:** medium
**Likely files:** src/app/errors.py

**Acceptance criteria:**

- Errors are reported with context.
- Exit code is non-zero on error.

**Verification:**

- `pytest tests/test_errors.py -v`
"""


# ---------------------------------------------------------------------------
# Helpers (self-contained, mirroring tests/test_cli.py — extracting to a shared
# conftest fixture is a tidy-up, not required here; see test_cli_plan.py note).
# ---------------------------------------------------------------------------


def _invoke(tmp_path: Path, cmd: list[str]):  # type: ignore[no-untyped-def]
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        return runner.invoke(app, cmd, catch_exceptions=False)
    finally:
        os.chdir(original_cwd)


def _dump(db_path: Path) -> str:
    """Full SQLite dump as a string — the equivalence comparison surface."""
    conn = sqlite3.connect(str(db_path))
    try:
        return "\n".join(conn.iterdump()).strip()
    finally:
        conn.close()


def _ready_task_ids(tmp_path: Path) -> list[str]:
    db_path = tmp_path / ".fakoli-state" / "state.db"
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT id FROM tasks WHERE status='ready' ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def _run_full_lifecycle(tmp_path: Path) -> None:
    """init → PRD → plan → score → review → claim → submit → apply (one task)."""
    init = _invoke(tmp_path, ["init", "--name", "Replay Equivalence Project"])
    assert init.exit_code == 0, f"init failed: {init.output}"

    prd_path = tmp_path / ".fakoli-state" / "prd.md"
    prd_path.write_text(_FULL_PRD_CONTENT, encoding="utf-8")

    assert _invoke(tmp_path, ["prd", "parse"]).exit_code == 0
    _invoke(tmp_path, ["prd", "review"])
    _invoke(tmp_path, ["prd", "review", "--approve"])
    assert _invoke(tmp_path, ["plan"]).exit_code == 0
    assert _invoke(tmp_path, ["score"]).exit_code == 0
    _invoke(tmp_path, ["review", "tasks"])

    ready = _ready_task_ids(tmp_path)
    assert ready, "no ready tasks after planning"
    task_id = ready[0]

    # claim → submit → apply (no git: claim warns but succeeds).
    assert _invoke(
        tmp_path, ["claim", task_id, "--actor", "agent-test"]
    ).exit_code == 0
    assert _invoke(
        tmp_path,
        [
            "submit", task_id,
            "--commands", "pytest tests/test_converter.py -v",
            "--files-changed", "src/app/converter.py",
            "--actor", "agent-test",
        ],
    ).exit_code == 0
    assert _invoke(
        tmp_path,
        ["apply", task_id, "--approve", "--reviewer", "human-reviewer"],
    ).exit_code == 0


def _inject_aborted_transaction(tmp_path: Path) -> None:
    """Append an ``error.transaction_aborted`` tombstone to the live log.

    Replay must skip it; this exercises the tombstone-skip branch on a realistic
    log rather than the synthetic 3-event fixture.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.backend import PENDING_EVENT_ID, TransactionAborted
    from fakoli_state.state.models import Event
    from fakoli_state.state.sqlite import SqliteBackend

    state_dir = tmp_path / ".fakoli-state"
    backend = SqliteBackend(
        db_path=str(state_dir / "state.db"),
        events_path=str(state_dir / "events.jsonl"),
        clock=SystemClock(),
    )
    backend.initialize()
    try:
        bad = Event(
            id=PENDING_EVENT_ID,
            timestamp=SystemClock().now(),
            actor="agent-test",
            action="unsupported.action",
            target_kind="project",
            target_id="proj-1",
        )
        with pytest.raises(TransactionAborted):
            backend.apply_event(bad)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# The audit guarantee, on a realistic stream
# ---------------------------------------------------------------------------


@pytest.mark.replay
def test_replay_equivalence_full_lifecycle(tmp_path: Path) -> None:
    """Replay the real lifecycle log; reconstructed state.db is byte-identical."""
    project = tmp_path / "proj"
    project.mkdir()
    _run_full_lifecycle(project)
    _inject_aborted_transaction(project)

    state_dir = project / ".fakoli-state"
    events_path = state_dir / "events.jsonl"
    live_db = state_dir / "state.db"

    # The tombstone-skip branch is genuinely exercised on this log.
    log_text = events_path.read_text(encoding="utf-8")
    assert "error.transaction_aborted" in log_text, (
        "expected an aborted-transaction tombstone in the realistic log"
    )

    live_dump = _dump(live_db)

    # Replay into a scratch directory and compare.
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.sqlite import SqliteBackend

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    scratch_db = scratch / "state.db"
    scratch_events = scratch / "events.jsonl"
    scratch_events.touch()
    b = SqliteBackend(
        db_path=str(scratch_db),
        events_path=str(scratch_events),
        clock=SystemClock(),
    )
    b.initialize()
    try:
        b.replay_from_empty(str(events_path))
    finally:
        b.close()

    replayed_dump = _dump(scratch_db)
    assert replayed_dump == live_dump, (
        "Replayed state.db diverged from the live state.db built by the real "
        "CLI lifecycle — the replay guarantee does not hold for this stream.\n"
        f"live (head):\n{live_dump[:600]}\n\nreplayed (head):\n{replayed_dump[:600]}"
    )


# ---------------------------------------------------------------------------
# The `fakoli-state replay` CLI surface
# ---------------------------------------------------------------------------


@pytest.mark.replay
def test_replay_cli_equivalence_passes(tmp_path: Path) -> None:
    """`replay --from-events ... --against live.db` exits 0 and reports PASSED."""
    project = tmp_path / "proj"
    project.mkdir()
    _run_full_lifecycle(project)

    state_dir = project / ".fakoli-state"
    scratch = tmp_path / "scratch"
    # Run from an unrelated cwd so the active-state-dir guard is not tripped.
    result = _invoke(
        tmp_path,
        [
            "replay",
            "--from-events", str(state_dir / "events.jsonl"),
            "--into", str(scratch),
            "--against", str(state_dir / "state.db"),
        ],
    )
    assert result.exit_code == 0, f"replay failed: {result.output}"
    assert "PASSED" in result.output


@pytest.mark.replay
def test_replay_cli_refuses_active_state_dir(tmp_path: Path) -> None:
    """Safety: --into pointed at the active .fakoli-state is refused (exit 1)."""
    project = tmp_path / "proj"
    project.mkdir()
    _run_full_lifecycle(project)

    state_dir = project / ".fakoli-state"
    # _invoke chdirs into `project`, so the active state dir == project/.fakoli-state.
    result = _invoke(
        project,
        [
            "replay",
            "--from-events", str(state_dir / "events.jsonl"),
            "--into", str(state_dir),
        ],
    )
    assert result.exit_code == 1
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "active .fakoli-state" in combined


@pytest.mark.replay
def test_replay_cli_detects_divergence(tmp_path: Path) -> None:
    """A reference DB that does not match the log exits 2 with a diff summary."""
    project = tmp_path / "proj"
    project.mkdir()
    _run_full_lifecycle(project)
    state_dir = project / ".fakoli-state"

    # Build a *different* reference DB: a fresh, empty (init-only) project.
    other = tmp_path / "other"
    other.mkdir()
    assert _invoke(other, ["init", "--name", "Other"]).exit_code == 0
    other_db = other / ".fakoli-state" / "state.db"

    scratch = tmp_path / "scratch"
    result = _invoke(
        tmp_path,
        [
            "replay",
            "--from-events", str(state_dir / "events.jsonl"),
            "--into", str(scratch),
            "--against", str(other_db),
        ],
    )
    assert result.exit_code == 2
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "FAILED" in combined
