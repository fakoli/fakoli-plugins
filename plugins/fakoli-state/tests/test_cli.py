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
        """--version prints 'fakoli-state 1.1.0' and exits 0."""
        result = runner.invoke(app, ["--version"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "fakoli-state" in result.output
        assert "1.1.0" in result.output

    def test_version_short_flag(self) -> None:
        """-V is an alias for --version."""
        result = runner.invoke(app, ["-V"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "fakoli-state" in result.output
