"""Format-faithful synthetic Pi 0.84/0.85 session reader tests."""

import importlib.util
import json
import os


HERE = os.path.dirname(__file__)
SCRIPTS = os.path.join(HERE, "..", "scripts")


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reader = _load("pi_session_reader")
miner = _load("session_miner")


def write_rows(path, rows, trailing=""):
    with open(path, "w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
        stream.write(trailing)


def entry(entry_id, parent_id, kind, **extra):
    row = {"type": kind, "id": entry_id, "parentId": parent_id,
           "timestamp": "2026-09-12T00:00:00.000Z"}
    row.update(extra)
    return row


def user(text):
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def assistant(content):
    return {"role": "assistant", "content": content,
            "provider": "anvil", "model": "llm.primary"}


def test_selected_leaf_excludes_abandoned_branch_and_pairs_tool_result(tmp_path):
    session = tmp_path / "pi.jsonl"
    write_rows(session, [
        {"type": "session", "version": 3, "id": "session", "timestamp": "x", "cwd": "/synthetic"},
        entry("u1", None, "message", message=user("Fix the parser")),
        entry("bad-call", "u1", "message", message=assistant([
            {"type": "toolCall", "id": "call-bad", "name": "bash", "arguments": {"command": "rm -rf /"}}])),
        entry("good-call", "u1", "message", message=assistant([
            {"type": "toolCall", "id": "call-good", "name": "bash", "arguments": {"command": "pytest -q"}}])),
        entry("result", "good-call", "message", message={"role": "toolResult", "toolCallId": "call-good", "content": [{"type": "text", "text": "1 passed"}]}),
        entry("correction", "result", "message", message=user("Keep the public API stable")),
    ])
    mined = reader.read_session(str(session))
    assert [action["tool_call_id"] for action in mined["actions"]] == ["call-good"]
    action = mined["actions"][0]
    assert action["result"] == "1 passed"
    assert action["followup_user_text"] == "Keep the public API stable"
    assert mined["counts"]["abandoned_entries"] == 1


def test_compaction_keeps_summary_and_marks_candidate_partial(tmp_path):
    session = tmp_path / "compact.jsonl"
    write_rows(session, [
        {"type": "session", "version": 3, "id": "session", "timestamp": "x", "cwd": "/synthetic"},
        entry("u1", None, "message", message=user("Old private task")),
        entry("old", "u1", "message", message=assistant([])),
        entry("compact", "old", "compaction", summary="Earlier task fixed parser.", firstKeptEntryId="u1", tokensBefore=100),
        entry("u2", "compact", "message", message=user("Add a regression test")),
        entry("call", "u2", "message", message=assistant([{ "type": "toolCall", "id": "c", "name": "bash", "arguments": {"command": "pytest -q"}}])),
    ])
    mined = reader.read_session(str(session))
    assert mined["compaction_summaries"] == ["Earlier task fixed parser."]
    assert mined["actions"][0]["partial"] is True


def test_malformed_unknown_duplicate_and_truncated_records_are_counted(tmp_path):
    session = tmp_path / "bad.jsonl"
    write_rows(session, [
        {"type": "session", "version": 99, "id": "session", "timestamp": "x", "cwd": "/synthetic"},
        entry("u1", None, "message", message=user("<script>hostile</script>")),
        entry("u1", None, "message", message=user("duplicate")),
        entry("x", "missing", "alien_event"),
        ["valid non-object"],
    ], trailing='{"type":"message"')
    mined = reader.read_session(str(session))
    assert mined["counts"]["unknown_version"] == 1
    assert mined["counts"]["duplicate_ids"] == 1
    assert mined["counts"]["unknown_entries"] == 1
    assert mined["counts"]["non_object_records"] == 1
    assert mined["counts"]["truncated_records"] == 1
    assert mined["counts"]["missing_parents"] == 0
    assert mined["actions"] == []


def test_session_miner_preserves_its_candidate_contract_for_pi(tmp_path):
    session = tmp_path / "pi.jsonl"
    write_rows(session, [
        {"type": "session", "version": 3, "id": "session", "timestamp": "x", "cwd": "/synthetic"},
        entry("u", None, "message", message=user("Fix the timeout")),
        entry("a", "u", "message", message=assistant([{ "type": "toolCall", "id": "tool", "name": "edit", "arguments": {"path": "app.py"}}])),
        entry("r", "a", "message", message={"role": "toolResult", "toolCallId": "tool", "content": [{"type": "text", "text": "changed"}], "isError": False}),
    ])
    candidates = miner.mine_session(str(session))
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["source"] == "pi"
    assert candidate["intent"] == "Fix the timeout"
    assert candidate["action"]["tool"] == "edit"
    assert candidate["action"]["input"] == {"path": "app.py"}
    assert candidate["partial"] is False


def test_reader_does_not_retain_reasoning_or_raw_secret_values(tmp_path):
    session = tmp_path / "private.jsonl"
    write_rows(session, [
        {"type": "session", "version": 3, "id": "session", "timestamp": "x", "cwd": "/synthetic"},
        entry("u", None, "message", message=user("Use sk-abcdefghijklmnop1234")),
        entry("a", "u", "message", message=assistant([
            {"type": "thinking", "thinking": "private provider reasoning"},
            {"type": "toolCall", "id": "tool", "name": "edit", "arguments": {"api_key": "sk-abcdefghijklmnop1234"}}])),
    ])
    action = reader.read_session(str(session))["actions"][0]
    assert "abcdefghijklmnop" not in json.dumps(action)
    assert "reasoning" not in json.dumps(action)
    assert "secret" in action["redaction_flags"]
