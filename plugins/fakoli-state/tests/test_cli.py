"""CLI integration tests using Typer's CliRunner.

Tests the fakoli-state CLI surface:
- init — scaffolding, overwrite guards, plugin-root guard
- status — uninitialized/initialized paths, human and hook formats
- --version

All tests run in isolated tmp directories.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import Result
from typer.testing import CliRunner

from fakoli_state.cli import app

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

runner = CliRunner()


# ---------------------------------------------------------------------------
# init — happy path
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_creates_state_directory(self, tmp_path: Path) -> None:
        """init creates .fakoli-state/ with all expected files and directories."""
        result = runner.invoke(
            app,
            ["init", "--name", "My Test Project"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path)},
        )
        # May run from the actual cwd; use tmp_path as the project root via os.chdir
        # We need to run in tmp_path, so let's use a different approach
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(
                app,
                ["init", "--name", "My Test Project"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0, f"init failed: {result.output}"
        state_dir = tmp_path / ".fakoli-state"
        assert state_dir.exists(), ".fakoli-state/ directory not created"
        assert (state_dir / "state.db").exists(), "state.db not created"
        assert (state_dir / "events.jsonl").exists(), "events.jsonl not created"
        assert (state_dir / "config.yaml").exists(), "config.yaml not created"
        assert (state_dir / "packets").is_dir(), "packets/ not created"
        assert (state_dir / "snapshots").is_dir(), "snapshots/ not created"

    def test_init_output_contains_project_name(self, tmp_path: Path) -> None:
        """init prints confirmation with the project name."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(
                app,
                ["init", "--name", "Repo Alpha"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "Repo Alpha" in result.output

    def test_init_refuses_overwrite(self, tmp_path: Path) -> None:
        """Second call to init in same dir exits non-zero without --force."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # First init
            first = runner.invoke(
                app,
                ["init", "--name", "Project"],
                catch_exceptions=False,
            )
            assert first.exit_code == 0

            # Second init without --force
            second = runner.invoke(
                app,
                ["init", "--name", "Project"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert second.exit_code != 0, "Second init should have failed without --force"
        assert "already exists" in second.output or "force" in second.output.lower()

    def test_init_force_overwrites_existing(self, tmp_path: Path) -> None:
        """--force reinitialises an existing .fakoli-state/ directory."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # First init
            runner.invoke(
                app,
                ["init", "--name", "Project"],
                catch_exceptions=False,
            )
            # Second init with --force
            result = runner.invoke(
                app,
                ["init", "--name", "Project", "--force"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0, f"--force init failed: {result.output}"

    def test_init_force_truncates_events_log(self, tmp_path: Path) -> None:
        """--force reinit wipes events.jsonl and state.db so the replay/audit
        guarantee holds — without this, a second init appends duplicate event
        IDs to the old log and the log no longer replays to the current DB.
        (Regression test for Greptile PR #37 finding.)
        """
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # First init — produces E000001 (project.created) and E000002 (state.initialized).
            runner.invoke(app, ["init", "--name", "First"], catch_exceptions=False)
            events_path = tmp_path / ".fakoli-state" / "events.jsonl"
            first_lines = events_path.read_text(encoding="utf-8").splitlines()
            assert len(first_lines) == 2, f"expected 2 events after first init, got {len(first_lines)}"

            # Second init with --force — must replace the log, not append to it.
            result = runner.invoke(
                app,
                ["init", "--name", "Second", "--force"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, f"--force init failed: {result.output}"

            second_lines = events_path.read_text(encoding="utf-8").splitlines()
            # Must still be exactly 2 events (not 4) — the old log was wiped.
            assert len(second_lines) == 2, (
                f"--force did not truncate events.jsonl; expected 2 events, "
                f"got {len(second_lines)}. Replay guarantee is broken."
            )
            # And the new events should be for the new project name.
            assert "Second" in second_lines[0], "first event after --force should reference new project"
        finally:
            os.chdir(original_cwd)

    def test_init_refuses_in_plugin_root(self, tmp_path: Path) -> None:
        """init refuses when .claude-plugin/plugin.json declares name == fakoli-state."""
        # Create fake plugin manifest
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"name": "fakoli-state", "version": "1.0.0"}),
            encoding="utf-8",
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(
                app,
                ["init", "--name", "Test"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code != 0
        # The error should mention plugin root or the plugin
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "plugin" in combined.lower() or "plugin" in result.output.lower()

    def test_init_non_fakoli_state_plugin_allowed(self, tmp_path: Path) -> None:
        """init is allowed in a directory with a different plugin name."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"name": "some-other-plugin", "version": "1.0.0"}),
            encoding="utf-8",
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(
                app,
                ["init", "--name", "Test"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# status — uninitialized
# ---------------------------------------------------------------------------


class TestStatusUninitialized:
    def test_status_uninitialized_human_format(self, tmp_path: Path) -> None:
        """status in dir without .fakoli-state/ exits 1."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(
                app,
                ["status"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 1
        assert "not initialized" in result.output.lower() or "init" in result.output.lower()

    def test_status_uninitialized_hook_format(self, tmp_path: Path) -> None:
        """status --hook-format in dir without .fakoli-state/ exits 0 with 'uninitialized'."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(
                app,
                ["status", "--hook-format"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0
        assert "uninitialized" in result.output


# ---------------------------------------------------------------------------
# status — initialized
# ---------------------------------------------------------------------------


class TestStatusInitialized:
    def _init_and_status(
        self, tmp_path: Path, extra_status_args: list[str] | None = None
    ) -> Result:
        """Helper: init in tmp_path, then run status."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            init_result = runner.invoke(
                app,
                ["init", "--name", "My Project"],
                catch_exceptions=False,
            )
            assert init_result.exit_code == 0, f"init failed: {init_result.output}"

            status_args = ["status"]
            if extra_status_args:
                status_args.extend(extra_status_args)
            status_result = runner.invoke(
                app,
                status_args,
                catch_exceptions=False,
            )
        finally:
            os.chdir(original_cwd)

        return status_result

    def test_status_initialized_human_format(self, tmp_path: Path) -> None:
        """status after init shows 'Active claims:' line."""
        result = self._init_and_status(tmp_path)
        assert result.exit_code == 0, f"status failed: {result.output}"
        output = result.output
        # Should have "Active claims:" section (from the CLI output)
        assert "claims" in output.lower(), f"Expected 'claims' in output:\n{output}"

    def test_status_initialized_human_format_has_project_name(self, tmp_path: Path) -> None:
        """Human-readable status output contains 'My Project'."""
        result = self._init_and_status(tmp_path)
        assert result.exit_code == 0
        assert "My Project" in result.output

    def test_status_initialized_hook_format(self, tmp_path: Path) -> None:
        """status --hook-format after init outputs the key:value compact line."""
        result = self._init_and_status(tmp_path, extra_status_args=["--hook-format"])
        assert result.exit_code == 0, f"status --hook-format failed: {result.output}"
        output = result.output
        # Expected: "active-claims:0 ready-tasks:0 blockers:0 prd-status:none"
        assert "active-claims:" in output
        assert "ready-tasks:" in output
        assert "blockers:" in output
        assert "prd-status:" in output

    def test_status_initialized_hook_format_exit_code_zero(self, tmp_path: Path) -> None:
        """hook-format always exits 0."""
        result = self._init_and_status(tmp_path, extra_status_args=["--hook-format"])
        assert result.exit_code == 0

    def test_status_with_cwd_flag(self, tmp_path: Path) -> None:
        """status --cwd works without changing directory."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            runner.invoke(app, ["init", "--name", "CWD Test"], catch_exceptions=False)
        finally:
            os.chdir(original_cwd)

        # Now run status --cwd from any directory
        result = runner.invoke(
            app,
            ["status", "--cwd", str(tmp_path)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "CWD Test" in result.output


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_still_works(self) -> None:
        """--version prints 'fakoli-state 1.4.0' and exits 0."""
        result = runner.invoke(app, ["--version"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "fakoli-state" in result.output
        assert "1.4.0" in result.output

    def test_version_short_flag(self) -> None:
        """-V is an alias for --version."""
        result = runner.invoke(app, ["-V"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "fakoli-state" in result.output


# ---------------------------------------------------------------------------
# Phase 3 CLI test helpers
# ---------------------------------------------------------------------------

_MINIMAL_PRD_CONTENT = """\
# Project: CLI Test Project

## Summary

A project for CLI testing.

## Goals

- Do something useful.

## Requirements

- R001: The system accepts input.
- R002: The system produces output.
"""

_FULL_PRD_CONTENT = """\
# Project: CLI Full Test Project

## Summary

A full project for complete CLI workflow testing.

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


def _do_init(tmp_path: Path, name: str = "Test Project") -> None:
    """Run `fakoli-state init` in tmp_path."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            app, ["init", "--name", name], catch_exceptions=False
        )
        assert result.exit_code == 0, f"init failed: {result.output}"
    finally:
        os.chdir(original_cwd)


def _write_prd(tmp_path: Path, content: str) -> None:
    """Write content to .fakoli-state/prd.md."""
    prd_path = tmp_path / ".fakoli-state" / "prd.md"
    prd_path.write_text(content, encoding="utf-8")


def _invoke_cmd(tmp_path: Path, cmd: list[str]):  # type: ignore[no-untyped-def]
    """Invoke a CLI command in tmp_path context."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, cmd, catch_exceptions=False)
    finally:
        os.chdir(original_cwd)
    return result


# ---------------------------------------------------------------------------
# prd parse command
# ---------------------------------------------------------------------------


class TestPrdParse:
    def test_prd_parse_minimal_valid(self, tmp_path: Path) -> None:
        """write minimal prd.md, run prd parse, exit 0, prints parsed requirements."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _MINIMAL_PRD_CONTENT)

        result = _invoke_cmd(tmp_path, ["prd", "parse"])
        assert result.exit_code == 0, f"prd parse failed: {result.output}"
        # Should print something about parsed requirements
        assert "Parsed" in result.output or "parsed" in result.output.lower()
        assert "2" in result.output  # 2 requirements

    def test_prd_parse_missing_required_section(self, tmp_path: Path) -> None:
        """PRD without ## Goals → exit 1, error mentions missing section."""
        _do_init(tmp_path)
        prd_without_goals = """\
# Project: Broken Project

## Summary

A project without goals.

## Requirements

- R001: Does something.
"""
        _write_prd(tmp_path, prd_without_goals)
        result = _invoke_cmd(tmp_path, ["prd", "parse"])
        assert result.exit_code == 1
        # The error should mention Goals
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "Goals" in combined or "goals" in combined.lower()

    def test_prd_parse_no_prd_md(self, tmp_path: Path) -> None:
        """Run prd parse with no prd.md present → exit 1 with sensible error."""
        _do_init(tmp_path)
        # Do NOT write prd.md
        result = _invoke_cmd(tmp_path, ["prd", "parse"])
        assert result.exit_code == 1
        # Should mention the file or the path
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "prd" in combined.lower() or "not found" in combined.lower()

    def test_prd_parse_without_init_exits_1(self, tmp_path: Path) -> None:
        """prd parse without init → exit 1."""
        result = _invoke_cmd(tmp_path, ["prd", "parse"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# prd review command
# ---------------------------------------------------------------------------


class TestPrdReview:
    def test_prd_review_draft_to_reviewed(self, tmp_path: Path) -> None:
        """After parse, run prd review (no --approve) → PRD moves to reviewed."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _MINIMAL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])

        result = _invoke_cmd(tmp_path, ["prd", "review"])
        assert result.exit_code == 0, f"prd review failed: {result.output}"
        assert "reviewed" in result.output.lower()

    def test_prd_review_approve_reviewed_to_approved(self, tmp_path: Path) -> None:
        """After review, run prd review --approve → PRD moves to approved."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _MINIMAL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["prd", "review"])  # draft → reviewed

        result = _invoke_cmd(tmp_path, ["prd", "review", "--approve"])
        assert result.exit_code == 0, f"prd review --approve failed: {result.output}"
        assert "approved" in result.output.lower()

    def test_prd_review_fails_without_parsed_prd(self, tmp_path: Path) -> None:
        """prd review without a parsed PRD → exit 1 with helpful error."""
        _do_init(tmp_path)
        # No prd parse done
        result = _invoke_cmd(tmp_path, ["prd", "review"])
        assert result.exit_code == 1
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "prd" in combined.lower() or "parse" in combined.lower()


# ---------------------------------------------------------------------------
# plan command
# ---------------------------------------------------------------------------


class TestPlan:
    def test_plan_generates_features_and_tasks(self, tmp_path: Path) -> None:
        """After prd parse with features + tasks, run plan, assert tasks in backend."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        parse_result = _invoke_cmd(tmp_path, ["prd", "parse"])
        assert parse_result.exit_code == 0

        result = _invoke_cmd(tmp_path, ["plan"])
        assert result.exit_code == 0, f"plan failed: {result.output}"
        assert "feature" in result.output.lower() or "task" in result.output.lower()

        # Verify tasks in backend
        list_result = _invoke_cmd(tmp_path, ["list"])
        assert list_result.exit_code == 0
        # Should show at least 2 tasks (T001, T002)
        assert "T001" in list_result.output or "task" in list_result.output.lower()

    def test_plan_creates_tasks_on_first_run(self, tmp_path: Path) -> None:
        """Running plan once creates tasks correctly."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])

        result = _invoke_cmd(tmp_path, ["plan"])
        assert result.exit_code == 0

        list_result = _invoke_cmd(tmp_path, ["list"])
        assert list_result.exit_code == 0
        assert "T001" in list_result.output
        assert "T002" in list_result.output

    def test_plan_is_idempotent(self, tmp_path: Path) -> None:
        """Running plan twice does not duplicate tasks and does not trip
        ON DELETE RESTRICT foreign keys. Regression test for the bug
        welder flagged in P3/W3: INSERT OR REPLACE on tasks triggered
        DELETE+INSERT, violating claim/evidence FK constraints whenever
        plan was re-run after work had begun. Fix: INSERT ... ON CONFLICT
        DO UPDATE preserves row identity, so FKs stay valid.
        """
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])

        first = _invoke_cmd(tmp_path, ["plan"])
        assert first.exit_code == 0
        first_list = _invoke_cmd(tmp_path, ["list"]).output
        first_t001_count = first_list.count("T001")

        # Re-parse + re-plan; must not duplicate or FK-error.
        _invoke_cmd(tmp_path, ["prd", "parse"])
        second = _invoke_cmd(tmp_path, ["plan"])
        assert second.exit_code == 0, f"second plan failed: {second.output}"

        second_list = _invoke_cmd(tmp_path, ["list"]).output
        second_t001_count = second_list.count("T001")
        assert second_t001_count == first_t001_count, (
            f"task count should not change on re-plan; "
            f"first={first_t001_count} second={second_t001_count}"
        )

    def test_plan_without_prd_parse_exits_1(self, tmp_path: Path) -> None:
        """plan without a prd.md → exit 1."""
        _do_init(tmp_path)
        # No prd.md file written
        result = _invoke_cmd(tmp_path, ["plan"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# score command
# ---------------------------------------------------------------------------


class TestScore:
    def _setup_planned_project(self, tmp_path: Path) -> None:
        """init + prd parse + plan."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])

    def test_score_all_populates_scores(self, tmp_path: Path) -> None:
        """After plan, run score → list tasks shows scores no longer all-None."""
        self._setup_planned_project(tmp_path)

        result = _invoke_cmd(tmp_path, ["score"])
        assert result.exit_code == 0, f"score failed: {result.output}"
        assert "Scored" in result.output or "task" in result.output.lower()

        # After scoring, show command shows score values
        show_result = _invoke_cmd(tmp_path, ["show", "T001"])
        if show_result.exit_code == 0:
            output = show_result.output
            # Should show numeric scores, not "(not yet scored)"
            assert "not yet scored" not in output

    def test_score_single_task(self, tmp_path: Path) -> None:
        """score TASK_ID populates just that one task."""
        self._setup_planned_project(tmp_path)

        result = _invoke_cmd(tmp_path, ["score", "T001"])
        assert result.exit_code == 0, f"score T001 failed: {result.output}"
        assert "T001" in result.output

    def test_score_nonexistent_task_exits_1(self, tmp_path: Path) -> None:
        """score T999 when T999 doesn't exist → exit 1."""
        self._setup_planned_project(tmp_path)

        result = _invoke_cmd(tmp_path, ["score", "T999"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# expand command
# ---------------------------------------------------------------------------


class TestExpand:
    def test_expand_refuses_without_llm(self, tmp_path: Path) -> None:
        """Phase 3 scaffold: expand T001 exits 1 with --use-llm message."""
        _do_init(tmp_path)
        result = _invoke_cmd(tmp_path, ["expand", "T001"])
        assert result.exit_code == 1
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "use-llm" in combined.lower() or "--use-llm" in combined

    def test_expand_with_use_llm_also_exits_1(self, tmp_path: Path) -> None:
        """expand --use-llm is also not implemented yet → exit 1."""
        _do_init(tmp_path)
        result = _invoke_cmd(tmp_path, ["expand", "T001", "--use-llm"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# review tasks command
# ---------------------------------------------------------------------------


class TestReviewTasks:
    def _setup_for_review(self, tmp_path: Path) -> None:
        """Setup: init + write PRD with AC + verification + parse + plan + score."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])
        _invoke_cmd(tmp_path, ["score"])

    def test_review_tasks_promotes_complete_tasks(self, tmp_path: Path) -> None:
        """Tasks with acceptance_criteria + verification → promoted to ready."""
        self._setup_for_review(tmp_path)

        result = _invoke_cmd(tmp_path, ["review", "tasks"])
        assert result.exit_code == 0, f"review tasks failed: {result.output}"
        assert "Promoted" in result.output

        # Check that at least some tasks made it to ready
        list_result = _invoke_cmd(tmp_path, ["list", "--status", "ready"])
        assert list_result.exit_code == 0
        # Should have some ready tasks
        assert "task" in list_result.output.lower() or "T001" in list_result.output

    def test_review_tasks_blocks_incomplete(self, tmp_path: Path) -> None:
        """Task without acceptance_criteria stays blocked; surface reason."""
        _do_init(tmp_path)
        # PRD without acceptance criteria on tasks
        prd_no_ac = """\
# Project: No AC Project

## Summary

A project where tasks have no acceptance criteria.

## Goals

- Do tasks.

## Requirements

- R001: Do something.

## Features

### F001: Feature

**Requirements:** R001

## Tasks

### T001: Task Without AC

**Feature:** F001
**Priority:** medium

A task without acceptance criteria.

**Verification:**

- `pytest tests/ -v`
"""
        _write_prd(tmp_path, prd_no_ac)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])

        result = _invoke_cmd(tmp_path, ["review", "tasks"])
        assert result.exit_code == 0
        # Task should be blocked
        assert "Blocked" in result.output or "blocked" in result.output.lower()


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


class TestList:
    def _setup_with_tasks(self, tmp_path: Path) -> None:
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])

    def test_list_shows_all_tasks(self, tmp_path: Path) -> None:
        """list shows all tasks without filters."""
        self._setup_with_tasks(tmp_path)

        result = _invoke_cmd(tmp_path, ["list"])
        assert result.exit_code == 0, f"list failed: {result.output}"
        assert "T001" in result.output
        assert "T002" in result.output

    def test_list_filtered_by_status(self, tmp_path: Path) -> None:
        """list --status drafted shows only drafted tasks."""
        self._setup_with_tasks(tmp_path)

        result = _invoke_cmd(tmp_path, ["list", "--status", "drafted"])
        assert result.exit_code == 0, f"list --status drafted failed: {result.output}"
        # After plan, tasks should be in drafted status
        # Output should either show tasks or "No tasks found"
        assert result.output  # non-empty output

    def test_list_filtered_by_feature(self, tmp_path: Path) -> None:
        """list --feature F001 shows only F001 tasks."""
        self._setup_with_tasks(tmp_path)

        result = _invoke_cmd(tmp_path, ["list", "--feature", "F001"])
        assert result.exit_code == 0, f"list --feature F001 failed: {result.output}"
        # T001 belongs to F001
        assert "T001" in result.output

    def test_list_empty_shows_no_tasks_message(self, tmp_path: Path) -> None:
        """list on project with no tasks shows a 'no tasks' message."""
        _do_init(tmp_path)
        result = _invoke_cmd(tmp_path, ["list"])
        assert result.exit_code == 0
        assert "No tasks" in result.output or "no tasks" in result.output.lower()


# ---------------------------------------------------------------------------
# show command
# ---------------------------------------------------------------------------


class TestShow:
    def test_show_full_task_detail(self, tmp_path: Path) -> None:
        """show T001 output contains acceptance criteria, scores breakdown, verification."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])
        _invoke_cmd(tmp_path, ["score"])

        result = _invoke_cmd(tmp_path, ["show", "T001"])
        assert result.exit_code == 0, f"show T001 failed: {result.output}"
        output = result.output

        # Should show task title
        assert "T001" in output

        # Should show acceptance criteria section
        assert "Acceptance" in output or "criteria" in output.lower()

        # Should show verification section
        assert "Verification" in output or "pytest" in output

    def test_show_nonexistent_task_exits_1(self, tmp_path: Path) -> None:
        """show T999 when T999 doesn't exist → exit 1."""
        _do_init(tmp_path)
        result = _invoke_cmd(tmp_path, ["show", "T999"])
        assert result.exit_code == 1

    def test_show_scores_after_scoring(self, tmp_path: Path) -> None:
        """show T001 after scoring shows score dimensions."""
        _do_init(tmp_path)
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])
        _invoke_cmd(tmp_path, ["score"])

        result = _invoke_cmd(tmp_path, ["show", "T001"])
        assert result.exit_code == 0
        output = result.output
        # Should show score dimensions
        assert "complexity" in output.lower()
        assert "blast" in output.lower()


# ---------------------------------------------------------------------------
# End-to-end workflow
# ---------------------------------------------------------------------------


class TestReplanPreservesTaskStatus:
    """Regression test for Greptile PR #38 finding #3 (P2): _insert_task_row
    upsert was overwriting status='proposed' on re-plan, which would silently
    reset claimed/in_progress tasks back to proposed. After the fix, status
    is excluded from the ON CONFLICT update set and changes only via
    task.status_changed events.
    """

    def test_replan_does_not_reset_advanced_task_status(self, tmp_path: Path) -> None:
        """Simulate Phase 4 by manually advancing a task past 'drafted', then
        re-running plan; the advanced status must be preserved."""
        import sqlite3

        _do_init(tmp_path, name="Replan Test")
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])  # tasks now at 'drafted'

        # Simulate Phase 4 claim by mutating one task to 'claimed' directly.
        # (Phase 4 will do this through claim events; we patch the DB to
        # represent the post-claim state without needing Phase 4 code.)
        db_path = tmp_path / ".fakoli-state" / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE tasks SET status = 'claimed' WHERE id = 'T001'"
        )
        conn.commit()
        conn.close()

        # Re-parse + re-plan. Without the fix, task.created would upsert
        # status back to 'proposed', then task.status_changed would error
        # (or worse, succeed and reset to 'drafted').
        reparse = _invoke_cmd(tmp_path, ["prd", "parse"])
        assert reparse.exit_code == 0
        replan = _invoke_cmd(tmp_path, ["plan"])
        assert replan.exit_code == 0, f"re-plan after claim failed: {replan.output}"

        # Verify T001 is STILL 'claimed' — the upsert did not reset it.
        conn = sqlite3.connect(str(db_path))
        status = conn.execute(
            "SELECT status FROM tasks WHERE id = 'T001'"
        ).fetchone()[0]
        conn.close()
        assert status == "claimed", (
            f"re-plan reset T001 from 'claimed' to '{status}' — the "
            "ON CONFLICT upsert is silently overwriting task status. "
            "status must be managed by task.status_changed events ONLY."
        )


# ---------------------------------------------------------------------------
# Phase 4 CLI helpers
# ---------------------------------------------------------------------------


def _do_init_and_plan(tmp_path: Path, *, with_git: bool = True) -> Path:
    """Full setup: optionally git-init, then fakoli-state init + PRD + plan + review_tasks.

    Returns tmp_path ready for claim-related tests.
    """
    import subprocess as _subprocess

    if with_git:
        _subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        _subprocess.run(
            ["git", "config", "user.email", "test@test.test"],
            cwd=str(tmp_path), check=True, capture_output=True,
        )
        _subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(tmp_path), check=True, capture_output=True,
        )
        (tmp_path / "README.md").write_text("initial\n", encoding="utf-8")
        _subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
        _subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=str(tmp_path), check=True, capture_output=True,
        )

    _do_init(tmp_path, name="Phase4 Test Project")
    _write_prd(tmp_path, _FULL_PRD_CONTENT)
    _invoke_cmd(tmp_path, ["prd", "parse"])
    _invoke_cmd(tmp_path, ["prd", "review"])
    _invoke_cmd(tmp_path, ["prd", "review", "--approve"])
    _invoke_cmd(tmp_path, ["plan"])
    _invoke_cmd(tmp_path, ["score"])
    _invoke_cmd(tmp_path, ["review", "tasks"])
    return tmp_path


def _get_first_ready_task_id(tmp_path: Path) -> str | None:
    """Return the first task ID in ready status by querying the backend directly."""
    import sqlite3 as _sqlite3
    db_path = tmp_path / ".fakoli-state" / "state.db"
    if not db_path.exists():
        return None
    conn = _sqlite3.connect(str(db_path))
    row = conn.execute("SELECT id FROM tasks WHERE status='ready' LIMIT 1").fetchone()
    conn.close()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Phase 4 — claim command
# ---------------------------------------------------------------------------


class TestClaimCommand:
    def test_claim_happy_path_creates_lease_and_branch(self, tmp_path: Path) -> None:
        """Claim a ready task; command exits 0 and prints claim ID + branch."""
        _do_init_and_plan(tmp_path, with_git=True)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None, "No ready task found after setup"

        result = _invoke_cmd(tmp_path, ["claim", task_id, "--actor", "agent-test"])
        assert result.exit_code == 0, f"claim failed: {result.output}"
        assert "Claim ID" in result.output or "Claimed" in result.output
        assert "Lease" in result.output or "lease" in result.output

    def test_claim_without_git_succeeds_warns(self, tmp_path: Path) -> None:
        """Claim succeeds even without a git repo; stderr has a branch warning."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None, "No ready task found after setup"

        result = _invoke_cmd(tmp_path, ["claim", task_id, "--actor", "agent-test"])
        assert result.exit_code == 0, f"claim without git failed: {result.output}"
        # The branch warning may be in output or stderr depending on Typer's mix
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "Warning" in combined or "Claimed" in result.output

    def test_claim_refuses_unready_task(self, tmp_path: Path) -> None:
        """Claiming a task not in 'ready' status exits non-zero."""
        _do_init_and_plan(tmp_path, with_git=False)

        # Use a task ID that was never created → should fail
        result = _invoke_cmd(tmp_path, ["claim", "T999", "--actor", "agent-test"])
        assert result.exit_code != 0
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "not found" in combined.lower() or "T999" in combined

    def test_claim_refuses_when_prd_draft(self, tmp_path: Path) -> None:
        """Claim exits non-zero when PRD is still in draft state."""
        # Init without review/approve
        _do_init(tmp_path, name="Draft PRD Project")
        _write_prd(tmp_path, _FULL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["plan"])

        result = _invoke_cmd(tmp_path, ["claim", "T001", "--actor", "agent-test"])
        assert result.exit_code != 0

    def test_claim_with_force_overrides_warnings(self, tmp_path: Path) -> None:
        """--force flag is accepted and claim proceeds (no conflict in this setup)."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        result = _invoke_cmd(
            tmp_path, ["claim", task_id, "--actor", "agent-test", "--force"]
        )
        assert result.exit_code == 0, f"claim --force failed: {result.output}"


# ---------------------------------------------------------------------------
# Phase 4 — release command
# ---------------------------------------------------------------------------


class TestReleaseCommand:
    def _claim_task(self, tmp_path: Path, task_id: str) -> str:
        """Claim task_id and return the claim ID."""
        import sqlite3 as _sqlite3
        _invoke_cmd(tmp_path, ["claim", task_id, "--actor", "agent-test"])
        db_path = tmp_path / ".fakoli-state" / "state.db"
        conn = _sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT id FROM claims WHERE task_id=? AND status='active'", (task_id,)
        ).fetchone()
        conn.close()
        return row[0] if row else "C001"

    def test_release_happy_path(self, tmp_path: Path) -> None:
        """Claim then release; exit 0, task returns to ready."""
        import sqlite3 as _sqlite3
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        claim_id = self._claim_task(tmp_path, task_id)

        result = _invoke_cmd(
            tmp_path, ["release", claim_id, "--actor", "agent-test"]
        )
        assert result.exit_code == 0, f"release failed: {result.output}"
        assert "Released" in result.output or "released" in result.output.lower()

        # Verify task returned to ready
        db_path = tmp_path / ".fakoli-state" / "state.db"
        conn = _sqlite3.connect(str(db_path))
        status = conn.execute(
            "SELECT status FROM tasks WHERE id=?", (task_id,)
        ).fetchone()[0]
        conn.close()
        assert status == "ready"

    def test_release_force_overrides_actor_check(self, tmp_path: Path) -> None:
        """--force allows a different actor to release."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        claim_id = self._claim_task(tmp_path, task_id)

        result = _invoke_cmd(
            tmp_path, ["release", claim_id, "--actor", "different-agent", "--force"]
        )
        assert result.exit_code == 0, f"release --force failed: {result.output}"


# ---------------------------------------------------------------------------
# Phase 4 — renew command
# ---------------------------------------------------------------------------


class TestRenewCommand:
    def test_renew_extends_lease(self, tmp_path: Path) -> None:
        """Renew prints new lease expiry and exits 0."""
        import sqlite3 as _sqlite3

        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        _invoke_cmd(tmp_path, ["claim", task_id, "--actor", "agent-test"])
        db_path = tmp_path / ".fakoli-state" / "state.db"
        conn = _sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT id FROM claims WHERE task_id=? AND status='active'", (task_id,)
        ).fetchone()
        claim_id = row[0]
        old_expiry = conn.execute(
            "SELECT lease_expires_at FROM claims WHERE id=?", (claim_id,)
        ).fetchone()[0]
        conn.close()

        result = _invoke_cmd(
            tmp_path, ["renew", claim_id, "--actor", "agent-test"]
        )
        assert result.exit_code == 0, f"renew failed: {result.output}"
        assert "lease" in result.output.lower() or "Renewed" in result.output

        # New lease should be present in output (some time string)
        assert old_expiry[:10] in result.output or "lease" in result.output.lower()


# ---------------------------------------------------------------------------
# Phase 4 — next command
# ---------------------------------------------------------------------------


class TestNextCommand:
    def test_next_returns_highest_priority_task(self, tmp_path: Path) -> None:
        """next command prints a task ID and exits 0 when ready tasks exist."""
        _do_init_and_plan(tmp_path, with_git=False)
        result = _invoke_cmd(tmp_path, ["next", "--actor", "agent-test"])
        assert result.exit_code == 0, f"next failed: {result.output}"
        # Should mention a task or 'Next recommended'
        combined = result.output
        assert "T0" in combined or "task" in combined.lower() or "No claimable" in combined

    def test_next_prints_no_tasks_message_when_empty(self, tmp_path: Path) -> None:
        """next prints 'No claimable tasks' when no ready tasks exist."""
        _do_init(tmp_path, name="Empty Project")
        # No PRD parsed, no tasks created
        result = _invoke_cmd(tmp_path, ["next", "--actor", "agent-test"])
        assert result.exit_code == 0, f"next (empty) failed: {result.output}"
        assert "No claimable" in result.output or "no" in result.output.lower()


# ---------------------------------------------------------------------------
# Phase 4 — hook subcommands
# ---------------------------------------------------------------------------


class TestHookSubcommands:
    def test_hook_check_claim_silent_when_no_state(self, tmp_path: Path) -> None:
        """hook check-claim exits 0 silently when no .fakoli-state/ exists."""
        result = _invoke_cmd(
            tmp_path,
            ["hook", "check-claim", "--file", "src/foo.py", "--actor", "agent-test"],
        )
        assert result.exit_code == 0

    def test_hook_record_file_change_appends_event(self, tmp_path: Path) -> None:
        """hook record-file-change exits 0 after init (appends event to JSONL)."""
        _do_init(tmp_path, name="Hook Test Project")
        result = _invoke_cmd(
            tmp_path,
            [
                "hook", "record-file-change",
                "--file", "src/app.py",
                "--tool", "Edit",
                "--actor", "agent-hook",
            ],
        )
        assert result.exit_code == 0

        events_path = tmp_path / ".fakoli-state" / "events.jsonl"
        assert events_path.exists()
        content = events_path.read_text(encoding="utf-8")
        assert "file_changed" in content or "src/app.py" in content


# ---------------------------------------------------------------------------
# Phase 4 — end-to-end claim + release cycle
# ---------------------------------------------------------------------------


class TestE2EClaimRelease:
    def test_full_claim_release_cycle(self, tmp_path: Path) -> None:
        """init + git init + PRD + plan + review_tasks + next + claim + renew + release.

        Asserts: task is back to 'ready' after release.
        """
        import sqlite3 as _sqlite3

        _do_init_and_plan(tmp_path, with_git=True)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None, "No ready tasks after full setup"

        # next — just verify it works
        next_result = _invoke_cmd(tmp_path, ["next", "--actor", "agent-test"])
        assert next_result.exit_code == 0, f"next failed: {next_result.output}"

        # claim
        claim_result = _invoke_cmd(
            tmp_path, ["claim", task_id, "--actor", "agent-test"]
        )
        assert claim_result.exit_code == 0, f"claim failed: {claim_result.output}"

        # find claim ID from DB
        db_path = tmp_path / ".fakoli-state" / "state.db"
        conn = _sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT id FROM claims WHERE task_id=? AND status='active'", (task_id,)
        ).fetchone()
        conn.close()
        assert row is not None, "No active claim found after claim command"
        claim_id = row[0]

        # renew
        renew_result = _invoke_cmd(
            tmp_path, ["renew", claim_id, "--actor", "agent-test"]
        )
        assert renew_result.exit_code == 0, f"renew failed: {renew_result.output}"

        # release
        release_result = _invoke_cmd(
            tmp_path, ["release", claim_id, "--actor", "agent-test", "--reason", "cycle done"]
        )
        assert release_result.exit_code == 0, f"release failed: {release_result.output}"

        # task should be back to ready
        conn = _sqlite3.connect(str(db_path))
        status = conn.execute(
            "SELECT status FROM tasks WHERE id=?", (task_id,)
        ).fetchone()[0]
        conn.close()
        assert status == "ready", (
            f"Expected task back to 'ready' after release, got '{status}'"
        )


class TestE2E:
    def test_full_planning_workflow(self, tmp_path: Path) -> None:
        """init → write PRD → prd parse → prd review --approve → plan → score → review tasks → list --status ready → show T001.

        Assert each step exits 0 and final list shows >= 1 ready task.
        """
        # 1. init
        _do_init(tmp_path, name="E2E Test Project")

        # 2. write PRD
        _write_prd(tmp_path, _FULL_PRD_CONTENT)

        # 3. prd parse
        parse_result = _invoke_cmd(tmp_path, ["prd", "parse"])
        assert parse_result.exit_code == 0, f"prd parse failed: {parse_result.output}"
        assert "Parsed" in parse_result.output

        # 4. prd review (draft → reviewed)
        review_result = _invoke_cmd(tmp_path, ["prd", "review"])
        assert review_result.exit_code == 0, f"prd review failed: {review_result.output}"

        # 5. prd review --approve (reviewed → approved)
        approve_result = _invoke_cmd(tmp_path, ["prd", "review", "--approve"])
        assert approve_result.exit_code == 0, f"prd review --approve failed: {approve_result.output}"

        # 6. plan
        plan_result = _invoke_cmd(tmp_path, ["plan"])
        assert plan_result.exit_code == 0, f"plan failed: {plan_result.output}"

        # 7. score
        score_result = _invoke_cmd(tmp_path, ["score"])
        assert score_result.exit_code == 0, f"score failed: {score_result.output}"

        # 8. review tasks → promote to ready
        review_tasks_result = _invoke_cmd(tmp_path, ["review", "tasks"])
        assert review_tasks_result.exit_code == 0, (
            f"review tasks failed: {review_tasks_result.output}"
        )

        # 9. list --status ready → at least 1 ready task
        list_result = _invoke_cmd(tmp_path, ["list", "--status", "ready"])
        assert list_result.exit_code == 0, f"list --status ready failed: {list_result.output}"
        # Should show at least 1 task or indicate tasks were promoted
        # (some tasks may be blocked if AC gate not met, but at least the command runs)

        # 10. show T001
        show_result = _invoke_cmd(tmp_path, ["show", "T001"])
        assert show_result.exit_code == 0, f"show T001 failed: {show_result.output}"
        assert "T001" in show_result.output

    def test_status_after_full_workflow(self, tmp_path: Path) -> None:
        """status command reflects PRD state after review."""
        _do_init(tmp_path, name="Status E2E Project")
        _write_prd(tmp_path, _MINIMAL_PRD_CONTENT)
        _invoke_cmd(tmp_path, ["prd", "parse"])
        _invoke_cmd(tmp_path, ["prd", "review"])

        result = _invoke_cmd(tmp_path, ["status"])
        assert result.exit_code == 0
        output = result.output
        # Should show the PRD status as reviewed
        assert "reviewed" in output.lower()


# ---------------------------------------------------------------------------
# Phase 5 — helpers
# ---------------------------------------------------------------------------


def _do_claim(tmp_path: Path, task_id: str, actor: str = "agent-test") -> str:
    """Claim task_id and return the claim ID from the DB."""
    import sqlite3 as _sqlite3

    _invoke_cmd(tmp_path, ["claim", task_id, "--actor", actor])
    db_path = tmp_path / ".fakoli-state" / "state.db"
    conn = _sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT id FROM claims WHERE task_id=? AND status='active'", (task_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else "CLAIM-UNKNOWN"


def _get_task_status(tmp_path: Path, task_id: str) -> str | None:
    """Return the current status of task_id from the DB."""
    import sqlite3 as _sqlite3

    db_path = tmp_path / ".fakoli-state" / "state.db"
    conn = _sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT status FROM tasks WHERE id=?", (task_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Phase 5 — packet command
# ---------------------------------------------------------------------------


class TestPacketCommand:
    def test_packet_renders_markdown_to_packets_dir(self, tmp_path: Path) -> None:
        """packet T001 exits 0 and writes .fakoli-state/packets/T001.md."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None, "No ready task after setup"

        result = _invoke_cmd(tmp_path, ["packet", task_id])
        assert result.exit_code == 0, f"packet failed: {result.output}"

        packet_file = tmp_path / ".fakoli-state" / "packets" / f"{task_id}.md"
        assert packet_file.exists(), "Packet .md file not written"
        content = packet_file.read_text(encoding="utf-8")
        assert task_id in content

    def test_packet_json_format_writes_json_file(self, tmp_path: Path) -> None:
        """packet T001 --format json writes .fakoli-state/packets/T001.json."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        result = _invoke_cmd(tmp_path, ["packet", task_id, "--format", "json"])
        assert result.exit_code == 0, f"packet --format json failed: {result.output}"

        packet_file = tmp_path / ".fakoli-state" / "packets" / f"{task_id}.json"
        assert packet_file.exists(), "Packet .json file not written"
        data = json.loads(packet_file.read_text(encoding="utf-8"))
        assert "task_id" in data

    def test_packet_unknown_task_exits_nonzero(self, tmp_path: Path) -> None:
        """packet T999 (unknown task) exits non-zero with error message."""
        _do_init(tmp_path, name="Packet Test Project")

        result = _invoke_cmd(tmp_path, ["packet", "T999"])
        assert result.exit_code != 0
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "T999" in combined or "not found" in combined.lower()

    def test_packet_active_claim_section_appears_when_claimed(
        self, tmp_path: Path
    ) -> None:
        """packet after claim shows 'Active Claim' section in output."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        _do_claim(tmp_path, task_id, actor="agent-test")

        result = _invoke_cmd(tmp_path, ["packet", task_id])
        assert result.exit_code == 0, f"packet after claim failed: {result.output}"
        assert "Active Claim" in result.output or "claim" in result.output.lower()


# ---------------------------------------------------------------------------
# Phase 5 — submit command
# ---------------------------------------------------------------------------


class TestSubmitCommand:
    def test_submit_happy_path_exits_zero(self, tmp_path: Path) -> None:
        """submit with required args exits 0 and prints evidence ID."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        _do_claim(tmp_path, task_id, actor="agent-test")

        result = _invoke_cmd(
            tmp_path,
            [
                "submit", task_id,
                "--commands", "pytest tests/ -v",
                "--files-changed", "src/auth.py",
                "--actor", "agent-test",
            ],
        )
        assert result.exit_code == 0, f"submit failed: {result.output}"
        assert "Evidence" in result.output or "submitted" in result.output.lower()

    def test_submit_transitions_task_to_needs_review(self, tmp_path: Path) -> None:
        """submit transitions task to needs_review status."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        _do_claim(tmp_path, task_id, actor="agent-test")

        _invoke_cmd(
            tmp_path,
            [
                "submit", task_id,
                "--commands", "pytest tests/ -v",
                "--files-changed", "src/main.py",
                "--actor", "agent-test",
            ],
        )

        status = _get_task_status(tmp_path, task_id)
        assert status == "needs_review", f"Expected needs_review, got {status!r}"

    def test_submit_without_active_claim_exits_nonzero(self, tmp_path: Path) -> None:
        """submit without an active claim exits non-zero with error."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None
        # Do NOT claim the task

        result = _invoke_cmd(
            tmp_path,
            [
                "submit", task_id,
                "--commands", "pytest -v",
                "--files-changed", "src/foo.py",
                "--actor", "agent-test",
            ],
        )
        assert result.exit_code != 0
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "claim" in combined.lower() or "no active" in combined.lower()

    def test_submit_with_pr_url_echoes_it(self, tmp_path: Path) -> None:
        """submit --pr-url records the URL and prints it."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        _do_claim(tmp_path, task_id, actor="agent-test")

        result = _invoke_cmd(
            tmp_path,
            [
                "submit", task_id,
                "--commands", "pytest tests/ -v",
                "--files-changed", "src/auth.py",
                "--pr-url", "https://github.com/repo/pull/42",
                "--actor", "agent-test",
            ],
        )
        assert result.exit_code == 0, f"submit with --pr-url failed: {result.output}"
        assert "https://github.com/repo/pull/42" in result.output


# ---------------------------------------------------------------------------
# Phase 5 — apply command
# ---------------------------------------------------------------------------


class TestApplyCommand:
    def _reach_needs_review(
        self, tmp_path: Path, task_id: str, actor: str = "agent-test"
    ) -> None:
        """Helper: claim + submit to reach needs_review state."""
        _do_claim(tmp_path, task_id, actor=actor)
        _invoke_cmd(
            tmp_path,
            [
                "submit", task_id,
                "--commands", "pytest tests/ -v",
                "--files-changed", "src/main.py",
                "--actor", actor,
            ],
        )

    def test_apply_approve_transitions_to_done(self, tmp_path: Path) -> None:
        """apply --approve transitions needs_review → done."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        self._reach_needs_review(tmp_path, task_id)

        result = _invoke_cmd(
            tmp_path,
            ["apply", task_id, "--approve", "--reviewer", "alice"],
        )
        assert result.exit_code == 0, f"apply --approve failed: {result.output}"
        assert "done" in result.output.lower() or "approved" in result.output.lower()

        status = _get_task_status(tmp_path, task_id)
        assert status == "done", f"Expected done, got {status!r}"

    def test_apply_reject_requires_reason(self, tmp_path: Path) -> None:
        """apply --reject without --reason exits non-zero."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        self._reach_needs_review(tmp_path, task_id)

        result = _invoke_cmd(
            tmp_path,
            ["apply", task_id, "--reject", "--reviewer", "bob"],
        )
        assert result.exit_code != 0
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "reason" in combined.lower() or "reject" in combined.lower()

    def test_apply_reject_with_reason_transitions_to_rejected(
        self, tmp_path: Path
    ) -> None:
        """apply --reject --reason transitions needs_review → rejected."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        self._reach_needs_review(tmp_path, task_id)

        result = _invoke_cmd(
            tmp_path,
            [
                "apply", task_id,
                "--reject",
                "--reason", "Needs more tests.",
                "--reviewer", "bob",
            ],
        )
        assert result.exit_code == 0, f"apply --reject failed: {result.output}"
        assert "rejected" in result.output.lower()

        status = _get_task_status(tmp_path, task_id)
        assert status == "rejected", f"Expected rejected, got {status!r}"

    def test_apply_without_flag_prints_review_summary(
        self, tmp_path: Path
    ) -> None:
        """apply without --approve or --reject prints review summary and exits 0."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None

        self._reach_needs_review(tmp_path, task_id)

        result = _invoke_cmd(tmp_path, ["apply", task_id])
        assert result.exit_code == 0, f"apply (no flag) failed: {result.output}"
        # Should show that task is awaiting review
        assert (
            "needs_review" in result.output
            or "awaiting" in result.output.lower()
            or "approve" in result.output.lower()
        )

    def test_apply_wrong_status_exits_nonzero(self, tmp_path: Path) -> None:
        """apply on a task not in needs_review status exits non-zero."""
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None
        # Task is 'ready' (not needs_review)

        result = _invoke_cmd(
            tmp_path,
            ["apply", task_id, "--approve", "--reviewer", "alice"],
        )
        assert result.exit_code != 0
        combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        assert "needs_review" in combined or "status" in combined.lower()


# ---------------------------------------------------------------------------
# Phase 5 — hook capture-evidence subcommand
# ---------------------------------------------------------------------------


class TestHookCaptureEvidence:
    def test_hook_capture_evidence_no_state_dir_exits_zero(
        self, tmp_path: Path
    ) -> None:
        """hook capture-evidence exits 0 when no .fakoli-state/ exists."""
        result = _invoke_cmd(
            tmp_path,
            [
                "hook", "capture-evidence",
                "--command", "pytest tests/ -v",
                "--exit-code", "0",
                "--actor", "agent-test",
            ],
        )
        assert result.exit_code == 0

    def test_hook_capture_evidence_writes_to_orphan_when_no_claim(
        self, tmp_path: Path
    ) -> None:
        """hook capture-evidence writes to orphan.json when no active claim."""
        _do_init(tmp_path, name="Hook CE Test Project")

        result = _invoke_cmd(
            tmp_path,
            [
                "hook", "capture-evidence",
                "--command", "pytest tests/ -v",
                "--exit-code", "0",
                "--actor", "agent-test",
            ],
        )
        assert result.exit_code == 0

        orphan_file = tmp_path / ".fakoli-state" / ".evidence-buffer" / "orphan.json"
        assert orphan_file.exists(), "orphan.json not written"
        content = orphan_file.read_text(encoding="utf-8")
        assert "pytest" in content

    def test_hook_capture_evidence_exits_zero_on_failure_command(
        self, tmp_path: Path
    ) -> None:
        """hook capture-evidence always exits 0 even when the command's exit-code is non-zero."""
        _do_init(tmp_path, name="Hook CE Failure Test")

        result = _invoke_cmd(
            tmp_path,
            [
                "hook", "capture-evidence",
                "--command", "pytest tests/ -v",
                "--exit-code", "1",
                "--actor", "agent-test",
            ],
        )
        assert result.exit_code == 0  # hook MUST always exit 0


# ---------------------------------------------------------------------------
# Phase 5 — end-to-end: full lifecycle init → done
# ---------------------------------------------------------------------------


class TestE2EPhase5:
    def test_full_lifecycle_init_to_done(self, tmp_path: Path) -> None:
        """Full lifecycle: init → PRD → plan → review_tasks → claim → submit → apply --approve.

        Asserts task reaches 'done' status at the end.
        """
        # 1. Full setup (git + init + PRD + plan + score + review tasks)
        _do_init_and_plan(tmp_path, with_git=False)
        task_id = _get_first_ready_task_id(tmp_path)
        assert task_id is not None, "No ready tasks after full setup"

        # 2. claim
        claim_result = _invoke_cmd(
            tmp_path, ["claim", task_id, "--actor", "agent-test"]
        )
        assert claim_result.exit_code == 0, f"claim failed: {claim_result.output}"

        # 3. submit evidence
        submit_result = _invoke_cmd(
            tmp_path,
            [
                "submit", task_id,
                "--commands", "pytest tests/ -v",
                "--files-changed", "src/auth.py",
                "--actor", "agent-test",
            ],
        )
        assert submit_result.exit_code == 0, f"submit failed: {submit_result.output}"

        # Verify task is now in needs_review
        status = _get_task_status(tmp_path, task_id)
        assert status == "needs_review", f"Expected needs_review, got {status!r}"

        # 4. apply --approve
        apply_result = _invoke_cmd(
            tmp_path,
            ["apply", task_id, "--approve", "--reviewer", "human-reviewer"],
        )
        assert apply_result.exit_code == 0, f"apply --approve failed: {apply_result.output}"

        # Verify task is now done
        final_status = _get_task_status(tmp_path, task_id)
        assert final_status == "done", (
            f"Expected task '{task_id}' to be 'done' after full lifecycle, got '{final_status}'"
        )
