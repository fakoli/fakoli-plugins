import importlib.util
import json
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
