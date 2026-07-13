import importlib.util
import io
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "session_stats.py"


def load_session_stats():
    spec = importlib.util.spec_from_file_location("session_stats", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_claude_session_parsing_still_counts_workflows_and_turns(tmp_path):
    mod = load_session_stats()
    session = tmp_path / "claude.jsonl"
    write_jsonl(session, [
        {
            "timestamp": "2026-06-25T10:00:00Z",
            "cwd": "/repo",
            "gitBranch": "main",
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 100,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 30,
                    "output_tokens": 10,
                },
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "session-retro"}},
                    {"type": "tool_use", "name": "Workflow", "input": {"name": "review-pass"}},
                ],
            },
        },
        {
            "timestamp": "2026-06-25T10:02:00Z",
            "type": "user",
            "message": {
                "content": (
                    "<task-notification><summary>review pass</summary>"
                    "<agent_count>2</agent_count><subagent_tokens>30</subagent_tokens>"
                    "<tool_uses>4</tool_uses><duration_ms>60000</duration_ms></task-notification>"
                )
            },
        },
        {
            "timestamp": "2026-06-25T10:03:00Z",
            "type": "user",
            "message": {"content": "Please validate the change"},
        },
    ])

    parsed = mod.parse(str(session))
    aggregate = mod.aggregate([parsed])

    assert parsed["runtime"] == "claude"
    assert parsed["out"] == 10
    assert aggregate["runtimes"] == ["claude"]
    assert aggregate["main_output_tokens"] == 10
    assert aggregate["workflow_tokens"] == 30
    assert aggregate["generative_total"] == 40
    assert aggregate["workflows"] == 1
    assert aggregate["user_turns"] == 1
    assert aggregate["tools"]["Skill"] == 1
    assert aggregate["skills_used"]["session-retro"] == 1


def test_codex_main_rollout_expands_subagents_and_splits_tokens(tmp_path, monkeypatch):
    mod = load_session_stats()
    codex_root = tmp_path / ".codex" / "sessions"
    monkeypatch.setattr(mod, "CODEX_SESSIONS", str(codex_root))
    monkeypatch.setattr(mod, "PROJECTS", str(tmp_path / ".claude" / "projects"))

    day = codex_root / "2026" / "06" / "25"
    main = day / "rollout-main.jsonl"
    child = day / "rollout-child.jsonl"
    other = day / "rollout-other.jsonl"
    prompt = "Implement and verify Codex parser support"

    write_jsonl(main, [
        {
            "timestamp": "2026-06-25T10:00:00Z",
            "type": "session_meta",
            "payload": {"session_id": "sid", "id": "sid", "cwd": "/repo"},
        },
        {
            "timestamp": "2026-06-25T10:01:00Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Build Codex support"}],
            },
        },
        {
            "timestamp": "2026-06-25T10:02:00Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "<subagent_notification>{}</subagent_notification>"}],
            },
        },
        {
            "timestamp": "2026-06-25T10:03:00Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "arguments": json.dumps({"agent_type": "worker", "message": prompt}),
            },
        },
        {
            "timestamp": "2026-06-25T10:04:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 1000,
                        "cached_input_tokens": 600,
                        "output_tokens": 50,
                        "reasoning_output_tokens": 7,
                    },
                    "last_token_usage": {
                        "output_tokens": 50,
                        "reasoning_output_tokens": 7,
                    },
                },
            },
        },
    ])
    write_jsonl(child, [
        {
            "timestamp": "2026-06-25T10:04:00Z",
            "type": "session_meta",
            "payload": {
                "session_id": "sid",
                "id": "child",
                "parent_thread_id": "sid",
                "cwd": "/repo",
            },
        },
        {
            "timestamp": "2026-06-25T10:05:00Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        },
        {
            "timestamp": "2026-06-25T10:06:00Z",
            "type": "response_item",
            "payload": {"type": "function_call", "name": "exec_command", "arguments": "{}"},
        },
        {
            "timestamp": "2026-06-25T10:07:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 200,
                        "cached_input_tokens": 100,
                        "output_tokens": 20,
                        "reasoning_output_tokens": 3,
                    },
                    "last_token_usage": {
                        "output_tokens": 20,
                        "reasoning_output_tokens": 3,
                    },
                },
            },
        },
        {
            "timestamp": "2026-06-25T10:08:00Z",
            "type": "event_msg",
            "payload": {"type": "task_complete", "duration_ms": 120000},
        },
    ])
    write_jsonl(other, [
        {
            "timestamp": "2026-06-25T10:09:00Z",
            "type": "session_meta",
            "payload": {"session_id": "other", "id": "other", "cwd": "/repo"},
        },
    ])

    expanded = mod.expand_paths([str(main)])
    expanded_from_child = mod.expand_paths([str(child)])
    aggregate = mod.aggregate([mod.parse(path) for path in expanded])

    assert expanded == [str(main), str(child)]
    assert expanded_from_child == [str(main), str(child)]
    assert aggregate["runtimes"] == ["codex"]
    assert aggregate["sessions"] == [str(main), str(child)]
    assert aggregate["main_output_tokens"] == 57
    assert aggregate["workflow_tokens"] == 23
    assert aggregate["generative_total"] == 80
    assert aggregate["fresh_input_tokens"] == 1200
    assert aggregate["cache_read_tokens"] == 700
    assert aggregate["workflows"] == 1
    assert aggregate["workflow_agents"] == 1
    assert aggregate["workflow_runs"][0]["summary"] == prompt
    assert aggregate["workflow_runs"][0]["tool_uses"] == 1
    assert aggregate["agent_types"]["worker"] == 1
    assert aggregate["tools"]["spawn_agent"] == 1
    assert aggregate["tools"]["exec_command"] == 1
    assert aggregate["user_turn_text"] == ["Build Codex support"]
    assert aggregate["workflow_tokens_available"] is True
    assert aggregate["measurement_notes"] == []


def _codex_meta_row(ts, session_id, rollout_id, parent=None, source=None):
    payload = {"session_id": session_id, "id": rollout_id, "cwd": "/repo"}
    if parent is not None:
        payload["parent_thread_id"] = parent
    if source is not None:
        payload["source"] = source
    return {"timestamp": ts, "type": "session_meta", "payload": payload}


def _token_count_row(ts, out_tokens, in_tokens=100, cached=50):
    return {
        "timestamp": ts,
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": in_tokens,
                    "cached_input_tokens": cached,
                    "output_tokens": out_tokens,
                    "reasoning_output_tokens": 0,
                },
                "last_token_usage": {"output_tokens": out_tokens},
            },
        },
    }


def _user_row(ts, text):
    return {
        "timestamp": ts,
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def test_list_and_find_survive_cp1252_stdout(tmp_path, monkeypatch):
    """Issue #135: default Windows consoles (cp1252) can't encode the ↳ marker."""
    mod = load_session_stats()
    projects = tmp_path / ".claude" / "projects"
    monkeypatch.setattr(mod, "PROJECTS", str(projects))
    monkeypatch.setattr(mod, "CODEX_SESSIONS", str(tmp_path / ".codex" / "sessions"))
    write_jsonl(projects / "repo" / "session.jsonl", [
        {
            "timestamp": "2026-06-25T10:00:00Z",
            "cwd": "/repo",
            "gitBranch": "main",
            "type": "user",
            "message": {"content": "Fix the anvil parser"},
        },
    ])

    buf = io.BytesIO()
    stream = io.TextIOWrapper(buf, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    mod.cmd_list([])
    mod.cmd_find(["parser"])
    stream.flush()

    text = buf.getvalue().decode("cp1252")
    assert "->" in text          # marker degraded instead of crashing
    assert "Fix the anvil parser" in text
    assert "session.jsonl" in text


def test_expand_paths_dedupes_equivalent_path_forms(tmp_path, monkeypatch):
    """Issue #134: the same rollout selected via two path spellings must count once."""
    mod = load_session_stats()
    codex_root = tmp_path / ".codex" / "sessions"
    monkeypatch.setattr(mod, "CODEX_SESSIONS", str(codex_root))
    monkeypatch.setattr(mod, "PROJECTS", str(tmp_path / ".claude" / "projects"))

    day = codex_root / "2026" / "06" / "25"
    main = day / "rollout-main.jsonl"
    write_jsonl(main, [
        _codex_meta_row("2026-06-25T10:00:00Z", "sid", "sid"),
        _token_count_row("2026-06-25T10:01:00Z", 40),
    ])

    messy = f"{day}{os.sep}.{os.sep}rollout-main.jsonl"
    expanded = mod.expand_paths([str(main), messy])

    assert len(expanded) == 1
    assert os.path.basename(expanded[0]) == "rollout-main.jsonl"


def test_forked_sibling_keeps_identity_and_reports_tokens_unavailable(tmp_path, monkeypatch):
    """Issue #134: a replayed session_meta must not erase the fork's identity,
    and replayed parent totals must not be charged again as delegated work."""
    mod = load_session_stats()
    codex_root = tmp_path / ".codex" / "sessions"
    monkeypatch.setattr(mod, "CODEX_SESSIONS", str(codex_root))
    monkeypatch.setattr(mod, "PROJECTS", str(tmp_path / ".claude" / "projects"))

    day = codex_root / "2026" / "06" / "25"
    root = day / "rollout-root.jsonl"
    fork = day / "rollout-fork.jsonl"

    write_jsonl(root, [
        _codex_meta_row("2026-06-25T10:00:00Z", "sid", "sid"),
        _user_row("2026-06-25T10:01:00Z", "Kick off the heavy generation"),
        {
            "timestamp": "2026-06-25T10:02:00Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "arguments": json.dumps({"agent_type": "worker", "message": "Run subtask A"}),
            },
        },
        _token_count_row("2026-06-25T10:03:00Z", 400, in_tokens=1000, cached=500),
    ])
    # Forked sibling: its own meta (parent set) first, then the REPLAYED
    # parent meta (parent_thread_id absent) plus replayed parent history and
    # a cumulative token snapshot that includes the parent's totals.
    write_jsonl(fork, [
        _codex_meta_row("2026-06-25T10:04:00Z", "sid", "fork-1", parent="sid"),
        _codex_meta_row("2026-06-25T10:04:01Z", "sid", "sid"),
        _user_row("2026-06-25T10:04:02Z", "Kick off the heavy generation"),
        {   # the parent's spawn_agent call, REPLAYED into the fork's history
            "timestamp": "2026-06-25T10:04:03Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "arguments": json.dumps({"agent_type": "worker", "message": "Run subtask A"}),
            },
        },
        _user_row("2026-06-25T10:05:00Z", "Run subtask A"),
        _token_count_row("2026-06-25T10:06:00Z", 450, in_tokens=1200, cached=600),
    ])

    parsed_fork = mod.parse(str(fork))
    assert parsed_fork["codex_is_subagent"] is True
    assert parsed_fork["codex_forked"] is True
    assert parsed_fork["parent_thread_id"] == "sid"
    assert parsed_fork["id"] == "fork-1"

    expanded = mod.expand_paths([str(root)])
    assert sorted(os.path.basename(p) for p in expanded) == [
        "rollout-fork.jsonl", "rollout-root.jsonl",
    ]

    agg = mod.aggregate([mod.parse(p) for p in expanded])
    # Main-loop totals come from the root only; the fork's cumulative
    # snapshot (which replays the parent's 400) is not double-counted.
    assert agg["main_output_tokens"] == 400
    assert agg["fresh_input_tokens"] == 1000
    assert agg["cache_read_tokens"] == 500
    # Delegated totals cannot be proven from a forked rollout — unavailable.
    assert agg["workflow_tokens_available"] is False
    assert agg["workflow_runs"][0]["tokens"] is None
    assert agg["workflow_tokens"] == 0
    assert agg["measurement_notes"]
    # Replayed parent turns are not human messages in this corpus.
    assert agg["user_turns"] == 1
    # The fork's replayed copy of the parent's spawn_agent call and assistant
    # history must not double the tool/turn counters.
    assert agg["tools"]["spawn_agent"] == 1
    # A type whose only run is token-unavailable reports None, not 0.
    by_type = next(iter(agg["workflow_by_type"].values()))
    assert by_type["tokens"] is None
    assert by_type["unknown_runs"] == 1

    report = mod.report_md(agg)
    assert "n/a" in report
    assert "0%" not in report


def test_encrypted_prompts_fall_back_to_agent_labels(tmp_path, monkeypatch):
    """Issue #134: encrypted gAAAA… payloads must not become labels or turns."""
    mod = load_session_stats()
    codex_root = tmp_path / ".codex" / "sessions"
    monkeypatch.setattr(mod, "CODEX_SESSIONS", str(codex_root))
    monkeypatch.setattr(mod, "PROJECTS", str(tmp_path / ".claude" / "projects"))

    day = codex_root / "2026" / "06" / "25"
    root = day / "rollout-root.jsonl"
    encrypted = "gAAAA" + "B" * 80

    write_jsonl(root, [
        _codex_meta_row("2026-06-25T10:00:00Z", "sid", "sid"),
        _user_row("2026-06-25T10:00:30Z", encrypted),
        {
            "timestamp": "2026-06-25T10:01:00Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "arguments": json.dumps({
                    "agent_type": "worker",
                    "message": encrypted,
                    "agent_nickname": "critic-1",
                }),
            },
        },
        _token_count_row("2026-06-25T10:02:00Z", 100),
    ])

    agg = mod.aggregate([mod.parse(p) for p in mod.expand_paths([str(root)])])
    assert agg["workflow_runs"][0]["summary"] == "critic-1"
    assert agg["user_turn_text"] == []
