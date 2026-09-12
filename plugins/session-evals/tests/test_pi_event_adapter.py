import importlib.util
import json
import os

import pytest


HERE = os.path.dirname(__file__)
PATH = os.path.join(HERE, "..", "scripts", "pi_event_adapter.py")
spec = importlib.util.spec_from_file_location("adapter", PATH)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

LIMITS = {"turns": 2, "tools": 2, "subprocesses": 1,
          "input_tokens": 20, "output_tokens": 10}


def event(kind, **extra):
    return json.dumps({"type": kind, **extra})


def assistant(**usage):
    return event("message_end", message={"role": "assistant", "usage": usage})


def test_measures_actual_assistant_turns_tool_pairs_and_cache_tokens():
    got = adapter.measured_events([
        event("turn_end"),
        event("tool_execution_start", toolName="read", toolCallId="call-1"),
        event("tool_execution_end", toolCallId="call-1"),
        assistant(input=4, output=2, cacheRead=3, cacheWrite=1),
    ], LIMITS)
    assert got == {"turns": 1, "tools": 1, "subprocesses": 1,
                   "input_tokens": 4, "output_tokens": 2,
                   "cache_read_tokens": 3, "cache_write_tokens": 1}


@pytest.mark.parametrize("line", [
    event("tool_execution_start", toolName="bash", toolCallId="bad"),
    event("tool_execution_end", toolCallId="unknown"),
    event("message_end", message={"role": "assistant"}),
    event("message_end", message={"role": "assistant", "usage": {"input": True, "output": 0}}),
    event("message_end", message={"role": "assistant", "usage": {"input": 0, "output": -1}}),
    event("message_end", message={"role": "assistant", "usage": {"input": 0, "output": 1}, "stopReason": "length"}),
    event("cancelled"),
    "[]",
    "{",
])
def test_rejects_disallowed_invalid_or_incomplete_events(line):
    with pytest.raises(ValueError):
        adapter.measured_events([line], LIMITS)


def test_repaired_final_call_is_checked_after_repair_and_must_be_paired():
    events = [
        event("tool_execution_start", toolName="read", toolCallId="before-repair"),
        event("tool_execution_end", toolCallId="before-repair"),
        event("tool_execution_start", toolName="bash", toolCallId="after-repair"),
        assistant(input=1, output=1),
    ]
    with pytest.raises(ValueError, match="disallowed Pi tool"):
        adapter.measured_events(events, LIMITS)


def test_line_and_stream_bounds_apply_before_event_processing():
    with pytest.raises(ValueError, match="line exceeded"):
        adapter.measured_events(["x" * 100], LIMITS, max_line_bytes=10)
    with pytest.raises(ValueError, match="stream exceeded"):
        adapter.measured_events([assistant(input=0, output=1), assistant(input=0, output=1)],
                               LIMITS, max_stream_bytes=10)


def test_pipe_reader_enforces_output_limits_before_constructing_a_json_line(tmp_path):
    output = tmp_path / "events.jsonl"
    output.write_bytes(b"x" * (adapter.MAX_EVENT_LINE_BYTES + 1))
    with output.open("rb") as stream:
        with pytest.raises(ValueError, match="line exceeded"):
            list(adapter._bounded_event_lines(stream))


def test_main_builds_no_discovery_custom_tool_composition(monkeypatch, tmp_path):
    prompt = tmp_path / "prompt.json"
    prompt.write_text(json.dumps({"prompt": "fix fixture"}), encoding="utf-8")
    guard = tmp_path / "guard.ts"
    guard.write_text("export default () => {}\n", encoding="utf-8")
    reviewed = tmp_path / "reviewed.ts"
    reviewed.write_text("export default () => {}\n", encoding="utf-8")
    captured = {}

    class Proc:
        stdout = [assistant(input=1, output=1)]

        def wait(self):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return Proc()

    monkeypatch.setattr(adapter.subprocess, "Popen", fake_popen)
    assert adapter.main(["--launcher", "/reviewed/pi", "--prompt-file", str(prompt),
                         "--session-dir", str(tmp_path / "sessions"),
                         "--restricted-tools-extension", str(guard),
                         "--reviewed-extension", str(reviewed), "--max-turns", "1",
                         "--max-tools", "1"]) == 0
    command = captured["command"]
    assert "--no-extensions" in command
    assert "--no-builtin-tools" in command
    assert command.count("--extension") == 2
    assert command[command.index("--tools") + 1] == "read,edit,write"
    assert "--no-skills" in command and "--no-context-files" in command
    assert "HOME" in captured["env"]
