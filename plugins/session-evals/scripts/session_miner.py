#!/usr/bin/env python3
"""session_miner.py - mine coding-agent sessions into eval candidates.

Stdlib-only. Reads local session logs from four sources and emits ranked
eval-candidate records for human/Claude curation (see the session-evals
skill). Never sends anything anywhere; output is a local JSON file.

Sources (three parser variants):
  claude   ~/.claude/projects/**/*.jsonl        (Anthropic content blocks)
  codex    ~/.codex/sessions/**/*.jsonl          (rollout: type+payload)
  openclaw <WSL>/.openclaw/agents/*/agent/codex-home/sessions/**/*.jsonl
           (codex rollout format - OpenClaw embeds a codex agent)
  cursor   ~/.cursor/projects/*/agent-transcripts/*/*.jsonl (role+message)

Commands:
  list [substr]                     enumerate sessions across sources
  mine <session.jsonl ...>          mine explicit session files
  mine --retro <retro-dir>          mine sessions listed in a session-retro
                                    output dir (session_stats.json)
  mine --corpus <corpus-dir>        mine every retro dir in a findings corpus
                                    and carry its failure themes alongside

Formats drift between agent releases; parsing is tolerant by design -
unknown types are skipped, malformed lines are counted, never fatal.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

CLAUDE_ROOT = os.path.expanduser("~/.claude/projects")
CODEX_ROOT = os.path.expanduser("~/.codex/sessions")
CURSOR_ROOT = os.path.expanduser("~/.cursor/projects")

# Ranking weights: transparent and additive so the curator can see why a
# candidate scored what it did (mirrors the "judgment stays with the
# curator" split - the script only orders the reading list).
W_TOOL_ARGS = 2      # structured tool call with parseable args
W_FOLLOWUP = 3       # a human turn follows - possible correction signal
W_DIFF = 2           # action carries a diff/patch (verifiable shape)
W_SMALL_CTX = 1      # fits a local-model context bucket without surgery

# anvil-serving's canonical taxonomy (router/classify.py WORK_CLASSES).
WORK_CLASSES = (
    "chat",
    "chat-fast",
    "bounded-edit",
    "multi-file-refactor",
    "planning",
    "review",
    "long-context",
)

# est_context_tokens above this can't fit the largest local bucket (32k)
# without curation surgery; used for ranking and the long-context guess.
MAX_LOCAL_CTX = 32768

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9-]{16,}"), "openai-style key"),
    (re.compile(r"(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}"), "github token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws access key"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "slack token"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{20,}", re.I), "bearer token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
]

CLIP = 2000  # max chars kept per captured text field


# ---------------------------------------------------------------- helpers

def _jsonl(path):
    """Yield parsed objects from a JSONL file; skip lines that don't parse."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError as e:
        print("warn: cannot read %s: %s" % (path, e), file=sys.stderr)


def _text(content):
    """Flatten Anthropic/Codex content (str or block list) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                t = c.get("text") or c.get("input_text") or ""
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(c, str):
                parts.append(c)
        return "\n".join(parts)
    return ""


def _clip(s, n=CLIP):
    s = s or ""
    return s if len(s) <= n else s[:n] + "...[clipped %d chars]" % (len(s) - n)


def _redaction_flags(*texts):
    flags = set()
    for t in texts:
        if not t:
            continue
        for pat, label in SECRET_PATTERNS:
            if pat.search(t):
                flags.add(label)
    return sorted(flags)


def _guess_work_class(intent, action_text, est_ctx):
    """Cheap keyword prior; the curator owns the final assignment."""
    if est_ctx and est_ctx > MAX_LOCAL_CTX:
        return "long-context"
    blob = ((intent or "") + " " + (action_text or "")).lower()
    if re.search(r"\breview\b|\bcritique\b|\baudit\b", blob):
        return "review"
    if re.search(r"\bplan\b|\broadmap\b|\bprd\b|\bbreak.{0,8}down\b", blob):
        return "planning"
    if re.search(r"^(---|\+\+\+|@@)", action_text or "", re.M):
        return "bounded-edit"
    if re.search(r"\brefactor\b", blob):
        return "multi-file-refactor"
    if re.search(r"\bedit\b|\bfix\b|\bpatch\b|\bdiff\b", blob):
        return "bounded-edit"
    return "chat"


def _mk_candidate(source, session_path, turn_ts, intent, action, est_ctx,
                  followup=None):
    """Assemble one candidate record + its transparent ranking score."""
    action_text = action.get("text") or json.dumps(
        action.get("input") or {}, ensure_ascii=False)
    score = 0
    if action.get("kind") == "tool_call" and action.get("input") is not None:
        score += W_TOOL_ARGS
    if followup:
        score += W_FOLLOWUP
    if re.search(r"^(---|\+\+\+|@@)", action_text or "", re.M):
        score += W_DIFF
    if est_ctx and est_ctx <= MAX_LOCAL_CTX:
        score += W_SMALL_CTX
    return {
        "source": source,
        "session": session_path,
        "turn_ts": turn_ts,
        "intent": _clip(intent),
        "action": {
            "kind": action.get("kind"),
            "tool": action.get("tool"),
            "input": action.get("input"),
            "text": _clip(action.get("text") or ""),
        },
        "followup_user_text": _clip(followup or "", 500) or None,
        "est_context_tokens": est_ctx,
        "work_class_guess": _guess_work_class(intent, action_text, est_ctx),
        "redaction_flags": _redaction_flags(intent, action_text, followup),
        "score": score,
    }


# ---------------------------------------------------------------- parsers

def _is_codex(path):
    for d in _jsonl(path):
        return d.get("type") in {"session_meta", "turn_context",
                                 "response_item", "event_msg"}
    return False


def _is_cursor(path):
    for d in _jsonl(path):
        return set(d.keys()) <= {"role", "message"} and "role" in d
    return False


def mine_claude(path):
    """Claude Code JSONL: assistant tool_use blocks anchored by user turns."""
    cands = []
    intent = None
    ctx = None
    pending = []  # candidates awaiting the next human turn (followup signal)
    for d in _jsonl(path):
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        ts = d.get("timestamp")
        if d.get("type") == "user" and not d.get("isSidechain"):
            txt = _text(m.get("content"))
            # Real human turns are plain text; tool_result / harness noise
            # arrives as blocks or XML-ish payloads (same filter as
            # session-retro's session_stats.py).
            if isinstance(m.get("content"), str) and txt.strip() \
                    and not txt.lstrip().startswith("<"):
                for c in pending:
                    c["followup_user_text"] = _clip(txt, 500)
                    c["score"] += W_FOLLOWUP
                pending = []
                intent = txt
        elif d.get("type") == "assistant" and not d.get("isSidechain"):
            u = m.get("usage") or {}
            got = sum(int(u.get(k) or 0) for k in (
                "input_tokens", "cache_read_input_tokens",
                "cache_creation_input_tokens"))
            ctx = got or ctx
            for c in (m.get("content") or []):
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    cand = _mk_candidate(
                        "claude", path, ts, intent,
                        {"kind": "tool_call", "tool": c.get("name"),
                         "input": c.get("input")},
                        ctx)
                    cands.append(cand)
                    pending.append(cand)
    return cands


def mine_codex(path, source="codex"):
    """Codex rollout JSONL (also OpenClaw's embedded agent)."""
    cands = []
    intent = None
    ctx = None
    pending = []
    for d in _jsonl(path):
        payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        ts = d.get("timestamp")
        ptype = payload.get("type")
        if ptype == "message" and payload.get("role") == "user":
            txt = _text(payload.get("content")).strip()
            if txt and not txt.lstrip().startswith("<"):
                for c in pending:
                    c["followup_user_text"] = _clip(txt, 500)
                    c["score"] += W_FOLLOWUP
                pending = []
                intent = txt
        elif ptype == "function_call":
            try:
                args = json.loads(payload.get("arguments") or "{}")
            except (json.JSONDecodeError, ValueError):
                args = {"_raw": _clip(str(payload.get("arguments")), 500)}
            cand = _mk_candidate(
                source, path, ts, intent,
                {"kind": "tool_call", "tool": payload.get("name"),
                 "input": args},
                ctx)
            cands.append(cand)
            pending.append(cand)
        elif ptype == "token_count":
            info = payload.get("info") or {}
            total = (info.get("total_token_usage") or {})
            got = int(total.get("input_tokens") or 0) \
                + int(total.get("cached_input_tokens") or 0)
            ctx = got or ctx
    return cands


def mine_cursor(path):
    """Cursor CLI agent transcript: role/message JSONL, Anthropic-ish blocks."""
    cands = []
    intent = None
    chars = 0
    pending = []
    for d in _jsonl(path):
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        content = m.get("content")
        chars += len(json.dumps(content, ensure_ascii=False)) if content else 0
        est_ctx = chars // 4  # no usage records; chars/4 approximation
        if d.get("role") == "user":
            txt = _text(content).strip()
            # Cursor wraps the real query in <user_query> tags.
            q = re.search(r"<user_query>\s*(.*?)\s*</user_query>", txt, re.S)
            txt = q.group(1) if q else txt
            if txt and not txt.lstrip().startswith("<"):
                for c in pending:
                    c["followup_user_text"] = _clip(txt, 500)
                    c["score"] += W_FOLLOWUP
                pending = []
                intent = txt
        elif d.get("role") == "assistant":
            for c in (content or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    cand = _mk_candidate(
                        "cursor", path, None, intent,
                        {"kind": "tool_call", "tool": c.get("name"),
                         "input": c.get("input")},
                        est_ctx)
                    cands.append(cand)
                    pending.append(cand)
    return cands


def mine_session(path):
    if _is_cursor(path):
        return mine_cursor(path)
    if _is_codex(path):
        src = "openclaw" if ".openclaw" in path.replace("\\", "/") else "codex"
        return mine_codex(path, src)
    return mine_claude(path)


# ------------------------------------------------------------- discovery

def _wsl_openclaw_roots():
    """OpenClaw session roots reachable from Windows via \\\\wsl$ UNC paths.

    Env override SESSION_EVALS_OPENCLAW_ROOTS (os.pathsep-separated dirs)
    always wins; otherwise enumerate WSL distros. Native Linux/macOS homes
    are covered by the ~/.openclaw default below.
    """
    env = os.environ.get("SESSION_EVALS_OPENCLAW_ROOTS")
    if env:
        return [p for p in env.split(os.pathsep) if p]
    roots = [os.path.expanduser("~/.openclaw")]
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["wsl.exe", "-l", "-q"], capture_output=True, timeout=10
            ).stdout.decode("utf-16-le", errors="ignore")
            for distro in out.split():
                distro = distro.strip()
                if distro:
                    roots.append(r"\\wsl$" + "\\" + distro + r"\home")
        except (OSError, subprocess.SubprocessError):
            pass
    return roots


def discover_sessions():
    """Return [(source, path)] for every session file found on this machine."""
    found = []
    for p in glob.glob(os.path.join(CLAUDE_ROOT, "**", "*.jsonl"),
                       recursive=True):
        found.append(("claude", p))
    for p in glob.glob(os.path.join(CODEX_ROOT, "**", "*.jsonl"),
                       recursive=True):
        found.append(("codex", p))
    for p in glob.glob(os.path.join(CURSOR_ROOT, "*", "agent-transcripts",
                                    "*", "*.jsonl")):
        found.append(("cursor", p))
    # OpenClaw embeds a codex agent; its rollouts live at a known depth so
    # the glob stays anchored (a recursive ** across a WSL home is minutes).
    for root in _wsl_openclaw_roots():
        if root.rstrip("\\/").endswith("home"):
            root = os.path.join(root, "*", ".openclaw")
        pat = os.path.join(root, "agents", "*", "agent", "codex-home",
                           "sessions", "**", "*.jsonl")
        try:
            for p in glob.glob(pat, recursive=True):
                found.append(("openclaw", p))
        except OSError:
            continue
    return found


# ---------------------------------------------------------------- inputs

def sessions_from_retro(retro_dir):
    """Session paths recorded by a session-retro run (session_stats.json)."""
    stats_path = os.path.join(retro_dir, "session_stats.json")
    with open(stats_path, encoding="utf-8") as f:
        stats = json.load(f)
    paths = stats.get("sessions") or []
    if not paths:
        raise SystemExit("no 'sessions' list in %s" % stats_path)
    return [os.path.normpath(p) for p in paths]


def corpus_inputs(corpus_dir):
    """(retro dirs, themes) from a post-session-findings corpus."""
    themes = []
    cf = os.path.join(corpus_dir, "cross_session_findings.json")
    if os.path.exists(cf):
        with open(cf, encoding="utf-8") as f:
            data = json.load(f)
        for t in data.get("themes") or []:
            themes.append({k: t.get(k) for k in
                           ("id", "title", "finding", "priority",
                            "severity", "severity_label")})
    retro_dirs = sorted(
        os.path.dirname(p) for p in
        glob.glob(os.path.join(corpus_dir, "*", "session_stats.json")))
    return retro_dirs, themes


# -------------------------------------------------------------- commands

def cmd_list(args):
    rows = []
    for source, p in discover_sessions():
        if args.substr and args.substr.lower() not in p.lower():
            continue
        try:
            mtime = os.path.getmtime(p)
            size = os.path.getsize(p)
        except OSError:
            continue
        rows.append((mtime, source, size, p))
    rows.sort()
    for mtime, source, size, p in rows:
        import datetime
        d = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print("%s  %-8s %8dKB  %s" % (d, source, size // 1024, p))
    if not rows:
        print("no sessions found", file=sys.stderr)


def cmd_mine(args):
    sessions = list(args.sessions)
    themes = []
    retro_label = None
    if args.retro:
        sessions += sessions_from_retro(args.retro)
        retro_label = os.path.basename(os.path.normpath(args.retro))
    if args.corpus:
        retro_dirs, themes = corpus_inputs(args.corpus)
        for rd in retro_dirs:
            try:
                sessions += sessions_from_retro(rd)
            except (OSError, SystemExit) as e:
                print("warn: skipping %s: %s" % (rd, e), file=sys.stderr)
    if not sessions:
        raise SystemExit("nothing to mine: pass session files, --retro or --corpus")

    candidates = []
    missing = []
    seen = set()
    for sp in sessions:
        if sp in seen:
            continue
        seen.add(sp)
        if not os.path.exists(sp):
            missing.append(sp)
            continue
        candidates.extend(mine_session(sp))

    candidates.sort(key=lambda c: -c["score"])
    if args.max_candidates:
        candidates = candidates[:args.max_candidates]
    for i, c in enumerate(candidates):
        c["id"] = "cand-%03d" % i

    out = {
        "tool": "session-evals/session_miner",
        "sessions_mined": len(seen) - len(missing),
        "sessions_missing": missing,
        "retro": retro_label,
        "themes": themes,
        "work_classes": list(WORK_CLASSES),
        "candidates": candidates,
    }
    text = json.dumps(out, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("wrote %d candidates (%d sessions) -> %s"
              % (len(candidates), len(seen) - len(missing), args.out))
        if missing:
            print("warn: %d session files missing (moved/deleted?)"
                  % len(missing), file=sys.stderr)
    else:
        print(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sl = sub.add_parser("list", help="enumerate sessions across sources")
    sl.add_argument("substr", nargs="?", default="",
                    help="filter paths containing this substring")
    sl.set_defaults(func=cmd_list)

    sm = sub.add_parser("mine", help="mine sessions into eval candidates")
    sm.add_argument("sessions", nargs="*", help="session JSONL files")
    sm.add_argument("--retro", help="session-retro output dir "
                    "(reads its session_stats.json sessions list)")
    sm.add_argument("--corpus", help="post-session-findings corpus dir "
                    "(mines every retro; carries cross-session themes)")
    sm.add_argument("--max-candidates", type=int, default=200,
                    help="keep top N ranked candidates (default 200)")
    sm.add_argument("--out", help="write JSON here instead of stdout")
    sm.set_defaults(func=cmd_mine)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
