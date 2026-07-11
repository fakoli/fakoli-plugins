"""Tests for session-evals scripts. Synthetic fixtures only - never real
session content - but byte-faithful to the shapes verified on-disk
(Claude content blocks, Codex rollout type+payload, Cursor role/message)."""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(__file__)
SCRIPTS = os.path.join(HERE, "..", "scripts")


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


miner = _load("session_miner")
emitter = _load("eval_emit")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ------------------------------------------------------------- fixtures

def claude_session(path):
    write_jsonl(path, [
        {"type": "queue-operation", "operation": "x", "sessionId": "s",
         "timestamp": "2026-07-11T00:00:00Z", "content": "noise"},
        {"type": "user", "isSidechain": False, "timestamp": "2026-07-11T00:01:00Z",
         "cwd": "C:/proj", "gitBranch": "main",
         "message": {"content": "Fix the timeout bug in app.py"}},
        {"type": "assistant", "isSidechain": False,
         "timestamp": "2026-07-11T00:01:10Z",
         "message": {"usage": {"input_tokens": 900,
                               "cache_read_input_tokens": 4000,
                               "cache_creation_input_tokens": 100,
                               "output_tokens": 50},
                     "content": [
                         {"type": "text", "text": "Editing now."},
                         {"type": "tool_use", "name": "Edit",
                          "input": {"file_path": "app.py",
                                    "old_string": "timeout = 30",
                                    "new_string": "timeout = 45"}}]}},
        {"type": "user", "isSidechain": False, "timestamp": "2026-07-11T00:02:00Z",
         "message": {"content": "No - keep retries unchanged too"}},
        # tool_result-style user line (block content) must NOT become intent
        {"type": "user", "isSidechain": False, "timestamp": "2026-07-11T00:02:05Z",
         "message": {"content": [{"type": "tool_result",
                                  "tool_use_id": "t1", "content": "ok"}]}},
        # sidechain traffic is ignored
        {"type": "assistant", "isSidechain": True,
         "timestamp": "2026-07-11T00:02:10Z",
         "message": {"content": [{"type": "tool_use", "name": "Read",
                                  "input": {"file_path": "x"}}]}},
    ])


def codex_session(path, secret=False):
    args = {"command": "git fetch origin"}
    if secret:
        args["env"] = "OPENAI_KEY=sk-abcdefghijklmnop1234"
    write_jsonl(path, [
        {"type": "session_meta", "timestamp": "t0",
         "payload": {"cwd": "/proj", "session_id": "abc"}},
        {"type": "response_item", "timestamp": "t1",
         "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text",
                                  "text": "Plan the merge-safety work"}]}},
        {"type": "event_msg", "timestamp": "t2",
         "payload": {"type": "token_count",
                     "info": {"total_token_usage": {
                         "input_tokens": 2000, "cached_input_tokens": 6000,
                         "output_tokens": 10}}}},
        {"type": "response_item", "timestamp": "t3",
         "payload": {"type": "function_call", "name": "shell_command",
                     "arguments": json.dumps(args)}},
        {"type": "response_item", "timestamp": "t4",
         "payload": {"type": "function_call", "name": "shell_command",
                     "arguments": "{not json"}},
    ])


def cursor_session(path):
    write_jsonl(path, [
        {"role": "user", "message": {"content": [
            {"type": "text", "text": "<timestamp>x</timestamp>\n"
             "<user_query>\nreview this diff please\n</user_query>"}]}},
        {"role": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "read_file",
             "input": {"path": "main.go"}}]}},
    ])


def make_spec(**over):
    spec = {
        "suite": "merge-safety",
        "date": "2026-07-11",
        "work_class": "planning",
        "evals": [
            {"id": "stale-base", "prompt": "What first before branching?",
             "checks": [{"name": "fetch", "contains": "git fetch"}],
             "provenance": {"theme": "merge-and-base-safety"}},
            {"id": "zip-tool", "prompt": "Record ZIP 10001.",
             "tools": [{"type": "function",
                        "function": {"name": "record_zip",
                                     "parameters": {"type": "object"}}}],
             "expect_tool": {"name": "record_zip",
                             "required_args": {"zip": "10001"}},
             "checks": []},
        ],
    }
    spec.update(over)
    return spec


# ---------------------------------------------------------------- miner

def test_mine_claude(tmp_path):
    p = str(tmp_path / "c.jsonl")
    claude_session(p)
    cands = miner.mine_session(p)
    assert len(cands) == 1  # sidechain tool_use excluded
    c = cands[0]
    assert c["source"] == "claude"
    assert c["action"]["tool"] == "Edit"
    assert c["intent"] == "Fix the timeout bug in app.py"
    assert c["followup_user_text"] == "No - keep retries unchanged too"
    assert c["est_context_tokens"] == 5000
    assert c["score"] >= miner.W_TOOL_ARGS + miner.W_FOLLOWUP + miner.W_SMALL_CTX


def test_mine_codex_and_redaction(tmp_path):
    p = str(tmp_path / "rollout-x.jsonl")
    codex_session(p, secret=True)
    cands = miner.mine_session(p)
    assert len(cands) == 2
    good, bad = cands
    assert good["source"] == "codex"
    assert good["action"]["tool"] == "shell_command"
    assert good["intent"] == "Plan the merge-safety work"
    assert good["est_context_tokens"] == 8000
    assert good["work_class_guess"] == "planning"
    assert "openai-style key" in good["redaction_flags"]
    # unparseable arguments degrade to _raw, never crash
    assert "_raw" in bad["action"]["input"]


def test_mine_cursor(tmp_path):
    p = str(tmp_path / "u.jsonl")
    cursor_session(p)
    cands = miner.mine_session(p)
    assert len(cands) == 1
    assert cands[0]["source"] == "cursor"
    assert cands[0]["intent"] == "review this diff please"
    assert cands[0]["work_class_guess"] == "review"


def test_openclaw_source_label(tmp_path):
    d = tmp_path / ".openclaw" / "sessions"
    d.mkdir(parents=True)
    p = str(d / "rollout-y.jsonl")
    codex_session(p)
    assert miner.mine_session(p)[0]["source"] == "openclaw"


def test_mine_retro_and_ranking(tmp_path, capsys):
    s1 = str(tmp_path / "a.jsonl")
    claude_session(s1)
    retro = tmp_path / "retro"
    retro.mkdir()
    (retro / "session_stats.json").write_text(
        json.dumps({"sessions": [s1, str(tmp_path / "gone.jsonl")]}),
        encoding="utf-8")
    out = str(tmp_path / "cands.json")
    miner.main(["mine", "--retro", str(retro), "--out", out])
    data = json.loads(open(out, encoding="utf-8").read())
    assert data["sessions_mined"] == 1
    assert data["sessions_missing"] == [str(tmp_path / "gone.jsonl")]
    assert data["retro"] == "retro"
    assert data["candidates"][0]["id"] == "cand-000"
    scores = [c["score"] for c in data["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_mine_corpus_carries_themes(tmp_path):
    s1 = str(tmp_path / "a.jsonl")
    codex_session(s1)
    corpus = tmp_path / "findings"
    (corpus / "retro1").mkdir(parents=True)
    (corpus / "retro1" / "session_stats.json").write_text(
        json.dumps({"sessions": [s1]}), encoding="utf-8")
    (corpus / "cross_session_findings.json").write_text(json.dumps({
        "themes": [{"id": "safe-host-ops", "title": "T", "finding": "F",
                    "priority": "Now", "severity": 5,
                    "severity_label": "Critical", "extra": "dropped"}]}),
        encoding="utf-8")
    out = str(tmp_path / "cands.json")
    miner.main(["mine", "--corpus", str(corpus), "--out", out])
    data = json.loads(open(out, encoding="utf-8").read())
    assert data["themes"][0]["id"] == "safe-host-ops"
    assert "extra" not in data["themes"][0]
    assert data["candidates"]


def test_long_context_guess():
    assert miner._guess_work_class("chat", "", 200000) == "long-context"
    assert miner._guess_work_class("please review", "", 100) == "review"


# -------------------------------------------------------------- emitter

def test_validate_spec_catches_problems():
    bad = make_spec(suite="Bad Name", work_class="wizardry")
    bad["evals"][0]["checks"] = [{"name": "dup", "contains": "x",
                                  "contains_any": ["y"]}]
    bad["evals"].append({"id": "no-grading", "prompt": "p", "checks": []})
    bad["evals"].append(dict(bad["evals"][0]))  # duplicate id
    problems = "\n".join(emitter.validate_spec(bad))
    for frag in ("kebab-case", "work_class", "exactly one",
                 "needs checks or expect_tool", "duplicate id"):
        assert frag in problems
    assert emitter.validate_spec(make_spec()) == []


def test_expect_tool_requires_tools():
    spec = make_spec()
    del spec["evals"][1]["tools"]
    assert any("without tools array" in p
               for p in emitter.validate_spec(spec))


def test_emit_layout_and_no_clobber(tmp_path, capsys):
    spec_path = str(tmp_path / "spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(make_spec(), f)
    root = str(tmp_path / "eval-data")
    assert emitter.main(["emit", spec_path, "--root", root]) == 0
    d = os.path.join(root, "2026-07-11-planning-merge-safety")
    assert os.path.exists(os.path.join(d, "suite.json"))
    assert os.path.exists(os.path.join(d, "prompts", "prompt_stale-base.txt"))
    prov = json.loads(open(os.path.join(d, "provenance.json"),
                           encoding="utf-8").read())
    assert prov["stale-base"]["theme"] == "merge-and-base-safety"
    # fail closed on re-emit
    assert emitter.main(["emit", spec_path, "--root", root]) == 1
    assert emitter.main(["emit", spec_path, "--root", root, "--force"]) == 0


# ---------------------------------------------------------------- runner

def fake_post_factory(content="run git fetch origin first", tool_call=None,
                      fail_ids=()):
    calls = []

    def fake_post(base, model, messages, max_tokens, timeout,
                  tools=None, api_key=None):
        calls.append({"messages": messages, "tools": tools})
        msg = {"content": content}
        if tool_call:
            msg["tool_calls"] = [tool_call]
        return 0.01, {"choices": [{"message": msg}]}

    fake_post.calls = calls
    return fake_post


def test_run_suite_checks_and_tools():
    tool_call = {"function": {"name": "record_zip",
                              "arguments": json.dumps({"zip": "10001"})}}
    post = fake_post_factory(tool_call=tool_call)
    ev = emitter.run_suite(make_spec(), "http://x/v1", "m", post=post)
    assert ev["summary"] == {"total": 2, "passed": 2, "pass_rate": 1.0}
    assert ev["failures"] == []
    assert len(post.calls) == 2
    assert post.calls[1]["tools"]  # tools forwarded


def test_run_suite_failures_and_exitcode(tmp_path):
    tool_call = {"function": {"name": "wrong_tool", "arguments": "{}"}}
    post = fake_post_factory(content="no such phrase", tool_call=tool_call)
    ev = emitter.run_suite(make_spec(), "http://x/v1", "m", post=post)
    assert ev["summary"]["passed"] == 0
    assert {f["id"] for f in ev["failures"]} == {"stale-base", "zip-tool"}
    assert ev["results"][0]["checks"][0]["passed"] is False
    assert "wrong_tool" in ev["results"][1]["tool"]["error"]


def test_validate_tool_call_semantics():
    v = emitter.validate_tool_call
    assert v({}, {"name": "f"})["error"] == "no tool_calls in response"
    good = {"tool_calls": [{"function": {
        "name": "f", "arguments": json.dumps({"a": "1", "b": "x"})}}]}
    assert v(good, {"name": "f", "required_args": {"a": "1", "b": None}}) \
        == {"valid": True, "error": None}
    assert not v(good, {"name": "f", "required_args": {"a": "2"}})["valid"]
    assert not v(good, {"name": "f", "required_args": {"c": None}})["valid"]
    badjson = {"tool_calls": [{"function": {"name": "f", "arguments": "{"}}]}
    assert not v(badjson, {"name": "f"})["valid"]


def test_evaluate_text_checks_case_insensitive():
    res = emitter.evaluate_text_checks("Run GIT FETCH now", [
        {"name": "a", "contains": "git fetch"},
        {"name": "b", "contains_all": ["run", "now"]},
        {"name": "c", "contains_any": ["nope", "fetch"]},
        {"name": "d", "contains": "missing"},
    ])
    assert [r["passed"] for r in res] == [True, True, True, False]
