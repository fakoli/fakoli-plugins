#!/usr/bin/env python3
"""eval_emit.py - emit and run session-derived eval suites for local models.

Stdlib-only. Takes a curated spec (written during the session-evals skill's
curation step) and:

  emit  <spec.json>   write an anvil-serving-compatible eval-data directory:
                      ~/.anvil-serving/eval-data/<date>-<work_class>-<slug>/
                        suite.json        the full spec (runner input)
                        prompts/          one prompt_<id>.txt per eval
                        provenance.json   theme/session/turn back-references
  run   <suite>       execute suite.json against any OpenAI-compatible
                      endpoint and write an evidence JSON (deterministic
                      checks only - no model grades itself, no judge).

Check semantics mirror anvil-serving's benchmark engine
(evaluate_text_checks / validate_function_tool_call) so suites stay
compatible with a future `anvil-serving eval benchmark run --suite-file`.

Spec shape:
{
  "suite": "merge-safety",            # kebab-case name
  "date": "2026-07-11",               # optional; default today
  "work_class": "planning",           # anvil-serving WORK_CLASSES member
  "description": "...",
  "evals": [
    {
      "id": "stale-base-check",
      "prompt": "..."                  # or "messages": [{role, content}]
      "max_tokens": 256,               # optional, default 256
      "tools": [...],                  # optional OpenAI tools array
      "expect_tool": {                 # optional: grade the tool call
        "name": "record_weather_zip",
        "required_args": {"zip": "10001"}   # null = present non-empty string
      },
      "checks": [                      # text checks on message content
        {"name": "mentions_fetch", "contains": "git fetch"},
        {"name": "diff_shape", "contains_all": ["---", "+++"]},
        {"name": "any_fix", "contains_any": ["rebase", "merge"]}
      ],
      "context_bucket": 8192,          # optional provenance dimension
      "provenance": {"theme": "...", "session": "...", "turn_ts": "..."}
    }
  ]
}
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

DEFAULT_ROOT = os.path.expanduser("~/.anvil-serving/eval-data")

WORK_CLASSES = (
    "chat",
    "chat-fast",
    "bounded-edit",
    "multi-file-refactor",
    "planning",
    "review",
    "long-context",
)


# -------------------------------------------------------------- validate

def validate_spec(spec):
    """Return a list of problems; empty list means the spec is emittable."""
    problems = []
    suite = spec.get("suite") or ""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", suite):
        problems.append("suite must be kebab-case, got %r" % suite)
    wc = spec.get("work_class")
    if wc not in WORK_CLASSES:
        problems.append("work_class %r not in %s" % (wc, list(WORK_CLASSES)))
    date = spec.get("date")
    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        problems.append("date must be YYYY-MM-DD, got %r" % date)
    if wc in WORK_CLASSES and suite:
        # anvil-serving's profile bootstrap re-derives the work class from
        # the dir name by longest-token match; make sure our
        # <work_class>-<suite> round-trips (e.g. work_class "chat" + suite
        # "fast-triage" would read back as "chat-fast")
        slug = "%s-%s" % (wc, suite)
        derived = next((c for c in sorted(WORK_CLASSES, key=len, reverse=True)
                        if slug == c or slug.startswith(c + "-")), None)
        if derived != wc:
            problems.append(
                "suite %r makes the dir name parse as work_class %r "
                "(anvil-serving longest-token match); rename the suite"
                % (suite, derived))
    evals = spec.get("evals")
    if not isinstance(evals, list) or not evals:
        problems.append("evals must be a non-empty list")
        return problems
    seen = set()
    for i, ev in enumerate(evals):
        eid = ev.get("id") or ""
        where = "evals[%d] (%s)" % (i, eid or "no id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", eid):
            problems.append("%s: id must be kebab/snake-case" % where)
        if eid in seen:
            problems.append("%s: duplicate id" % where)
        seen.add(eid)
        if not ev.get("prompt") and not ev.get("messages"):
            problems.append("%s: needs prompt or messages" % where)
        if ev.get("prompt") and ev.get("messages"):
            problems.append("%s: prompt and messages are exclusive" % where)
        checks = ev.get("checks") or []
        if not checks and not ev.get("expect_tool"):
            problems.append("%s: needs checks or expect_tool" % where)
        for c in checks:
            if not c.get("name"):
                problems.append("%s: check without a name" % where)
            keys = {"contains", "contains_all", "contains_any"} & set(c)
            if len(keys) != 1:
                problems.append(
                    "%s: check %r needs exactly one of contains/"
                    "contains_all/contains_any" % (where, c.get("name")))
                continue
            key = keys.pop()
            val = c[key]
            # type-check now so a bad operand is a spec error, not a
            # crash mid-run (contains_all given a string would silently
            # iterate characters instead)
            if key == "contains" and not isinstance(val, str):
                problems.append("%s: check %r: contains must be a string"
                                % (where, c.get("name")))
            if key in ("contains_all", "contains_any") and (
                    not isinstance(val, list)
                    or not all(isinstance(x, str) for x in val)
                    or not val):
                problems.append("%s: check %r: %s must be a non-empty "
                                "list of strings" % (where, c.get("name"), key))
        et = ev.get("expect_tool")
        if et is not None:
            if not et.get("name"):
                problems.append("%s: expect_tool.name required" % where)
            if not ev.get("tools"):
                problems.append("%s: expect_tool without tools array - the "
                                "model can't call what isn't offered" % where)
            for k, want in (et.get("required_args") or {}).items():
                # anvil compares against the raw expected value, so a
                # non-string (e.g. 10001 vs "10001") can never match
                if want is not None and not isinstance(want, str):
                    problems.append("%s: required_args[%r] must be a string "
                                    "or null" % (where, k))
    return problems


# ------------------------------------------------------------------ emit

def cmd_emit(args):
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    problems = validate_spec(spec)
    if problems:
        for p in problems:
            print("spec error: %s" % p, file=sys.stderr)
        return 1

    date = spec.get("date") or datetime.date.today().isoformat()
    dirname = "%s-%s-%s" % (date, spec["work_class"], spec["suite"])
    out_dir = os.path.join(os.path.expanduser(args.root), dirname)
    if os.path.exists(out_dir):
        if not args.force:
            # fail closed: an eval dir is measurement evidence; never clobber
            print("refusing to overwrite %s (pass --force to replace)"
                  % out_dir, file=sys.stderr)
            return 1
        # replace wholesale so prompts of since-removed evals don't linger
        shutil.rmtree(out_dir)

    prompts_dir = os.path.join(out_dir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    spec.setdefault("date", date)
    with open(os.path.join(out_dir, "suite.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
        f.write("\n")
    provenance = {}
    for ev in spec["evals"]:
        text = ev.get("prompt") or json.dumps(ev.get("messages"), indent=2,
                                              ensure_ascii=False)
        with open(os.path.join(prompts_dir, "prompt_%s.txt" % ev["id"]),
                  "w", encoding="utf-8") as f:
            f.write(text + "\n")
        provenance[ev["id"]] = ev.get("provenance") or {}
    with open(os.path.join(out_dir, "provenance.json"), "w",
              encoding="utf-8") as f:
        json.dump(provenance, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("emitted %d evals -> %s" % (len(spec["evals"]), out_dir))
    return 0


# ------------------------------------------------------------------- run

def evaluate_text_checks(content, checks):
    """Mirror of anvil_serving.benchmark.evaluate_text_checks."""
    normalized = (content or "").lower()
    results = []
    for check in checks:
        ok = True
        if "contains" in check:
            ok = check["contains"].lower() in normalized
        elif "contains_all" in check:
            ok = all(x.lower() in normalized for x in check["contains_all"])
        elif "contains_any" in check:
            ok = any(x.lower() in normalized for x in check["contains_any"])
        results.append({"name": check["name"], "passed": ok})
    return results


def validate_tool_call(message, expect):
    """Faithful mirror of anvil_serving.benchmark.validate_function_tool_call.

    Semantics must not drift (a suite has to grade identically here and in
    a future anvil-serving --suite-file run): every required arg must be a
    NON-EMPTY STRING even when its expected value is null (presence-only);
    a dict-typed `arguments` from vLLM/SGLang tool parsers is accepted
    as-is; expected values compare against value.strip().
    """
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not tool_calls:
        return {"valid": False, "error": "response did not include tool_calls"}
    first = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
    fn = first.get("function") if isinstance(first, dict) else {}
    if not isinstance(fn, dict):
        return {"valid": False, "error": "tool_call missing function object"}
    if fn.get("name") != expect["name"]:
        return {"valid": False,
                "error": "wrong function name: %r" % fn.get("name")}
    raw = fn.get("arguments")
    try:
        got = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, ValueError) as exc:
        return {"valid": False,
                "error": "arguments are not valid JSON: %s" % exc}
    if not isinstance(got, dict):
        return {"valid": False, "error": "arguments are not a JSON object"}
    for key, want in (expect.get("required_args") or {}).items():
        value = got.get(key)
        if not isinstance(value, str) or not value.strip():
            return {"valid": False,
                    "error": "missing required string argument: %s" % key}
        if want is not None and value.strip() != want:
            return {"valid": False,
                    "error": "wrong argument %s: %r" % (key, value)}
    return {"valid": True, "error": None}


def _post_chat(base, model, messages, max_tokens, timeout, tools=None,
               api_key=None):
    """One OpenAI-compatible chat call; deterministic settings (temp 0)."""
    url = base.rstrip("/") + "/chat/completions"
    body = {"model": model, "messages": messages, "max_tokens": max_tokens,
            "temperature": 0.0, "stream": False}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return time.time() - t0, data


def run_suite(spec, base_url, model, timeout=120, api_key=None, post=None):
    """Execute every eval; return the evidence dict. `post` is the seam."""
    if not spec.get("evals"):
        raise ValueError("spec has no evals (validate_spec should gate this)")
    post = post or _post_chat
    results = []
    failures = []
    for ev in spec["evals"]:
        messages = ev.get("messages") or [
            {"role": "user", "content": ev["prompt"]}]
        row = {"id": ev["id"], "checks": [], "tool": None, "latency_s": None,
               "passed": False, "error": None}
        try:
            latency, data = post(base_url, model, messages,
                                 ev.get("max_tokens", 256), timeout,
                                 tools=ev.get("tools"), api_key=api_key)
            row["latency_s"] = round(latency, 3)
            choices = data.get("choices") if isinstance(data, dict) else None
            choice = (choices or [{}])[0]
            msg = choice.get("message") if isinstance(choice, dict) else None
            msg = msg if isinstance(msg, dict) else {}
            content = msg.get("content")
            # anvil _message_text parity: block-list content grades as ""
            # rather than crashing on list.lower()
            content = content if isinstance(content, str) else ""
            row["checks"] = evaluate_text_checks(content, ev.get("checks") or [])
            ok = all(c["passed"] for c in row["checks"])
            if ev.get("expect_tool"):
                row["tool"] = validate_tool_call(msg, ev["expect_tool"])
                ok = ok and row["tool"]["valid"]
            row["passed"] = ok
        except (urllib.error.URLError, OSError, ValueError, KeyError,
                TypeError, AttributeError, IndexError) as e:
            # a malformed response from one local serve must cost one eval,
            # never the whole evidence run
            row["error"] = "%s: %s" % (type(e).__name__, e)
        if not row["passed"]:
            failures.append({"id": ev["id"],
                             "error": row["error"] or "checks failed"})
        results.append(row)

    passed = sum(1 for r in results if r["passed"])
    return {
        "tool": "session-evals/eval_emit run",
        "suite": spec["suite"],
        "work_class": spec["work_class"],
        "base_url": base_url,
        "model": model,
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
        "results": results,
        "failures": failures,
        "summary": {"total": len(results), "passed": passed,
                    "pass_rate": round(passed / len(results), 4)},
    }


def cmd_run(args):
    suite_path = args.suite
    if os.path.isdir(suite_path):
        suite_path = os.path.join(suite_path, "suite.json")
    with open(suite_path, encoding="utf-8") as f:
        spec = json.load(f)
    problems = validate_spec(spec)
    if problems:
        for p in problems:
            print("spec error: %s" % p, file=sys.stderr)
        return 1
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    evidence = run_suite(spec, args.base_url, args.model,
                         timeout=args.timeout, api_key=api_key)
    text = json.dumps(evidence, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    s = evidence["summary"]
    print("%s: %d/%d passed (%.0f%%) against %s"
          % (spec["suite"], s["passed"], s["total"], 100 * s["pass_rate"],
             args.model), file=sys.stderr)
    return 0 if s["passed"] == s["total"] else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    se = sub.add_parser("emit", help="write an eval-data dir from a spec")
    se.add_argument("spec", help="curated spec JSON")
    se.add_argument("--root", default=DEFAULT_ROOT,
                    help="eval-data root (default %(default)s)")
    se.add_argument("--force", action="store_true",
                    help="replace an existing suite dir")
    se.set_defaults(func=cmd_emit)

    sr = sub.add_parser("run", help="run a suite against an endpoint")
    sr.add_argument("suite", help="suite dir or suite.json")
    sr.add_argument("--base-url", required=True,
                    help="OpenAI-compatible base, e.g. http://127.0.0.1:30001/v1")
    sr.add_argument("--model", required=True, help="served model name")
    sr.add_argument("--timeout", type=int, default=120)
    sr.add_argument("--api-key-env", default="",
                    help="env var holding a bearer key (never pass the key "
                    "itself on the command line)")
    sr.add_argument("--out", help="write evidence JSON here")
    sr.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
