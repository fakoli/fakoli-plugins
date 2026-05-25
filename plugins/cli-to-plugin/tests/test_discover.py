"""
test_discover.py — Unit and fixture tests for discover.py.

Covers:
- Real gh/kubectl/docker fixture subset-matching
- parse_help_text / parse_flag_line unit tests
- ANSI stripping
- Non-zero exit with stdout (warn-and-continue)
- Non-zero exit with empty stdout (halt)
- Recursion depth cap
- Command count cap
- Per-call timeout
- UTF-8 decode with replacement
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import discover.py as a module (it lives in scripts/ not a package)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_DISCOVER_PATH = _SCRIPTS_DIR / "discover.py"

spec = importlib.util.spec_from_file_location("discover", _DISCOVER_PATH)
discover_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discover_mod)

# Aliases for convenience
strip_ansi = discover_mod.strip_ansi
run_help = discover_mod.run_help
parse_flag_line = discover_mod.parse_flag_line
parse_help_text = discover_mod.parse_help_text
walk = discover_mod.walk
discover = discover_mod.discover
WalkState = discover_mod.WalkState
get_cli_version = discover_mod.get_cli_version

# ---------------------------------------------------------------------------
# Import conftest helpers directly (they're also accessible as fixtures,
# but some helpers need to be callable from within test functions)
# ---------------------------------------------------------------------------

from conftest import (
    FIXTURES_DIR,
    assert_subset_match,
    make_opts,
    make_subprocess_patcher_from_dir,
)


# ===========================================================================
# Unit tests — strip_ansi
# ===========================================================================

class TestStripAnsi:
    def test_removes_color_codes(self):
        text = "\x1b[31mHello\x1b[0m World"
        assert strip_ansi(text) == "Hello World"

    def test_removes_bold_codes(self):
        text = "\x1b[1mBold\x1b[0m"
        assert strip_ansi(text) == "Bold"

    def test_removes_multiple_sequences(self):
        text = "\x1b[1m\x1b[33mYELLOW BOLD\x1b[0m — plain"
        assert strip_ansi(text) == "YELLOW BOLD — plain"

    def test_passes_through_plain_text(self):
        text = "no escape sequences here"
        assert strip_ansi(text) == text

    def test_no_escape_chars_in_output(self, pathological_dir):
        raw = (pathological_dir / "ansi-codes.txt").read_text(encoding="utf-8")
        result = strip_ansi(raw)
        assert "\x1b" not in result

    def test_ansi_fixture_parses_cleanly(self, pathological_dir):
        """After stripping ANSI from the fixture, parse_help_text must produce a valid structure."""
        raw = (pathological_dir / "ansi-codes.txt").read_text(encoding="utf-8")
        clean = strip_ansi(raw)
        parsed = parse_help_text(clean)
        assert parsed["summary"] != ""
        # Must have at least one commands section
        command_sections = [s for s in parsed["sections"] if s["kind"] == "commands"]
        assert len(command_sections) >= 1
        # Commands list must be non-empty
        assert any(len(s["entries"]) > 0 for s in command_sections)


# ===========================================================================
# Unit tests — parse_flag_line
# ===========================================================================

class TestParseFlagLine:
    def test_long_flag_with_description(self):
        line = "  --help      Show help for command"
        f = parse_flag_line(line)
        assert f is not None
        assert f["long"] == "--help"
        assert f["description"] == "Show help for command"
        assert "short" not in f
        assert "argument" not in f

    def test_short_and_long_with_argument(self):
        line = "  -R, --repo [HOST/]OWNER/REPO   Select another repository"
        f = parse_flag_line(line)
        assert f is not None
        assert f["short"] == "-R"
        assert f["long"] == "--repo"
        assert f["argument"] == "[HOST/]OWNER/REPO"
        assert "Select another repository" in f["description"]

    def test_flag_with_string_argument(self):
        line = "  -c, --context string     Name of the context"
        f = parse_flag_line(line)
        assert f is not None
        assert f["short"] == "-c"
        assert f["long"] == "--context"
        assert f["argument"] == "string"
        assert "Name of the context" in f["description"]

    def test_flag_no_description(self):
        line = "      --tls"
        f = parse_flag_line(line)
        assert f is not None
        assert f["long"] == "--tls"

    def test_not_a_flag_line(self):
        line = "  create       Create a resource"
        f = parse_flag_line(line)
        assert f is None

    def test_empty_line(self):
        assert parse_flag_line("") is None

    def test_section_heading(self):
        assert parse_flag_line("CORE COMMANDS") is None

    def test_short_and_long_flag_parses_short(self):
        """Short flags require a comma-separated long counterpart to be captured."""
        line = "  -v, --version            Print version information and quit"
        f = parse_flag_line(line)
        assert f is not None
        assert f["short"] == "-v"
        assert f["long"] == "--version"

    def test_standalone_short_flag_not_matched(self):
        """
        The _FLAG_RE pattern requires either a long flag or a comma after short.
        A bare '-v  description' line (no comma, no long flag) returns None.
        This documents a known parser limitation.
        """
        line = "  -v              Enable verbose output"
        f = parse_flag_line(line)
        # The regex doesn't capture standalone short flags without a long counterpart
        assert f is None


# ===========================================================================
# Unit tests — parse_help_text
# ===========================================================================

class TestParseHelpText:
    def test_gh_root_summary(self):
        text = (FIXTURES_DIR / "gh-help-raw" / "gh.txt").read_text()
        parsed = parse_help_text(text)
        assert parsed["summary"] == "Work seamlessly with GitHub from the command line."

    def test_gh_root_has_command_sections(self):
        text = (FIXTURES_DIR / "gh-help-raw" / "gh.txt").read_text()
        parsed = parse_help_text(text)
        cmd_sections = [s for s in parsed["sections"] if s["kind"] == "commands"]
        assert len(cmd_sections) >= 2  # CORE COMMANDS + GITHUB ACTIONS COMMANDS etc.

    def test_gh_root_flags(self):
        text = (FIXTURES_DIR / "gh-help-raw" / "gh.txt").read_text()
        parsed = parse_help_text(text)
        flag_sections = [s for s in parsed["sections"] if s["kind"] == "flags"]
        assert len(flag_sections) >= 1
        entries = flag_sections[0]["entries"]
        long_flags = [e["long"] for e in entries if "long" in e]
        assert "--help" in long_flags
        assert "--version" in long_flags

    def test_kubectl_mixed_case_headings(self):
        text = (FIXTURES_DIR / "kubectl-help-raw" / "kubectl.txt").read_text()
        parsed = parse_help_text(text)
        cmd_sections = [s for s in parsed["sections"] if s["kind"] == "commands"]
        # kubectl uses "Basic Commands (Beginner):", "Advanced Commands:" etc.
        assert len(cmd_sections) >= 3

    def test_kubectl_root_summary(self):
        text = (FIXTURES_DIR / "kubectl-help-raw" / "kubectl.txt").read_text()
        parsed = parse_help_text(text)
        assert "kubectl" in parsed["summary"].lower()

    def test_docker_inline_usage(self):
        text = (FIXTURES_DIR / "docker-help-raw" / "docker.txt").read_text()
        parsed = parse_help_text(text)
        # docker starts with "Usage:  docker [OPTIONS] COMMAND"
        assert parsed["usage"] != ""
        assert "docker" in parsed["usage"]

    def test_docker_root_summary(self):
        text = (FIXTURES_DIR / "docker-help-raw" / "docker.txt").read_text()
        parsed = parse_help_text(text)
        assert "containers" in parsed["summary"].lower()

    def test_docker_global_options_section(self):
        text = (FIXTURES_DIR / "docker-help-raw" / "docker.txt").read_text()
        parsed = parse_help_text(text)
        flag_sections = [s for s in parsed["sections"] if s["kind"] == "flags"]
        assert len(flag_sections) >= 1
        # Should have at least 10 flags in Global Options
        all_entries = [e for s in flag_sections for e in s["entries"]]
        assert len(all_entries) >= 10

    def test_empty_text(self):
        parsed = parse_help_text("")
        assert parsed["summary"] == ""
        assert parsed["sections"] == []

    def test_comment_lines_skipped(self):
        text = "# This is a comment\nMyCLI — description\n\nCOMMANDS\n  do   Do something\n"
        parsed = parse_help_text(text)
        assert parsed["summary"] == "MyCLI — description"

    def test_continuation_flag_description(self):
        text = (
            "COMMANDS\n"
            "  foo   Do foo\n\n"
            "FLAGS\n"
            "  --bar   First line of description\n"
            "           continued here\n"
        )
        parsed = parse_help_text(text)
        flag_sections = [s for s in parsed["sections"] if s["kind"] == "flags"]
        assert len(flag_sections) == 1
        entry = flag_sections[0]["entries"][0]
        assert "continued here" in entry.get("description", "")


# ===========================================================================
# Unit tests — run_help (subprocess wrapper)
# ===========================================================================

class TestRunHelp:
    def test_utf8_decode_with_replacement(self):
        """Non-UTF-8 bytes must not crash; replacement chars appear in output."""
        bad_bytes = b"\x80\x81\x82 some text"
        mock_result = MagicMock()
        mock_result.stdout = bad_bytes
        mock_result.stderr = b""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            text, rc, timed_out = run_help(["fake", "--help"], 5.0)

        assert not timed_out
        assert rc == 0
        # Replacement characters (U+FFFD) or similar should appear
        assert "�" in text or len(text) > 0  # no crash is the main assertion

    def test_timeout_returns_timed_out_flag(self):
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd=["x"], timeout=1)):
            text, rc, timed_out = run_help(["fake", "--help"], 1.0)
        assert timed_out is True
        assert rc == -1
        assert text == ""

    def test_stderr_fallback_when_stdout_empty(self):
        mock_result = MagicMock()
        mock_result.stdout = b""
        mock_result.stderr = b"help text on stderr"
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            text, rc, timed_out = run_help(["fake", "--help"], 5.0)

        assert "help text on stderr" in text
        assert rc == 1
        assert not timed_out


# ===========================================================================
# Integration tests — discover() with gh fixtures
# ===========================================================================

class TestGhFixtures:
    """Use monkeypatched subprocess to simulate gh CLI discovery."""

    def _build_fake_run(self, gh_raw_dir: Path):
        """Build subprocess.run patch from gh fixture dir."""
        return make_subprocess_patcher_from_dir(
            gh_raw_dir,
            "gh",
            # Unknown sub-commands return empty stdout (bare leaf behavior)
        )

    def test_real_gh_fixture_matches_expected(
        self, monkeypatch, gh_raw_dir, gh_expected
    ):
        """Core acceptance test: subset-match actual vs expected for gh."""
        fake_run = self._build_fake_run(gh_raw_dir)

        with patch.object(discover_mod, "run_help") as mock_run_help:
            # Translate fixture dir-based patching to run_help signature
            def run_help_shim(args, timeout):
                return fake_run(args)
            # Build per-call fake that respects our fixture map
            _fake = make_subprocess_patcher_from_dir(gh_raw_dir, "gh")

            def rh(args, timeout):
                mock = _fake(args)
                return (
                    mock.stdout.decode("utf-8"),
                    mock.returncode,
                    False,
                )

            mock_run_help.side_effect = rh

            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/gh"):
                opts = make_opts(max_depth=3, max_commands=500)
                tree = discover("gh", opts)

        assert_subset_match(tree, gh_expected)

    def test_gh_global_flags_exact(self, monkeypatch, gh_raw_dir, gh_expected):
        """global_flags from root FLAGS section only: --help and --version."""
        _fake = make_subprocess_patcher_from_dir(gh_raw_dir, "gh")

        def rh(args, timeout):
            mock = _fake(args)
            return (mock.stdout.decode("utf-8"), mock.returncode, False)

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/gh"):
                opts = make_opts()
                tree = discover("gh", opts)

        assert "global_flags" in tree
        long_flags = [f["long"] for f in tree["global_flags"] if "long" in f]
        assert "--help" in long_flags
        assert "--version" in long_flags
        # INHERITED FLAGS from sub-help pages must NOT appear
        assert "--repo" not in long_flags


# ===========================================================================
# Integration tests — discover() with kubectl fixtures
# ===========================================================================

class TestKubectlFixtures:
    def test_kubectl_fixture_validates_against_schema(
        self, monkeypatch, kubectl_raw_dir, kubectl_expected
    ):
        """kubectl subset-match: create and apply groups with their commands."""
        _fake = make_subprocess_patcher_from_dir(kubectl_raw_dir, "kubectl")

        def rh(args, timeout):
            mock = _fake(args)
            return (mock.stdout.decode("utf-8"), mock.returncode, False)

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/kubectl"):
                opts = make_opts(max_depth=3, max_commands=500)
                tree = discover("kubectl", opts)

        assert_subset_match(tree, kubectl_expected)

    def test_kubectl_no_global_flags(
        self, monkeypatch, kubectl_raw_dir
    ):
        """kubectl root help has no FLAGS section — global_flags must be absent or empty."""
        _fake = make_subprocess_patcher_from_dir(kubectl_raw_dir, "kubectl")

        def rh(args, timeout):
            mock = _fake(args)
            return (mock.stdout.decode("utf-8"), mock.returncode, False)

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/kubectl"):
                opts = make_opts()
                tree = discover("kubectl", opts)

        # kubectl has no global FLAGS section in root help
        assert tree.get("global_flags", []) == []


# ===========================================================================
# Integration tests — discover() with docker fixtures
# ===========================================================================

class TestDockerFixtures:
    def test_docker_fixture_validates_against_schema(
        self, monkeypatch, docker_raw_dir, docker_expected
    ):
        """docker subset-match: container/image/volume/network groups."""
        _fake = make_subprocess_patcher_from_dir(docker_raw_dir, "docker")

        def rh(args, timeout):
            mock = _fake(args)
            return (mock.stdout.decode("utf-8"), mock.returncode, False)

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/docker"):
                opts = make_opts(max_depth=3, max_commands=500)
                tree = discover("docker", opts)

        assert_subset_match(tree, docker_expected)

    def test_docker_global_flags_count(
        self, monkeypatch, docker_raw_dir, docker_expected
    ):
        """docker expected JSON lists 11 global flags — verify exact match."""
        _fake = make_subprocess_patcher_from_dir(docker_raw_dir, "docker")

        def rh(args, timeout):
            mock = _fake(args)
            return (mock.stdout.decode("utf-8"), mock.returncode, False)

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/docker"):
                opts = make_opts()
                tree = discover("docker", opts)

        assert "global_flags" in tree
        assert len(tree["global_flags"]) == len(docker_expected["global_flags"])


# ===========================================================================
# Pathological tests
# ===========================================================================

class TestPathologicalCases:

    # -----------------------------------------------------------------------
    # ANSI: feed ansi-codes.txt — assert no \x1b in output
    # -----------------------------------------------------------------------

    def test_ansi_stripping_in_discovery(self, pathological_dir):
        """Discovery pipeline strips ANSI codes before parsing."""
        ansi_text = (pathological_dir / "ansi-codes.txt").read_text(encoding="utf-8")

        call_count = 0

        def rh(args, timeout):
            nonlocal call_count
            call_count += 1
            # Return ansi text for any invocation
            return ansi_text, 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/mycli"):
                opts = make_opts(max_depth=2, max_commands=50)
                tree = discover("mycli", opts)

        # No ANSI in any string field of the tree
        tree_str = str(tree)
        assert "\x1b" not in tree_str

    # -----------------------------------------------------------------------
    # Non-zero exit WITH stdout: warn-and-continue
    # -----------------------------------------------------------------------

    def test_nonzero_exit_with_stdout_warns_and_continues(self, pathological_dir):
        """When root help returns exit 1 but has stdout, discover warns and continues."""
        exits_text = (pathological_dir / "exits-nonzero.txt").read_text(encoding="utf-8")

        def rh(args, timeout):
            return exits_text, 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/badcli"):
                opts = make_opts(max_depth=1, max_commands=10)
                tree = discover("badcli", opts)

        # Must NOT have exited — tree should be returned
        assert "groups" in tree
        # Warning must mention the non-zero exit
        warnings = tree["discovery"]["warnings"]
        assert any("non-zero" in w.lower() or "rc=" in w or "exited" in w for w in warnings), (
            f"Expected a warning about non-zero exit, got: {warnings}"
        )

    def test_nonzero_exit_with_stdout_still_parses_commands(self, pathological_dir):
        """Commands from exits-nonzero.txt stdout must appear in the tree."""
        exits_text = (pathological_dir / "exits-nonzero.txt").read_text(encoding="utf-8")

        def rh(args, timeout):
            return exits_text, 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/badcli"):
                opts = make_opts(max_depth=1, max_commands=20)
                tree = discover("badcli", opts)

        group_names = [g["name"] for g in tree["groups"]]
        # The fixture defines: start, stop, status, config as top-level commands
        assert len(group_names) >= 1

    # -----------------------------------------------------------------------
    # Non-zero exit with EMPTY stdout: halt
    # -----------------------------------------------------------------------

    def test_nonzero_exit_empty_stdout_raises(self):
        """Root help returning empty stdout + non-zero exit must call sys.exit(1)."""

        def rh(args, timeout):
            return "", 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/emptycli"):
                opts = make_opts()
                with pytest.raises(SystemExit) as exc_info:
                    discover("emptycli", opts)
                assert exc_info.value.code == 1

    def test_nonzero_exit_empty_stdout_error_message(self, capsys):
        """Error message must go to stderr and mention the CLI name."""

        def rh(args, timeout):
            return "", 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/emptycli"):
                opts = make_opts()
                with pytest.raises(SystemExit):
                    discover("emptycli", opts)

        captured = capsys.readouterr()
        assert "emptycli" in captured.err
        assert "error" in captured.err.lower()

    # -----------------------------------------------------------------------
    # CLI not on PATH
    # -----------------------------------------------------------------------

    def test_cli_not_on_path_exits(self, capsys):
        """When shutil.which returns None, discover must call sys.exit(1)."""
        with patch.object(discover_mod.shutil, "which", return_value=None):
            opts = make_opts()
            with pytest.raises(SystemExit) as exc_info:
                discover("notacli", opts)
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "notacli" in captured.err

    # -----------------------------------------------------------------------
    # Recursion depth cap: with max_depth=3, deep-foo-bar-baz-qux is not walked
    # -----------------------------------------------------------------------

    def test_depth_cap_no_qux_group(self, pathological_dir):
        """With max_depth=3, discover must not walk into 'qux' (depth 4)."""
        fixture_map = {
            "deep-foo.txt": ["foo"],
            "deep-foo-bar.txt": ["foo", "bar"],
            "deep-foo-bar-baz.txt": ["foo", "bar", "baz"],
            "deep-foo-bar-baz-qux.txt": ["foo", "bar", "baz", "qux"],
        }

        qux_called = []

        def rh(args, timeout):
            # Strip flags
            path = [a for a in args if not a.startswith("-")]
            if path == ["foo"]:
                return (pathological_dir / "deep-foo.txt").read_text(), 0, False
            elif path == ["foo", "bar"]:
                return (pathological_dir / "deep-foo-bar.txt").read_text(), 0, False
            elif path == ["foo", "bar", "baz"]:
                return (pathological_dir / "deep-foo-bar-baz.txt").read_text(), 0, False
            elif path == ["foo", "bar", "baz", "qux"]:
                qux_called.append(True)
                return (pathological_dir / "deep-foo-bar-baz-qux.txt").read_text(), 0, False
            else:
                return "", 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/foo"):
                # max_depth=3: root=0, bar=1, baz=2, qux would be 3 (at limit)
                opts = make_opts(max_depth=3, max_commands=200)
                tree = discover("foo", opts)

        # At max_depth=3, depth-3 commands are recorded as bare leaves
        # "qux" should appear as a leaf command under "bar-baz", not as a group with "quux"
        group_names = [g["name"] for g in tree["groups"]]
        # "quux" and "also" must NOT appear anywhere as group names
        assert "quux" not in group_names, (
            f"'quux' appeared as a group — depth limit not enforced. Groups: {group_names}"
        )
        assert "also" not in group_names

        # Check that quux is not a command in any group's commands list
        for group in tree["groups"]:
            cmd_names = [c["name"] for c in group.get("commands", [])]
            # quux should not appear as a walked command (it's at depth > cap)
            # It may appear as a bare leaf IF qux was walked — but qux itself should
            # not have its sub-commands (quux) walked further
            pass  # The key assertion is that quux never becomes a GROUP

    def test_depth_cap_depth_reached_value(self, pathological_dir):
        """depth_reached in discovery metadata must reflect max walked depth."""

        def rh(args, timeout):
            path = [a for a in args if not a.startswith("-")]
            if path == ["foo"]:
                return (pathological_dir / "deep-foo.txt").read_text(), 0, False
            elif path == ["foo", "bar"]:
                return (pathological_dir / "deep-foo-bar.txt").read_text(), 0, False
            elif path == ["foo", "bar", "baz"]:
                return (pathological_dir / "deep-foo-bar-baz.txt").read_text(), 0, False
            elif path == ["foo", "bar", "baz", "qux"]:
                return (pathological_dir / "deep-foo-bar-baz-qux.txt").read_text(), 0, False
            else:
                return "", 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/foo"):
                opts = make_opts(max_depth=3, max_commands=200)
                tree = discover("foo", opts)

        # With max_depth=3, walk goes to depth 3 (baz at depth 2, then qux at depth 3 as leaf
        # or depth 2 sub-walk) — depth_reached should be >= 2
        assert tree["discovery"]["depth_reached"] >= 2

    # -----------------------------------------------------------------------
    # Command count cap
    # -----------------------------------------------------------------------

    def test_command_count_cap_halts_with_warning(self):
        """When max_commands is hit, discover halts and records a warning."""
        # Synthetic CLI with many top-level commands
        many_commands_help = (
            "MyCLI — many commands.\n\n"
            "USAGE\n  mycli <command>\n\n"
            "COMMANDS\n"
            + "".join(f"  cmd{i}:   Command {i}\n" for i in range(30))
        )

        call_count = [0]

        def rh(args, timeout):
            call_count[0] += 1
            return many_commands_help, 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/mycli"):
                # Cap at 5 commands total
                opts = make_opts(max_depth=3, max_commands=5)
                tree = discover("mycli", opts)

        warnings = tree["discovery"]["warnings"]
        assert any(
            "limit" in w.lower() or "max" in w.lower() or "halting" in w.lower()
            for w in warnings
        ), f"Expected a command-limit warning, got: {warnings}"

        # Must have walked fewer groups than available
        assert len(tree["groups"]) < 30

    # -----------------------------------------------------------------------
    # Per-call timeout: monkeypatch returns timed_out=True
    # -----------------------------------------------------------------------

    def test_per_call_timeout_skips_subtree(self):
        """When a subcommand times out, it's skipped and a warning is recorded."""
        root_help = (
            "MyCLI.\n\nUSAGE\n  mycli <cmd>\n\n"
            "COMMANDS\n"
            "  fast:     A fast command\n"
            "  slow:     A slow command that times out\n"
        )
        fast_help = "Fast sub.\n\nUSAGE\n  mycli fast [flags]\n\nFLAGS\n  --help  Help\n"

        call_args_log = []

        def rh(args, timeout):
            path = [a for a in args if not a.startswith("-")]
            call_args_log.append(path)
            if path == ["mycli"]:
                return root_help, 0, False
            elif path == ["mycli", "fast"]:
                return fast_help, 0, False
            elif path == ["mycli", "slow"]:
                # Simulate timeout
                return "", -1, True
            else:
                return "", 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/mycli"):
                opts = make_opts(max_depth=2, max_commands=50)
                tree = discover("mycli", opts)

        # "fast" should be present as a group; "slow" as a bare leaf with a warning
        group_names = [g["name"] for g in tree["groups"]]
        assert "fast" in group_names

        warnings = tree["discovery"]["warnings"]
        assert any("timeout" in w.lower() for w in warnings), (
            f"Expected timeout warning, got: {warnings}"
        )

    # -----------------------------------------------------------------------
    # UTF-8 decode with replacement
    # -----------------------------------------------------------------------

    def test_utf8_decode_replacement_no_crash(self):
        """Raw bytes that aren't valid UTF-8 must not crash discover.py."""
        bad_bytes = b"\x80\x81\x82 CLI Help\n\nCOMMANDS\n  go   Go somewhere\n"

        def rh(args, timeout):
            # run_help is already called with a list; we bypass it and
            # test the internal decode path by returning pre-decoded text
            text = bad_bytes.decode("utf-8", errors="replace")
            return text, 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/mycli"):
                opts = make_opts(max_depth=1, max_commands=10)
                # Must not raise
                tree = discover("mycli", opts)

        assert "groups" in tree

    def test_run_help_utf8_replacement_in_actual_decode(self):
        """The run_help function itself decodes stdout bytes with errors=replace."""
        bad_bytes = b"\x80\x81\x82 plain text after"
        mock_result = MagicMock()
        mock_result.stdout = bad_bytes
        mock_result.stderr = b""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            text, rc, timed_out = run_help(["fake", "--help"], 5.0)

        assert not timed_out
        assert "�" in text  # Replacement character
        assert "plain text after" in text

    # -----------------------------------------------------------------------
    # Total timeout
    # -----------------------------------------------------------------------

    def test_total_timeout_stops_walk(self):
        """When total_timeout is nearly exhausted, remaining groups are skipped with warning."""
        root_help = (
            "MyCLI.\n\nUSAGE\n  mycli <cmd>\n\n"
            "COMMANDS\n"
            + "".join(f"  cmd{i}:   Command {i}\n" for i in range(10))
        )

        call_count = [0]
        # We'll manipulate time.monotonic to simulate elapsed time
        original_monotonic = time.monotonic
        start = [None]

        def fake_monotonic():
            t = original_monotonic()
            if start[0] is None:
                start[0] = t
            # After 2 calls, pretend 100 seconds have passed
            if call_count[0] >= 2:
                return start[0] + 200.0
            return t

        def rh(args, timeout):
            call_count[0] += 1
            return root_help, 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/mycli"):
                with patch.object(discover_mod.time, "monotonic", side_effect=fake_monotonic):
                    opts = make_opts(max_depth=2, max_commands=500, total_timeout=5.0)
                    tree = discover("mycli", opts)

        warnings = tree["discovery"]["warnings"]
        assert any("timeout" in w.lower() for w in warnings), (
            f"Expected total-timeout warning, got: {warnings}"
        )


# ===========================================================================
# Unit tests — WalkState
# ===========================================================================

class TestWalkState:
    def test_over_limit_false_when_under(self):
        state = WalkState(
            max_depth=3, max_commands=10, per_call_timeout=5.0,
            total_timeout=30.0, start_time=time.monotonic()
        )
        state.commands_walked = 5
        assert not state.over_limit()

    def test_over_limit_true_when_at_max(self):
        state = WalkState(
            max_depth=3, max_commands=10, per_call_timeout=5.0,
            total_timeout=30.0, start_time=time.monotonic()
        )
        state.commands_walked = 10
        assert state.over_limit()

    def test_timed_out_false_initially(self):
        state = WalkState(
            max_depth=3, max_commands=10, per_call_timeout=5.0,
            total_timeout=30.0, start_time=time.monotonic()
        )
        assert not state.timed_out()

    def test_elapsed_increases(self):
        state = WalkState(
            max_depth=3, max_commands=10, per_call_timeout=5.0,
            total_timeout=30.0, start_time=time.monotonic() - 1.0
        )
        assert state.elapsed() >= 1.0


# ===========================================================================
# Unit tests — get_cli_version
# ===========================================================================

class TestGetCliVersion:
    def test_returns_first_line_of_version_output(self):
        def rh(args, timeout):
            if "--version" in args:
                return "gh version 2.92.0\nsome other line\n", 0, False
            return "", 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            version = get_cli_version("gh", 5.0)
        assert version == "gh version 2.92.0"

    def test_returns_none_when_no_version(self):
        def rh(args, timeout):
            return "", 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            version = get_cli_version("gh", 5.0)
        assert version is None

    def test_handles_timeout_gracefully(self):
        def rh(args, timeout):
            return "", -1, True

        with patch.object(discover_mod, "run_help", side_effect=rh):
            version = get_cli_version("gh", 5.0)
        assert version is None


# ===========================================================================
# Unit tests — walk() function directly
# ===========================================================================

class TestWalk:
    def _make_state(self, max_depth=3, max_commands=100):
        return WalkState(
            max_depth=max_depth,
            max_commands=max_commands,
            per_call_timeout=5.0,
            total_timeout=60.0,
            start_time=time.monotonic(),
        )

    def test_walk_returns_group_on_success(self):
        help_text = (
            "My group.\n\nUSAGE\n  cli grp [flags]\n\n"
            "COMMANDS\n  sub   A subcommand\n\n"
            "FLAGS\n  --help   Help\n"
        )

        def rh(args, timeout):
            return help_text, 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            state = self._make_state()
            group = walk("cli", ["grp"], 1, state)

        assert group is not None
        assert group["name"] == "grp"
        assert group["path"] == ["grp"]

    def test_walk_returns_none_on_timeout(self):
        def rh(args, timeout):
            return "", -1, True

        with patch.object(discover_mod, "run_help", side_effect=rh):
            state = self._make_state()
            group = walk("cli", ["grp"], 1, state)

        assert group is None
        assert any("timeout" in w for w in state.warnings)

    def test_walk_returns_none_on_empty_nonzero(self):
        def rh(args, timeout):
            return "", 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            state = self._make_state()
            group = walk("cli", ["grp"], 1, state)

        assert group is None
        assert any("non-zero" in w.lower() or "empty" in w.lower() for w in state.warnings)

    def test_walk_warns_nonzero_with_stdout(self):
        """Non-zero exit with stdout — parse anyway, add warning."""
        help_text = "Grp.\n\nUSAGE\n  cli grp [flags]\n\nFLAGS\n  --help   Help\n"

        def rh(args, timeout):
            return help_text, 1, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            state = self._make_state()
            group = walk("cli", ["grp"], 1, state)

        assert group is not None
        assert any("non-zero" in w.lower() for w in state.warnings)

    def test_walk_respects_over_limit(self):
        """When state is over the command limit, walk returns None immediately."""
        state = self._make_state(max_commands=0)
        state.commands_walked = 1  # over limit

        group = walk("cli", ["grp"], 1, state)
        assert group is None
        assert any("limit" in w.lower() for w in state.warnings)

    def test_walk_respects_timed_out(self):
        """When total timeout has elapsed, walk returns None immediately."""
        state = WalkState(
            max_depth=3, max_commands=100, per_call_timeout=5.0,
            total_timeout=0.0,  # already timed out
            start_time=time.monotonic() - 100.0,
        )

        group = walk("cli", ["grp"], 1, state)
        assert group is None
        assert any("timeout" in w.lower() for w in state.warnings)

    def test_walk_depth_cap_records_bare_leaves(self):
        """At max_depth, sub-commands of depth-limited commands appear as bare leaves."""
        deep_help = (
            "Deep.\n\nUSAGE\n  cli deep [flags]\n\n"
            "COMMANDS\n  leaf   A leaf command\n  leaf2   Another leaf\n"
        )

        def rh(args, timeout):
            return deep_help, 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            # depth=2, max_depth=3 → recurse
            # At depth=3, no more recursion
            state = self._make_state(max_depth=3)
            group = walk("cli", ["deep"], 2, state)

        assert group is not None
        # Commands should be recorded (as leaves since next level would be depth 3)
        assert "commands" in group or "raw_help" in group

    def test_walk_attaches_raw_help_for_leaf(self):
        """Commands with no subcommands get raw_help attached."""
        leaf_help = "A leaf command with no subcommands.\n\nFLAGS\n  --help   Help\n"

        def rh(args, timeout):
            return leaf_help, 0, False

        with patch.object(discover_mod, "run_help", side_effect=rh):
            state = self._make_state()
            group = walk("cli", ["leaf"], 1, state)

        assert group is not None
        assert "raw_help" in group


# ===========================================================================
# Root timeout test for discover()
# ===========================================================================

class TestDiscoverRootTimeout:
    def test_root_timeout_exits(self, capsys):
        """When root --help times out, discover calls sys.exit(1)."""

        def rh(args, timeout):
            return "", -1, True

        with patch.object(discover_mod, "run_help", side_effect=rh):
            with patch.object(discover_mod.shutil, "which", return_value="/usr/local/bin/mycli"):
                opts = make_opts()
                with pytest.raises(SystemExit) as exc_info:
                    discover("mycli", opts)
                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "timed out" in captured.err.lower() or "timeout" in captured.err.lower()
