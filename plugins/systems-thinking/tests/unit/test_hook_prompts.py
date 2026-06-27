"""Tests for hook prompts defined in hooks/hooks.json."""

import json

import pytest


@pytest.fixture
def settings(settings_path):
    return json.loads(settings_path.read_text(encoding="utf-8"))


@pytest.fixture
def hooks(settings):
    return settings["hooks"]


@pytest.fixture
def preflight_hook(hooks):
    entry = hooks["UserPromptSubmit"][0]
    # Enforce nested format: each entry must wrap hooks in a non-empty "hooks" list
    assert "hooks" in entry, "UserPromptSubmit entry must contain a 'hooks' list"
    assert isinstance(entry["hooks"], list) and entry["hooks"], (
        "UserPromptSubmit 'hooks' must be a non-empty list"
    )
    hook = entry["hooks"][0]
    assert isinstance(hook, dict), "Wrapped preflight hook must be a dict"
    return hook


@pytest.fixture
def completion_hook(hooks):
    entry = hooks["Stop"][0]
    assert "hooks" in entry, "Stop entry must contain a 'hooks' list"
    assert isinstance(entry["hooks"], list) and entry["hooks"], (
        "Stop 'hooks' must be a non-empty list"
    )
    hook = entry["hooks"][0]
    assert isinstance(hook, dict), "Wrapped completion hook must be a dict"
    return hook


# ── Structure tests ──────────────────────────────────────────────────────────


def test_settings_json_is_valid_json(settings_path):
    """settings.json must parse as valid JSON."""
    text = settings_path.read_text(encoding="utf-8")
    json.loads(text)  # raises on invalid JSON


def test_hooks_key_exists(settings):
    assert "hooks" in settings


def test_user_prompt_submit_hook_exists(hooks):
    assert "UserPromptSubmit" in hooks
    assert len(hooks["UserPromptSubmit"]) >= 1


def test_stop_hook_exists(hooks):
    assert "Stop" in hooks
    assert len(hooks["Stop"]) >= 1


def test_hooks_use_nested_wrapper_schema(hooks):
    """Each hook entry must be a wrapper object with a non-empty 'hooks' list."""
    for hook_type, entries in hooks.items():
        assert isinstance(entries, list), f"{hook_type} entries must be a list"
        for idx, entry in enumerate(entries):
            assert isinstance(entry, dict), f"{hook_type}[{idx}] entry must be a dict"
            assert "hooks" in entry, f"{hook_type}[{idx}] must contain a 'hooks' list"
            inner = entry["hooks"]
            assert isinstance(inner, list) and inner, (
                f"{hook_type}[{idx}].hooks must be a non-empty list"
            )
            for j, hook in enumerate(inner):
                assert isinstance(hook, dict), f"{hook_type}[{idx}].hooks[{j}] must be a dict"
                assert "type" in hook, f"{hook_type}[{idx}].hooks[{j}] must have a 'type'"
                assert isinstance(hook["type"], str), (
                    f"{hook_type}[{idx}].hooks[{j}].type must be a string"
                )
                if "prompt" in hook:
                    assert isinstance(hook["prompt"], str), (
                        f"{hook_type}[{idx}].hooks[{j}].prompt must be a string"
                    )


def test_preflight_hook_is_command_type(preflight_hook):
    """UserPromptSubmit hook uses a command gate to scope to systems-thinking sessions."""
    assert preflight_hook["type"] == "command"


def test_completion_hook_is_command_type(completion_hook):
    """Stop hook uses a command gate script to scope to systems-thinking sessions."""
    assert completion_hook["type"] == "command"


def test_completion_hook_references_gate_script(completion_hook):
    """Stop hook must reference the quality gate script."""
    assert "stop-quality-gate.sh" in completion_hook["command"]


def test_completion_hook_uses_plugin_root(completion_hook):
    """Stop hook command must use ${CLAUDE_PLUGIN_ROOT} for portability."""
    assert "${CLAUDE_PLUGIN_ROOT}" in completion_hook["command"]


# ── Content tests ────────────────────────────────────────────────────────────


@pytest.fixture
def user_prompt_gate_path():
    from pathlib import Path
    return Path(__file__).resolve().parents[2] / "hooks" / "user-prompt-gate.sh"


def test_user_prompt_gate_exists(user_prompt_gate_path):
    assert user_prompt_gate_path.is_file(), "user-prompt-gate.sh must exist in hooks/"


def test_preflight_references_gate_script(preflight_hook):
    """UserPromptSubmit hook must reference the user-prompt-gate script."""
    assert "user-prompt-gate.sh" in preflight_hook["command"]


def test_preflight_gate_mentions_extraction_synthesis(user_prompt_gate_path):
    content = user_prompt_gate_path.read_text().lower()
    assert "extraction" in content, "Preflight gate should mention extraction"
    assert "synthesis" in content, "Preflight gate should mention synthesis"


def test_preflight_gate_mentions_source_anchors(user_prompt_gate_path):
    content = user_prompt_gate_path.read_text().lower()
    assert "source" in content, "Preflight gate should mention source"


def test_preflight_gate_uses_slash_command_matching(user_prompt_gate_path):
    """Preflight gate must match slash-command invocations, not loose keyword mentions."""
    content = user_prompt_gate_path.read_text()
    assert "SLASH_PATTERN" in content or "^/" in content, (
        "Preflight gate must use slash-command pattern matching to avoid "
        "false positives on casual mentions of component names"
    )


def test_preflight_gate_sources_discover_components(user_prompt_gate_path):
    """Preflight gate must source discover-components.sh for dynamic discovery."""
    content = user_prompt_gate_path.read_text()
    assert "discover-components.sh" in content


# ── Gate script tests ───────────────────────────────────────────────────────


@pytest.fixture
def gate_script_path():
    from pathlib import Path
    return Path(__file__).resolve().parents[2] / "hooks" / "stop-quality-gate.sh"


def test_gate_script_exists(gate_script_path):
    assert gate_script_path.is_file(), "stop-quality-gate.sh must exist in hooks/"


def test_gate_script_checks_quality_keywords(gate_script_path):
    """Gate script must check for assumptions, risks, unresolved, and next steps."""
    content = gate_script_path.read_text().lower()
    assert "assumption" in content
    assert "risk" in content
    assert "unresolved" in content
    assert "next step" in content or "next check" in content


@pytest.fixture
def discover_script_path():
    from pathlib import Path
    return Path(__file__).resolve().parents[2] / "hooks" / "discover-components.sh"


def test_discover_script_exists(discover_script_path):
    assert discover_script_path.is_file(), "discover-components.sh must exist in hooks/"


def test_gate_script_sources_discover_components(gate_script_path):
    """Gate script must source discover-components.sh for dynamic pattern discovery."""
    content = gate_script_path.read_text()
    assert "discover-components.sh" in content


def test_discover_script_reads_skills_and_agents(discover_script_path):
    """discover-components.sh must read from skills/ and agents/ directories."""
    content = discover_script_path.read_text()
    assert "skills" in content, "Discovery script must reference skills directory"
    assert "agents" in content, "Discovery script must reference agents directory"
    assert "INVOCATION_PATTERNS" in content, "Discovery script must export INVOCATION_PATTERNS"
    assert "systems-thinking" in content.lower()


def test_gate_script_does_not_use_set_e(gate_script_path):
    """Gate script must not use 'set -e' or 'set -euo' — it kills grep || fallbacks."""
    content = gate_script_path.read_text()
    # Check for set -e, set -euo, set -eo, etc. (any set that includes -e)
    import re
    # Match 'set' followed by flags that include 'e'
    assert not re.search(r'\bset\s+-\w*e\w*\b', content), (
        "Gate script must not use 'set -e' — grep non-zero exits kill the script "
        "before the '|| missing=...' fallback can execute"
    )


def test_gate_script_greps_file_directly(gate_script_path):
    """Gate script must grep the transcript file directly, not load into a variable.

    Loading a large JSONL transcript into a shell variable via $(cat ...) fails
    silently when the file exceeds ARG_MAX or contains problematic characters.
    """
    content = gate_script_path.read_text()
    # Should NOT have: transcript=$(cat "$transcript_path") followed by echo "$transcript" | grep
    assert 'transcript=$(cat' not in content, (
        "Gate script must not load transcript into a variable — "
        "grep the file directly to handle large transcripts"
    )


# ── Quality constraints ──────────────────────────────────────────────────────


def _flatten_hooks(entries, hook_type="<unknown>"):
    """Yield individual hook dicts from the required nested wrapper format."""
    for idx, entry in enumerate(entries):
        assert isinstance(entry, dict), f"{hook_type}[{idx}] must be a dict"
        assert "hooks" in entry, f"{hook_type}[{idx}] must contain a 'hooks' list"
        inner = entry["hooks"]
        assert isinstance(inner, list) and inner, (
            f"{hook_type}[{idx}] 'hooks' must be a non-empty list"
        )
        for j, hook in enumerate(inner):
            assert isinstance(hook, dict), f"{hook_type}[{idx}].hooks[{j}] must be a dict"
            yield hook


def test_hook_prompts_are_concise(hooks):
    """Each hook prompt should be under 500 characters to stay focused."""
    for hook_type, entries in hooks.items():
        for i, hook in enumerate(_flatten_hooks(entries, hook_type)):
            if "prompt" in hook:
                length = len(hook["prompt"])
                assert length < 500, f"{hook_type}[{i}] prompt is {length} chars (max 500)"


def test_no_bash_hooks(hooks):
    """v1 should not define any bash hooks."""
    for hook_type, entries in hooks.items():
        for i, hook in enumerate(_flatten_hooks(entries, hook_type)):
            assert hook.get("type") != "bash", (
                f"{hook_type}[{i}] has type 'bash'; bash hooks are not allowed in v1"
            )
