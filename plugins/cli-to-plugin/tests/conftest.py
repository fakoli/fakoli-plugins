"""
conftest.py — Shared fixtures for discover.py and override.py tests.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Callable
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Root path helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


# ---------------------------------------------------------------------------
# Fixture directory Path objects
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def gh_raw_dir() -> Path:
    return FIXTURES_DIR / "gh-help-raw"


@pytest.fixture(scope="session")
def kubectl_raw_dir() -> Path:
    return FIXTURES_DIR / "kubectl-help-raw"


@pytest.fixture(scope="session")
def docker_raw_dir() -> Path:
    return FIXTURES_DIR / "docker-help-raw"


@pytest.fixture(scope="session")
def pathological_dir() -> Path:
    return FIXTURES_DIR / "pathological"


# ---------------------------------------------------------------------------
# Pre-loaded expected JSON trees
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def gh_expected() -> dict:
    return json.loads((FIXTURES_DIR / "gh-help-tree.expected.json").read_text())


@pytest.fixture(scope="session")
def kubectl_expected() -> dict:
    return json.loads((FIXTURES_DIR / "kubectl-help-tree.expected.json").read_text())


@pytest.fixture(scope="session")
def docker_expected() -> dict:
    return json.loads((FIXTURES_DIR / "docker-help-tree.expected.json").read_text())


# ---------------------------------------------------------------------------
# Monkeypatch subprocess helper
# ---------------------------------------------------------------------------

def _fixture_file_for_args(fixture_dir: Path, cli: str, args: list[str]) -> Path | None:
    """
    Map a subprocess invocation to a fixture file.

    Mapping rules:
    - [cli, "--help"]               → <fixture_dir>/<cli>.txt
    - [cli, sub, "--help"]          → <fixture_dir>/<cli>-<sub>.txt
    - [cli, sub1, sub2, "--help"]   → <fixture_dir>/<cli>-<sub1>-<sub2>.txt
    - [cli, "--version"] / etc.     → None (unknown, returns empty)
    - deep/ prefix: look in pathological dir for deep-<segments>.txt

    For the pathological "foo" CLI we look in fixture_dir directly.
    """
    # Filter out --help from the path segments
    path_segments = [a for a in args if not a.startswith("-")]

    if not path_segments:
        return None

    # Build dash-joined name:  cli-sub1-sub2
    name_parts = [path_segments[0]] + path_segments[1:]  # includes cli name
    filename = "-".join(name_parts) + ".txt"
    candidate = fixture_dir / filename
    if candidate.exists():
        return candidate
    return None


def make_subprocess_patcher(
    fixture_map: dict[tuple, tuple[str, int]],
    default_stdout: str = "",
    default_rc: int = 0,
):
    """
    Return a function suitable for monkeypatching subprocess.run.

    fixture_map: maps (cli, *path_segments) → (stdout_text, returncode)
        e.g. {("gh",): ("...", 0), ("gh", "pr"): ("...", 0)}

    Any invocation not found in fixture_map uses default_stdout/default_rc.
    Timeout is simulated by checking the 'timeout' kwarg — not actually waited.
    """

    def fake_run(cmd_args, **kwargs):
        # cmd_args is a list like ["gh", "pr", "--help"]
        # Strip trailing "--help" to build the lookup key
        path = tuple(a for a in cmd_args if not a.startswith("-"))
        entry = fixture_map.get(path)
        if entry is None:
            stdout_text = default_stdout
            rc = default_rc
        else:
            stdout_text, rc = entry

        mock = MagicMock()
        mock.stdout = stdout_text.encode("utf-8") if isinstance(stdout_text, str) else stdout_text
        mock.stderr = b""
        mock.returncode = rc
        return mock

    return fake_run


def make_subprocess_patcher_from_dir(
    fixture_dir: Path,
    cli: str,
    *,
    default_stdout: str = "",
    default_rc: int = 0,
    overrides: dict | None = None,
):
    """
    Build a subprocess.run monkeypatch from a fixture directory.

    For each call to subprocess.run(args, ...) where args looks like
    [cli, sub..., "--help"], tries to read <fixture_dir>/<cli>-<sub...>.txt.
    Falls back to default_stdout / default_rc when no file is found.

    overrides: dict mapping tuple(path_segments_without_flags) → (stdout, rc)
    """
    _overrides = overrides or {}

    def fake_run(cmd_args, **kwargs):
        # Build key from non-flag segments
        path = tuple(a for a in cmd_args if not a.startswith("-"))

        # Check caller-supplied overrides first
        if path in _overrides:
            stdout_text, rc = _overrides[path]
        else:
            fx_file = _fixture_file_for_args(fixture_dir, cli, list(cmd_args))
            if fx_file is not None:
                stdout_text = fx_file.read_text(encoding="utf-8")
                rc = 0
            else:
                stdout_text = default_stdout
                rc = default_rc

        mock = MagicMock()
        mock.stdout = (
            stdout_text.encode("utf-8")
            if isinstance(stdout_text, str)
            else stdout_text
        )
        mock.stderr = b""
        mock.returncode = rc
        return mock

    return fake_run


# ---------------------------------------------------------------------------
# Subset-match assertion utility
# ---------------------------------------------------------------------------

def assert_subset_match(actual: dict, expected: dict) -> None:
    """
    Assert that every group and command in `expected` appears in `actual`.

    Rules (from fixtures/README.md):
    - Every group in expected must exist in actual (matched by name)
    - For each matched group: name, path, summary must equal
    - For each command in expected group: must exist in actual group (by name);
      name, path, summary must equal
    - Extra groups and extra commands in actual are allowed
    - global_flags (if present in expected) must exactly equal actual's global_flags
    """
    actual_groups = {g["name"]: g for g in actual.get("groups", [])}
    expected_groups = {g["name"]: g for g in expected.get("groups", [])}

    for gname, exp_group in expected_groups.items():
        assert gname in actual_groups, (
            f"expected group {gname!r} not found in actual output.\n"
            f"actual group names: {sorted(actual_groups.keys())}"
        )
        act_group = actual_groups[gname]

        # Core fields must match exactly
        assert act_group["name"] == exp_group["name"], (
            f"group {gname!r}: name mismatch"
        )
        assert act_group["path"] == exp_group["path"], (
            f"group {gname!r}: path mismatch — expected {exp_group['path']}, "
            f"got {act_group['path']}"
        )
        if "summary" in exp_group:
            assert act_group.get("summary") == exp_group["summary"], (
                f"group {gname!r}: summary mismatch — "
                f"expected {exp_group['summary']!r}, "
                f"got {act_group.get('summary')!r}"
            )

        # Check commands subset
        exp_commands = {c["name"]: c for c in exp_group.get("commands", [])}
        act_commands = {c["name"]: c for c in act_group.get("commands", [])}

        for cname, exp_cmd in exp_commands.items():
            assert cname in act_commands, (
                f"group {gname!r}: expected command {cname!r} not found.\n"
                f"actual commands: {sorted(act_commands.keys())}"
            )
            act_cmd = act_commands[cname]
            assert act_cmd["name"] == exp_cmd["name"], (
                f"group {gname!r} / command {cname!r}: name mismatch"
            )
            assert act_cmd["path"] == exp_cmd["path"], (
                f"group {gname!r} / command {cname!r}: path mismatch — "
                f"expected {exp_cmd['path']}, got {act_cmd['path']}"
            )
            if "summary" in exp_cmd:
                assert act_cmd.get("summary") == exp_cmd["summary"], (
                    f"group {gname!r} / command {cname!r}: summary mismatch — "
                    f"expected {exp_cmd['summary']!r}, "
                    f"got {act_cmd.get('summary')!r}"
                )

    # global_flags: exact equality if expected has them
    if "global_flags" in expected:
        assert actual.get("global_flags") == expected["global_flags"], (
            f"global_flags mismatch:\n"
            f"expected: {json.dumps(expected['global_flags'], indent=2)}\n"
            f"actual:   {json.dumps(actual.get('global_flags'), indent=2)}"
        )


# ---------------------------------------------------------------------------
# Shared argparse Namespace builder
# ---------------------------------------------------------------------------

def make_opts(
    *,
    max_depth: int = 3,
    max_commands: int = 500,
    per_call_timeout: float = 5.0,
    total_timeout: float = 30.0,
    output: str = "-",
):
    """Build a minimal argparse.Namespace for use with discover.discover()."""
    import argparse
    return argparse.Namespace(
        max_depth=max_depth,
        max_commands=max_commands,
        per_call_timeout=per_call_timeout,
        total_timeout=total_timeout,
        output=output,
    )
