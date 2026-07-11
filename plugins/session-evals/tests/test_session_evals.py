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


def test_mine_retro_and_ranking(tmp_path):
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


def test_work_class_guess_ignores_session_context():
    # session-cumulative context must NOT force long-context (it exceeds
    # any local bucket in every real Claude session)
    assert miner._guess_work_class("chat about x", "", 200000) == "chat"
    assert miner._guess_work_class("please review", "", 100) == "review"


def test_diff_in_tool_input_scores_and_classifies():
    patch = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x\n+y\n"
    c = miner._mk_candidate(
        "codex", "s.jsonl", "t", "apply this",
        {"kind": "tool_call", "tool": "apply_patch",
         "input": {"patch": patch}}, 1000)
    assert c["score"] >= miner.W_TOOL_ARGS + miner.W_DIFF + miner.W_SMALL_CTX
    assert c["work_class_guess"] == "bounded-edit"


def test_jsonl_tolerates_non_dict_lines_and_bom(tmp_path):
    p = tmp_path / "weird.jsonl"
    p.write_bytes(
        b'\xef\xbb\xbf{"type": "session_meta", "payload": {"cwd": "/x"}}\n'
        b"42\n"
        b'"bare string"\n'
        b"[1, 2]\n"
        b"null\n"
        b"{not json\n"
        b'{"type": "response_item", "payload": {"type": "function_call", '
        b'"name": "t", "arguments": "{}"}}\n')
    rows = list(miner._jsonl(str(p)))
    assert [r.get("type") for r in rows] == ["session_meta", "response_item"]
    # BOM must not hide the first record from format detection
    cands = miner.mine_session(str(p))
    assert len(cands) == 1 and cands[0]["source"] == "codex"


def test_followup_secret_is_flagged(tmp_path):
    p = str(tmp_path / "c.jsonl")
    write_jsonl(p, [
        {"type": "user", "isSidechain": False,
         "message": {"content": "do the thing"}},
        {"type": "assistant", "isSidechain": False,
         "message": {"usage": {"input_tokens": 10},
                     "content": [{"type": "tool_use", "name": "Bash",
                                  "input": {"command": "ls"}}]}},
        {"type": "user", "isSidechain": False,
         "message": {"content": "no, use key sk-abcdefghijklmnop1234"}},
    ])
    c = miner.mine_session(p)[0]
    assert "openai-style key" in c["redaction_flags"]


def test_resolve_session_path_archived(tmp_path, monkeypatch):
    archive = tmp_path / "archived_sessions"
    archive.mkdir()
    (archive / "rollout-z.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(miner, "CODEX_ARCHIVE", str(archive))
    stale = str(tmp_path / "sessions" / "2026" / "rollout-z.jsonl")
    assert miner.resolve_session_path(stale) == \
        str(archive / "rollout-z.jsonl")
    assert miner.resolve_session_path(str(tmp_path / "gone.jsonl")) is None


def test_work_classes_in_sync():
    # duplicated on purpose (stdlib-only, no cross-script import under the
    # importlib test loader); this guard is what keeps them from drifting
    assert tuple(miner.WORK_CLASSES) == tuple(emitter.WORK_CLASSES)


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


def test_emit_layout_and_no_clobber(tmp_path):
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


def test_validate_tool_call_anvil_parity():
    """Semantics must match anvil_serving.benchmark.validate_function_tool_call
    exactly - a suite has to grade identically here and there."""
    v = emitter.validate_tool_call
    assert "tool_calls" in v({}, {"name": "f"})["error"]
    good = {"tool_calls": [{"function": {
        "name": "f", "arguments": json.dumps({"a": "1", "b": "x"})}}]}
    assert v(good, {"name": "f", "required_args": {"a": "1", "b": None}}) \
        == {"valid": True, "error": None}
    assert not v(good, {"name": "f", "required_args": {"a": "2"}})["valid"]
    assert not v(good, {"name": "f", "required_args": {"c": None}})["valid"]
    badjson = {"tool_calls": [{"function": {"name": "f", "arguments": "{"}}]}
    assert not v(badjson, {"name": "f"})["valid"]
    # anvil parity: a non-string arg value is INVALID even if it stringifies
    intarg = {"tool_calls": [{"function": {
        "name": "f", "arguments": json.dumps({"zip": 98101})}}]}
    assert not v(intarg, {"name": "f", "required_args": {"zip": "98101"}})["valid"]
    # anvil parity: presence-only (null) still demands a non-empty string
    empty = {"tool_calls": [{"function": {
        "name": "f", "arguments": json.dumps({"path": ""})}}]}
    assert not v(empty, {"name": "f", "required_args": {"path": None}})["valid"]
    # anvil parity: dict-typed arguments (vLLM/SGLang parsers) accepted as-is
    dictargs = {"tool_calls": [{"function": {
        "name": "f", "arguments": {"a": "1"}}}]}
    assert v(dictargs, {"name": "f", "required_args": {"a": "1"}})["valid"]
    # non-object arguments graded invalid, not crashed
    nonobj = {"tool_calls": [{"function": {"name": "f", "arguments": "[1]"}}]}
    assert not v(nonobj, {"name": "f"})["valid"]


def test_validate_spec_dir_name_roundtrip():
    spec = make_spec(work_class="chat", suite="fast-triage")
    assert any("chat-fast" in p for p in emitter.validate_spec(spec))
    assert emitter.validate_spec(make_spec(work_class="chat",
                                           suite="triage")) == []


def test_validate_spec_check_operand_types():
    spec = make_spec()
    spec["evals"][0]["checks"] = [
        {"name": "n1", "contains": 123},
        {"name": "n2", "contains_all": "notalist"},
        {"name": "n3", "contains_any": []},
    ]
    problems = "\n".join(emitter.validate_spec(spec))
    assert "contains must be a string" in problems
    assert "contains_all must be a non-empty list" in problems
    assert "contains_any must be a non-empty list" in problems


def test_force_reemit_removes_stale_prompts(tmp_path):
    spec = make_spec()
    spec_path = str(tmp_path / "spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    root = str(tmp_path / "eval-data")
    assert emitter.main(["emit", spec_path, "--root", root]) == 0
    spec["evals"] = [spec["evals"][0]]  # drop zip-tool
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    assert emitter.main(["emit", spec_path, "--root", root, "--force"]) == 0
    d = os.path.join(root, "2026-07-11-planning-merge-safety", "prompts")
    assert sorted(os.listdir(d)) == ["prompt_stale-base.txt"]


def test_evaluate_text_checks_case_insensitive():
    res = emitter.evaluate_text_checks("Run GIT FETCH now", [
        {"name": "a", "contains": "git fetch"},
        {"name": "b", "contains_all": ["run", "now"]},
        {"name": "c", "contains_any": ["nope", "fetch"]},
        {"name": "d", "contains": "missing"},
    ])
    assert [r["passed"] for r in res] == [True, True, True, False]
