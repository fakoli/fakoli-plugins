#!/usr/bin/env python3
"""session_stats.py — extract metrics from Claude Code or Codex session JSONL logs.

Deterministic data work for the session-retro skill. Three modes:

    session_stats.py list [substr]            # browse sessions (date/branch/topic)
    session_stats.py find <keyword> [substr]  # sessions mentioning a keyword
    session_stats.py stats <a.jsonl> [b...]   # JSON aggregates (combined if >1)
    session_stats.py report <a.jsonl> [b...]  # markdown: tables + ASCII charts
    session_stats.py html <a.jsonl> [b...] [--narrative note.md]  # interactive single-page site

`list`/`find` are for DISCOVERY — locate any session (not just the current one) by
project, branch, first-message topic, or content (a PR number, feature, filename).
Then pass its path to `stats`/`report`. `substr` filters by the project/worktree path.

The narrative (interaction analysis, recommendations) is the model's job — this
script fills the deterministic sections and hands back the user-turn list.

Reads only local ~/.claude and ~/.codex logs. No network, no third-party deps
(stdlib only).
"""
import json, os, re, sys, glob
from collections import Counter, defaultdict
from datetime import datetime

PROJECTS = os.path.expanduser("~/.claude/projects")
CODEX_SESSIONS = os.path.expanduser("~/.codex/sessions")
CODEX_TOP_TYPES = {"session_meta", "turn_context", "response_item", "event_msg"}


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") in ("text", "input_text", "output_text"))
    return ""


def _jsonl(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _is_codex(path):
    for d in _jsonl(path):
        if d.get("type") in CODEX_TOP_TYPES:
            return True
        if d.get("message"):
            return False
    return False


def _codex_kind(text, agent_type=""):
    t = (text or "").lower()
    if "adversarial" in t:
        return "review"
    if "critic" in t or "review" in t or agent_type == "explorer":
        return "review"
    if "fix" in t or "apply" in t:
        return "apply-fixes"
    if "implement" in t or "working in" in t:
        return "task-cycle"
    return "other"


def _codex_prompt_summary(text):
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    return clean[:90]


def _wf_ref(inp):
    """Canonical dynamic-workflow name from a Workflow tool_use input."""
    if inp.get("name"):
        base = inp["name"]
    elif inp.get("scriptPath"):
        base = os.path.basename(inp["scriptPath"])
    elif inp.get("script"):
        mm = re.search(r"name:\s*['\"]([^'\"]+)['\"]", inp["script"])
        base = mm.group(1) if mm else "inline"
    else:
        base = "?"
    base = base.replace("inline:", "")
    base = re.sub(r"-wf_[a-z0-9-]+\.(js|json)$", "", base)
    return re.sub(r"\.(js|json)$", "", base)


def scan_agent_types(session_jsonl):
    """agentType counts from the session's workflow subagent meta files."""
    base = session_jsonl[:-6] if session_jsonl.endswith(".jsonl") else session_jsonl
    c = Counter()
    for mf in glob.glob(f"{base}/subagents/workflows/wf_*/agent-*.meta.json"):
        try:
            c[json.load(open(mf)).get("agentType", "?")] += 1
        except Exception:
            pass
    return c


def parse(path):
    """Aggregate one session JSONL into a stats dict."""
    if _is_codex(path):
        return parse_codex(path)
    return parse_claude(path)


def _base_stats(path, runtime):
    return dict(path=path, runtime=runtime, out=0, inp=0, cc=0, cr=0, asst=0,
                user_turns=[], tools=Counter(), workflows=[], ts_first=None,
                ts_last=None, cwd=None, branch=None, skills=Counter(),
                agent_types=Counter(), wf_named=Counter(), events=[], wf_ts=[],
                session_id=None, id=None, parent_thread_id=None,
                codex_is_subagent=False, duration_ms=0, prompt_summary="")


def parse_claude(path):
    """Aggregate one Claude Code session JSONL into a stats dict."""
    s = _base_stats(path, "claude")
    for d in _jsonl(path):
        ts = d.get("timestamp")
        if ts:
            s["ts_first"] = s["ts_first"] or ts
            s["ts_last"] = ts
        if d.get("cwd") and not s["cwd"]:
            s["cwd"] = d["cwd"]
            s["branch"] = d.get("gitBranch")
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        if d.get("type") == "assistant":
            u = m.get("usage") or {}
            s["out"] += u.get("output_tokens", 0)
            s["inp"] += u.get("input_tokens", 0)
            s["cc"] += u.get("cache_creation_input_tokens", 0)
            s["cr"] += u.get("cache_read_input_tokens", 0)
            s["asst"] += 1
            if ts:
                s["events"].append((ts, u.get("output_tokens", 0)))
            for c in (m.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    nm = c.get("name", "?")
                    s["tools"][nm] += 1
                    inp = c.get("input") or {}
                    if nm == "Skill":
                        s["skills"][inp.get("skill", "?")] += 1
                    elif nm == "Agent":
                        s["agent_types"][inp.get("subagent_type") or "general-purpose"] += 1
                    elif nm == "Workflow":
                        s["wf_named"][_wf_ref(inp)] += 1
                        if ts:
                            s["wf_ts"].append(ts)
        elif d.get("type") == "user":
            txt = _text(m.get("content"))
            if "<usage>" in txt or "<task-notification>" in txt:
                g = lambda p: (re.search(p, txt, re.S) or [None, None])[1] \
                    if re.search(p, txt, re.S) else None
                s["workflows"].append(dict(
                    summary=(g(r"<summary>(.*?)</summary>") or "").strip()[:90],
                    agents=int(g(r"<agent_count>(\d+)") or 0),
                    tokens=int(g(r"<subagent_tokens>(\d+)") or 0),
                    tool_uses=int(g(r"<tool_uses>(\d+)") or 0),
                    ms=int(g(r"<duration_ms>(\d+)") or 0),
                ))
            elif isinstance(m.get("content"), str) and not m["content"].lstrip().startswith("<"):
                s["user_turns"].append(m["content"].replace("\n", " ").strip()[:140])
    return s


def parse_codex(path):
    """Aggregate one Codex rollout JSONL into the same stats shape as Claude."""
    s = _base_stats(path, "codex")
    token_totals = []
    first_user = None
    for d in _jsonl(path):
        ts = d.get("timestamp")
        if ts:
            s["ts_first"] = s["ts_first"] or ts
            s["ts_last"] = ts
        top_type = d.get("type")
        payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}

        if top_type == "session_meta":
            s["cwd"] = s["cwd"] or payload.get("cwd")
            s["session_id"] = payload.get("session_id")
            s["id"] = payload.get("id")
            s["parent_thread_id"] = payload.get("parent_thread_id")
            s["codex_is_subagent"] = bool(payload.get("parent_thread_id"))
        elif top_type == "turn_context":
            s["cwd"] = s["cwd"] or payload.get("cwd")

        ptype = payload.get("type")
        if ptype == "message":
            role = payload.get("role")
            text = _text(payload.get("content")).strip()
            if role == "assistant":
                s["asst"] += 1
            elif role == "user" and text and not text.lstrip().startswith("<"):
                clean = text.replace("\n", " ").strip()
                s["user_turns"].append(clean[:140])
                if first_user is None:
                    first_user = clean
        elif ptype == "function_call":
            name = payload.get("name") or "?"
            s["tools"][name] += 1
            if name == "spawn_agent":
                try:
                    inp = json.loads(payload.get("arguments") or "{}")
                except Exception:
                    inp = {}
                prompt = inp.get("message") or ""
                agent_type = inp.get("agent_type") or "default"
                kind = _codex_kind(prompt, agent_type)
                summary = _codex_prompt_summary(prompt) or f"{agent_type} subagent"
                s["workflows"].append(dict(
                    summary=summary,
                    agents=1,
                    tokens=0,
                    tool_uses=0,
                    ms=0,
                    kind=kind,
                    codex_spawn=True,
                    agent_type=agent_type,
                ))
                s["agent_types"][agent_type] += 1
                s["wf_named"][summary.split(":", 1)[0][:34] or kind] += 1
                if ts:
                    s["wf_ts"].append(ts)
        elif ptype == "custom_tool_call":
            s["tools"][payload.get("name") or "custom_tool_call"] += 1
        elif ptype == "mcp_tool_call_end":
            s["tools"][payload.get("tool_name") or "mcp_tool"] += 1
        elif ptype == "token_count":
            token_totals.append(payload.get("info", {}).get("total_token_usage", {}))
            last = payload.get("info", {}).get("last_token_usage", {})
            if ts:
                s["events"].append((
                    ts,
                    int(last.get("output_tokens") or 0) + int(last.get("reasoning_output_tokens") or 0),
                ))
        elif ptype == "task_complete":
            s["duration_ms"] = max(s["duration_ms"], int(payload.get("duration_ms") or 0))

    usage = token_totals[-1] if token_totals else {}
    s["out"] = int(usage.get("output_tokens") or 0) + int(usage.get("reasoning_output_tokens") or 0)
    s["inp"] = int(usage.get("input_tokens") or 0)
    s["cr"] = int(usage.get("cached_input_tokens") or 0)
    s["prompt_summary"] = _codex_prompt_summary(first_user or "")
    return s


def wf_kind(summary):
    t = (summary or "").lower()
    if "implement" in t and "verify" in t:
        return "task-cycle"
    if "review" in t or "adversarial" in t:
        return "review"
    if "apply" in t or "fix" in t:
        return "apply-fixes"
    return "other"


def hours(a, b):
    if not (a and b):
        return 0.0
    f = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
    return round((f(b) - f(a)).total_seconds() / 3600, 1)


def _duration_ms(a, b):
    if not (a and b):
        return 0
    f = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
    return int((f(b) - f(a)).total_seconds() * 1000)


def aggregate(sessions):
    """Roll up one or more parsed sessions into a flat summary."""
    codex_subagents = [s for s in sessions if s.get("runtime") == "codex" and s.get("codex_is_subagent")]
    codex_mains = [s for s in sessions if s.get("runtime") == "codex" and not s.get("codex_is_subagent")]
    claude_sessions = [s for s in sessions if s.get("runtime") != "codex"]

    workflow_runs = []
    for s in sessions:
        if s.get("runtime") != "codex":
            workflow_runs.extend(s["workflows"])

    spawn_workflows = [w for s in codex_mains for w in s["workflows"] if w.get("codex_spawn")]
    for idx, sub in enumerate(codex_subagents):
        prompt = sub.get("prompt_summary") or (sub["user_turns"][0] if sub.get("user_turns") else "")
        spawn = spawn_workflows[idx] if idx < len(spawn_workflows) else {}
        summary = spawn.get("summary") or prompt or os.path.basename(sub["path"])
        kind = spawn.get("kind") or _codex_kind(prompt, sub.get("agent_type") or "")
        ms = sub.get("duration_ms") or _duration_ms(sub.get("ts_first"), sub.get("ts_last"))
        workflow_runs.append(dict(
            summary=summary,
            agents=1,
            tokens=sub["out"],
            tool_uses=sum(sub["tools"].values()),
            ms=ms,
            kind=kind,
        ))
    for spawn in spawn_workflows[len(codex_subagents):]:
        workflow_runs.append(dict(
            summary=spawn.get("summary", ""),
            agents=spawn.get("agents", 1),
            tokens=0,
            tool_uses=0,
            ms=0,
            kind=spawn.get("kind", "other"),
        ))

    main_output_tokens = sum(s["out"] for s in claude_sessions + codex_mains)
    workflow_tokens = sum(w["tokens"] for w in workflow_runs)
    human_sessions = claude_sessions + codex_mains
    out = dict(
        sessions=[s["path"] for s in sessions],
        cwd=next((s["cwd"] for s in sessions if s["cwd"]), None),
        branch=next((s["branch"] for s in sessions if s["branch"]), None),
        wall_hours=hours(min(s["ts_first"] for s in sessions if s["ts_first"]),
                         max(s["ts_last"] for s in sessions if s["ts_last"]))
        if any(s["ts_first"] for s in sessions) else 0.0,
        assistant_turns=sum(s["asst"] for s in sessions),
        user_turns=sum(len(s["user_turns"]) for s in human_sessions),
        runtimes=sorted({s.get("runtime", "claude") for s in sessions}),
        main_output_tokens=main_output_tokens,
        fresh_input_tokens=sum(s["inp"] for s in sessions),
        cache_creation_tokens=sum(s["cc"] for s in sessions),
        cache_read_tokens=sum(s["cr"] for s in sessions),
        workflows=len(workflow_runs),
        workflow_agents=sum(w["agents"] for w in workflow_runs),
        workflow_tokens=workflow_tokens,
        tools=dict(sum((s["tools"] for s in sessions), Counter()).most_common()),
        user_turn_text=[t for s in human_sessions for t in s["user_turns"]],
    )
    out["skills_used"] = dict(sum((s["skills"] for s in sessions), Counter()).most_common())
    at = sum((s["agent_types"] for s in sessions), Counter())
    for s in claude_sessions:
        at += scan_agent_types(s["path"])
    out["agent_types"] = dict(at.most_common())
    out["workflows_named"] = dict(sum((s["wf_named"] for s in sessions), Counter()).most_common())
    # activity timeline: hourly buckets of main output tokens + workflow dispatches
    tl = defaultdict(lambda: [0, 0])
    for s in sessions:
        for ets, out_t in s["events"]:
            tl[ets[:13]][0] += out_t
        for wts in s["wf_ts"]:
            tl[wts[:13]][1] += 1
    out["timeline"] = [{"hour": k[5:].replace("T", " ") + ":00", "out": v[0], "wf": v[1]}
                       for k, v in sorted(tl.items())]
    by = defaultdict(lambda: [0, 0, 0, 0])  # runs, agents, tokens, ms
    runs = []
    for w in workflow_runs:
        k = wf_kind(w["summary"])
        if w.get("kind"):
            k = w["kind"]
        by[k][0] += 1; by[k][1] += w["agents"]; by[k][2] += w["tokens"]; by[k][3] += w["ms"]
        runs.append({**w, "kind": k})
    out["workflow_by_type"] = {k: dict(runs=v[0], agents=v[1], tokens=v[2],
                                       minutes=round(v[3] / 60000, 1))
                               for k, v in sorted(by.items(), key=lambda x: -x[1][2])}
    out["workflow_runs"] = sorted(runs, key=lambda r: -r["tokens"])
    out["generative_total"] = out["main_output_tokens"] + out["workflow_tokens"]
    return out


def bar(v, mx, width=44):
    return "█" * (round(width * v / mx) if mx else 0)


def fmt(n):
    return f"{n:,}"


def report_md(agg):
    L = []
    a = agg
    L.append("## Session shape\n")
    L.append("| Metric | Value |")
    L.append("|---|---|")
    if a.get("cwd"):
        L.append(f"| Project (cwd) | `{a['cwd']}`{' @ ' + a['branch'] if a.get('branch') else ''} |")
    if a.get("runtimes"):
        L.append(f"| Runtime(s) | {', '.join(a['runtimes'])} |")
    L.append(f"| Wall-clock | {a['wall_hours']} h |")
    L.append(f"| Assistant turns | {a['assistant_turns']:,} |")
    L.append(f"| Human messages | {a['user_turns']} |")
    L.append(f"| Tool calls | {sum(a['tools'].values())} |")
    L.append(f"| Background workflows | {a['workflows']} ({a['workflow_agents']} subagents) |")
    L.append("")
    # Token economy (generative)
    L.append("## Token economy\n")
    L.append("**Generated (output) tokens — where the work happened:**\n")
    mo, wt = a["main_output_tokens"], a["workflow_tokens"]
    mx = max(mo, wt, 1)
    tot = mo + wt
    pct = lambda x: f"{round(100*x/tot)}%" if tot else "0%"
    L.append("```")
    L.append(f"delegated to workflows  {fmt(wt):>12}  {bar(wt, mx)}  {pct(wt)}")
    L.append(f"main-loop orchestrator  {fmt(mo):>12}  {bar(mo, mx)}  {pct(mo)}")
    L.append(f"{'total generative':22}  {fmt(tot):>12}")
    L.append("```\n")
    # Total processed incl cache
    cr, cc, inp, gen = a["cache_read_tokens"], a["cache_creation_tokens"], a["fresh_input_tokens"], a["generative_total"]
    gt = cr + cc + gen + inp
    mxp = max(cr, cc, gen, inp, 1)
    L.append("**Total tokens processed (incl. cache):**\n")
    L.append("```")
    for label, v in [("cache read", cr), ("cache creation", cc),
                     ("generated output", gen), ("fresh input", inp)]:
        L.append(f"{label:16} {fmt(v):>14}  {bar(v, mxp)}")
    L.append(f"{'total processed':16} {fmt(gt):>14}")
    L.append("```")
    L.append("> Cache reads scale with session length (the context re-read each turn); "
             "cheap per token but usually the largest line in a long session.\n")
    # Workflow taxonomy
    if a["workflows"]:
        L.append("## Workflow analysis\n")
        L.append(f"{a['workflows']} workflows, {a['workflow_agents']} subagents.\n")
        L.append("```")
        mxw = max((v["tokens"] for v in a["workflow_by_type"].values()), default=1)
        for k, v in a["workflow_by_type"].items():
            L.append(f"{k:14} {v['runs']:>3} runs {v['agents']:>4} ag {fmt(v['tokens']):>12}  {bar(v['tokens'], mxw, 30)}")
        L.append("```\n")
        L.append("**Most expensive runs:**\n")
        L.append("| tokens | agents | min | summary |")
        L.append("|---:|---:|---:|---|")
        for r in a["workflow_runs"][:8]:
            L.append(f"| {fmt(r['tokens'])} | {r['agents']} | {round(r['ms']/60000,1)} | {r['summary'][:48]} |")
        L.append("")
    # Tools
    L.append("## Tool distribution\n")
    L.append("```")
    mxt = max(a["tools"].values(), default=1)
    for k, v in a["tools"].items():
        L.append(f"{k:16} {v:>4}  {bar(v, mxt, 40)}")
    L.append("```\n")
    # Dynamic workflows + agents + skills
    if a.get("workflows_named"):
        L.append("## Dynamic workflows in play\n")
        L.append("```")
        mxn = max(a["workflows_named"].values(), default=1)
        for k, v in a["workflows_named"].items():
            L.append(f"{k[:34]:34} {v:>3}x  {bar(v, mxn, 28)}")
        L.append("```\n")
    if a.get("agent_types") or a.get("skills_used"):
        L.append("## Agents & skills\n")
        at = a.get("agent_types") or {}
        L.append(f"- **Agent types** ({sum(at.values())} subagents): "
                 + (", ".join(f"{k} ({v})" for k, v in at.items()) or "none"))
        sk = a.get("skills_used") or {}
        L.append("- **Skills invoked**: "
                 + (", ".join(f"{k} ({v})" for k, v in sk.items()) or "none") + "\n")
    # Narrative scaffold for the model
    L.append("## Interaction analysis (fill in)\n")
    L.append("Characterize the steering pattern from the human messages below "
             "(autonomous directive vs step-by-step; where they intervened; friction "
             "signals like repeated status checks):\n")
    for i, t in enumerate(a["user_turn_text"], 1):
        L.append(f"{i:>2}. {t}")
    L.append("\n## Retrospective (fill in)\n")
    L.append("Write an honest retro, grounded in the numbers above:\n")
    L.append("- **What went well** - and *why* it worked, so it can be repeated.")
    L.append("- **What went wrong** - the real problems and the rework they caused.")
    L.append("- **Where we got lucky** - outcomes that worked out but were not earned "
             "by the process: a near-miss caught by chance, a guess that happened to be "
             "right, an error that surfaced before it mattered. Luck is not skill; "
             "name it so the process can be hardened to not depend on it.")
    L.append("- **Five Whys** - take the most important problem and ask \"why\" five "
             "times to reach the root cause, then name the systemic fix.\n")
    L.append("## Recommendations (fill in)\n")
    return "\n".join(L)


def md_to_html(md):
    """Minimal markdown -> HTML for the narrative (headings, bold, code, links, lists)."""
    import html as _h
    out, inlist = [], False

    def inline(s):
        s = _h.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
        return s

    for line in md.splitlines():
        l = line.rstrip()
        if not l.strip():
            if inlist:
                out.append("</ul>"); inlist = False
            continue
        m = re.match(r"(#{1,4})\s+(.*)", l)
        if m:
            if inlist:
                out.append("</ul>"); inlist = False
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); continue
        m = re.match(r"[-*]\s+(.*)", l.lstrip())
        if m:
            if not inlist:
                out.append("<ul>"); inlist = True
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        if inlist:
            out.append("</ul>"); inlist = False
        out.append(f"<p>{inline(l)}</p>")
    if inlist:
        out.append("</ul>")
    return "\n".join(out)


HTML_TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Session Retro</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--fg:#e6edf3;--mut:#8b949e;--ac:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
a{color:var(--ac)}.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 70px}
header h1{margin:0 0 4px;font-size:24px}.meta{color:var(--mut);font-size:12px;margin-bottom:22px;word-break:break-all}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:22px}
.kpi{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px 16px}
.kpi .v{font-size:21px;font-weight:700}.kpi .l{color:var(--mut);font-size:12px;margin-top:2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}@media(max-width:760px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:18px}.card h2{margin:0 0 14px;font-size:15px}
.bar{display:flex;align-items:center;gap:10px;margin:7px 0}.bar .lab{width:130px;color:var(--mut);font-size:12px;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .track{flex:1;background:#0d1117;border-radius:6px;overflow:hidden;height:22px;position:relative}
.bar .fill{height:100%;border-radius:6px;transition:width .9s cubic-bezier(.2,.8,.2,1);min-width:2px}
.bar .val{position:absolute;right:8px;top:0;line-height:22px;font-size:11px}.bar:hover .fill{filter:brightness(1.25)}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--bd)}
th{color:var(--mut);cursor:pointer;user-select:none}th:hover{color:var(--fg)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.dough{display:flex;align-items:center;gap:18px;flex-wrap:wrap}.legend div{margin:6px 0;color:var(--mut);font-size:12px}.legend b{color:var(--fg)}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:7px}
.tl{max-height:330px;overflow:auto}.tl .t{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid #21262d}.tl .i{color:var(--ac);font-weight:700;min-width:22px}
.note{color:var(--mut);font-size:12px;margin-top:8px}
.narrative{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:6px 22px 18px;margin-top:16px}
.narrative h2{font-size:18px;border-bottom:1px solid var(--bd);padding-bottom:8px}.narrative h3{font-size:14px;color:var(--ac)}
.narrative code{background:#0d1117;padding:2px 5px;border-radius:4px;font-size:12px}
footer{color:var(--mut);font-size:12px;margin-top:28px;text-align:center}
</style></head><body><div class="wrap">
<header><h1>Session Retro</h1><div class="meta" id="meta"></div></header>
<div class="kpis" id="kpis"></div>
<div class="grid">
<div class="card"><h2>Generated tokens — orchestrator vs delegated</h2><div class="dough" id="dough"></div><div class="note">Output tokens (the real work). Cache reads are shown separately.</div></div>
<div class="card"><h2>Tokens processed (incl. cache)</h2><div id="cache"></div><div class="note">Cache reads = context re-read each turn; cheap, usually the largest line.</div></div>
</div>
<div class="grid">
<div class="card"><h2>Workflows by type</h2><div id="wftype"></div><div class="note">Hover a bar for runs / agents / minutes.</div></div>
<div class="card"><h2>Tool calls</h2><div id="tools"></div></div>
</div>
<div class="grid">
<div class="card"><h2>Dynamic workflows in play</h2><div id="wfnamed"></div><div class="note">By invocation count. A reused workflow script counts each run.</div></div>
<div class="card"><h2>Agents &amp; skills</h2><div id="agents"></div></div>
</div>
<div class="card" style="margin-bottom:16px"><h2>Activity timeline <span class="note">output tokens / hour, purple dots = workflow dispatches</span></h2><div id="timeline"></div></div>
<div class="card" id="wfrunsCard" style="margin-bottom:16px"><h2>Most expensive workflow runs <span class="note">(click a header to sort)</span></h2><table id="wfruns"></table></div>
<div class="card"><h2>Interaction timeline <span class="note" id="utc"></span></h2><div class="tl" id="turns"></div></div>
<div class="narrative" id="narrative">__NARRATIVE__</div>
<footer>Generated by the session-retro skill - reads only local ~/.claude / ~/.codex logs, sends nothing.</footer>
</div><script>
const D = __DATA__, fmt = n => (n||0).toLocaleString(), $ = id => document.getElementById(id);
$('meta').textContent = [D.cwd, D.branch, D.wall_hours? D.wall_hours+' h':''].filter(Boolean).join('  -  ');
$('kpis').innerHTML = [['Wall-clock',(D.wall_hours||0)+' h'],['Assistant turns',fmt(D.assistant_turns)],['Human messages',fmt(D.user_turns)],['Generated tokens',fmt(D.generative_total)],['Workflows',fmt(D.workflows)+' / '+fmt(D.workflow_agents)+' ag'],['Cache read',fmt(D.cache_read_tokens)]].map(([l,v])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');
function doughnut(parts){const tot=parts.reduce((a,p)=>a+p.value,0)||1,R=52,C=2*Math.PI*R;let off=0;const segs=parts.map(p=>{const dash=p.value/tot*C,s=`<circle r="${R}" cx="70" cy="70" fill="none" stroke="${p.color}" stroke-width="20" stroke-dasharray="${dash} ${C-dash}" stroke-dashoffset="${-off}" transform="rotate(-90 70 70)"/>`;off+=dash;return s;}).join('');return `<svg width="140" height="140" viewBox="0 0 140 140">${segs}</svg><div class="legend">${parts.map(p=>`<div><span class="dot" style="background:${p.color}"></span><b>${fmt(p.value)}</b> ${p.label} (${Math.round(100*p.value/tot)}%)</div>`).join('')}</div>`;}
$('dough').innerHTML=doughnut([{label:'delegated to workflows',value:D.workflow_tokens,color:'#bc8cff'},{label:'main-loop orchestrator',value:D.main_output_tokens,color:'#58a6ff'}]);
function hbars(el,items){const mx=Math.max(...items.map(i=>i.value),1);el.innerHTML=items.map(i=>`<div class="bar" title="${i.tip||''}"><div class="lab">${i.label}</div><div class="track"><div class="fill" style="width:${100*i.value/mx}%;background:${i.color}"></div><div class="val">${i.disp||fmt(i.value)}</div></div></div>`).join('');}
hbars($('cache'),[{label:'cache read',value:D.cache_read_tokens,color:'#6e7681'},{label:'cache creation',value:D.cache_creation_tokens,color:'#484f58'},{label:'generated output',value:D.generative_total,color:'#58a6ff'},{label:'fresh input',value:D.fresh_input_tokens,color:'#3fb950'}]);
hbars($('wftype'),Object.entries(D.workflow_by_type||{}).map(([k,v])=>({label:k,value:v.tokens,disp:fmt(v.tokens),tip:v.runs+' runs / '+v.agents+' agents / '+v.minutes+' min',color:'#3fb950'})));
hbars($('tools'),Object.entries(D.tools||{}).map(([k,v])=>({label:k,value:v,disp:String(v),color:'#d29922'})));
hbars($('wfnamed'),Object.entries(D.workflows_named||{}).map(([k,v])=>({label:k.length>22?k.slice(0,21)+'…':k,value:v,disp:v+'x',color:'#bc8cff',tip:k})));
(function(){const at=Object.entries(D.agent_types||{}),sk=Object.entries(D.skills_used||{}),tot=Object.values(D.agent_types||{}).reduce((a,b)=>a+b,0);const m1=Math.max(...at.map(x=>x[1]),1),m2=Math.max(...sk.map(x=>x[1]),1);let h='<div class="note" style="margin:0 0 6px">Agent types ('+tot+' subagents)</div>';h+=(at.map(([k,v])=>`<div class="bar"><div class="lab">${k}</div><div class="track"><div class="fill" style="width:${100*v/m1}%;background:#58a6ff"></div><div class="val">${fmt(v)}</div></div></div>`).join('')||'<div class="note">none</div>');h+='<div class="note" style="margin:13px 0 6px">Skills invoked</div>';h+=(sk.length?sk.map(([k,v])=>`<div class="bar"><div class="lab">${k}</div><div class="track"><div class="fill" style="width:${100*v/m2}%;background:#3fb950"></div><div class="val">${v}</div></div></div>`).join(''):'<div class="note">none</div>');$('agents').innerHTML=h;})();
(function(){const T=D.timeline||[];if(!T.length){$('timeline').closest('.card').style.display='none';return;}const mx=Math.max(...T.map(t=>t.out),1);$('timeline').innerHTML='<div style="display:flex;align-items:flex-end;gap:3px;height:120px">'+T.map(t=>`<div title="${t.hour}: ${fmt(t.out)} output tokens${t.wf?', '+t.wf+' workflow(s) dispatched':''}" style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%"><div style="font-size:11px;color:#bc8cff;height:13px;line-height:13px">${t.wf?'●':''}</div><div style="width:100%;background:linear-gradient(#58a6ff,#1f6feb);border-radius:3px 3px 0 0;height:${Math.round(100*t.out/mx)}%;min-height:2px"></div></div>`).join('')+'</div><div style="display:flex;gap:3px;margin-top:5px">'+T.map((t,i)=>`<div style="flex:1;text-align:center;font-size:8px;color:var(--mut)">${i%2?'':t.hour.slice(6,11)}</div>`).join('')+'</div>';})();
const runs=(D.workflow_runs||[]).slice(0,30);let sk='tokens',sd=-1;
function rr(){runs.sort((a,b)=>sd*((a[sk]>b[sk])?1:(a[sk]<b[sk])?-1:0));$('wfruns').innerHTML='<tr><th data-k="kind">type</th><th data-k="agents" class="n">agents</th><th data-k="tokens" class="n">tokens</th><th data-k="ms" class="n">min</th><th data-k="summary">summary</th></tr>'+runs.map(r=>`<tr><td>${r.kind}</td><td class="n">${r.agents}</td><td class="n">${fmt(r.tokens)}</td><td class="n">${(r.ms/60000).toFixed(1)}</td><td>${(r.summary||'').replace(/</g,'&lt;').slice(0,60)}</td></tr>`).join('');$('wfruns').querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;sd=(sk===k)?-sd:-1;sk=k;rr();});}
runs.length?rr():$('wfrunsCard').style.display='none';
$('utc').textContent='('+(D.user_turn_text||[]).length+' human turns)';
$('turns').innerHTML=(D.user_turn_text||[]).map((t,i)=>`<div class="t"><div class="i">${i+1}</div><div>${t.replace(/</g,'&lt;')}</div></div>`).join('');
if(!$('narrative').textContent.trim())$('narrative').style.display='none';
</script></body></html>"""


def report_html(agg, narrative_html=""):
    data = json.dumps(agg).replace("</", "<\\/")  # prevent </script> breakout
    return (HTML_TEMPLATE
            .replace("__DATA__", data)
            .replace("__NARRATIVE__", narrative_html or ""))


def _head(path, maxlines=800):
    """Cheap breadcrumbs from the top of a session: cwd, branch, first-ts, topic."""
    cwd = branch = ts = topic = runtime = None
    for i, line in enumerate(open(path, errors="replace")):
        if i > maxlines:
            break
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts = ts or d.get("timestamp")
        if d.get("cwd") and not cwd:
            cwd, branch = d["cwd"], d.get("gitBranch")
        payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        if d.get("type") in CODEX_TOP_TYPES:
            runtime = "codex"
        if d.get("type") == "session_meta" and payload.get("cwd") and not cwd:
            cwd = payload.get("cwd")
        if d.get("type") == "turn_context" and payload.get("cwd") and not cwd:
            cwd = payload.get("cwd")
        if not topic and payload.get("type") == "message" and payload.get("role") == "user":
            c = _text(payload.get("content"))
            if c and not c.lstrip().startswith("<"):
                topic = c.replace("\n", " ").strip()[:72]
        if not topic and d.get("type") == "user" and isinstance(d.get("message"), dict):
            c = d["message"].get("content")
            if isinstance(c, str) and not c.lstrip().startswith("<"):
                topic = c.replace("\n", " ").strip()[:72]
        if cwd and topic:
            break
    return dict(cwd=cwd, branch=branch, ts=ts, topic=topic, runtime=runtime or "claude")


def _session_files():
    return glob.glob(f"{PROJECTS}/**/*.jsonl", recursive=True) + glob.glob(f"{CODEX_SESSIONS}/**/*.jsonl", recursive=True)


def _session_rows(sub=""):
    rows = []
    needle = sub.lower()
    for f in _session_files():
        try:
            h = _head(f)
            haystack = " ".join(str(v or "") for v in (f, h.get("cwd"), h.get("branch"), h.get("topic"))).lower()
            if needle and needle not in haystack:
                continue
            sz = os.path.getsize(f)
            mt = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            rows.append((mt, sz, f, h))
        except Exception:
            continue
    return rows


def _codex_meta(path):
    for d in _jsonl(path):
        if d.get("type") == "session_meta" and isinstance(d.get("payload"), dict):
            return d["payload"]
    return {}


def _codex_sort_key(path):
    meta = _codex_meta(path)
    return (1 if meta.get("parent_thread_id") else 0,
            meta.get("timestamp") or "",
            path)


def expand_paths(paths):
    """Expand a Codex rollout to all rollout JSONLs from the same session_id."""
    expanded = []
    seen = set()
    for path in paths:
        if not _is_codex(path):
            if path not in seen:
                expanded.append(path)
                seen.add(path)
            continue
        meta = _codex_meta(path)
        session_id = meta.get("session_id")
        if not session_id:
            if path not in seen:
                expanded.append(path)
                seen.add(path)
            continue
        candidates = []
        for candidate in glob.glob(f"{CODEX_SESSIONS}/**/*.jsonl", recursive=True):
            if _codex_meta(candidate).get("session_id") == session_id:
                candidates.append(candidate)
        if path not in candidates:
            candidates.append(path)
        for candidate in sorted(candidates, key=_codex_sort_key):
            if candidate in seen:
                continue
            expanded.append(candidate)
            seen.add(candidate)
    return expanded


def cmd_list(args):
    """List sessions (newest last) with breadcrumbs so a user can pick one."""
    sub = args[0] if args else ""
    rows = _session_rows(sub)
    for mt, sz, f, h in sorted(rows)[-40:]:
        proj = (h.get("cwd") or os.path.basename(os.path.dirname(f))).replace(os.path.expanduser("~/"), "~/")
        print(f"{mt}  {h['runtime']:<6}  {sz//1024:>5}K  {(h['branch'] or '-'):22}  {proj[:46]}")
        if h["topic"]:
            print(f"            ↳ {h['topic']}")
        print(f"            {f}")
    if rows:
        print(f"\n# newest (likely the current session):\n{sorted(rows)[-1][2]}")
    else:
        print(f"no sessions found{f' matching {sub!r}' if sub else ''} under {PROJECTS} or {CODEX_SESSIONS}")


def cmd_find(args):
    """Find sessions whose content mentions a keyword (PR #, feature, filename...)."""
    if not args:
        print("usage: find <keyword> [project-substr]   e.g. find '#93' anvil")
        return
    kw, sub = args[0].lower(), (args[1] if len(args) > 1 else "")
    rows = []
    for _, _, f, h in _session_rows(sub):
        try:
            hits = open(f, errors="replace").read().lower().count(kw)
        except Exception:
            continue
        if hits:
            mt = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            rows.append((mt, hits, f, h))
    for mt, hits, f, h in sorted(rows):
        proj = (h.get("cwd") or os.path.basename(os.path.dirname(f))).replace(os.path.expanduser("~/"), "~/")
        print(f"{mt}  {h['runtime']:<6}  {hits:>4}x  {(h['branch'] or '-'):22}  {proj[:46]}")
        if h["topic"]:
            print(f"            ↳ {h['topic']}")
        print(f"            {f}")
    if not rows:
        print(f"no sessions mention {args[0]!r}{f' (filter {sub!r})' if sub else ''}")


def main(argv):
    if len(argv) < 2 or argv[1] not in ("list", "find", "stats", "report", "html"):
        print(__doc__)
        return 1
    mode, args = argv[1], argv[2:]
    if mode == "list":
        cmd_list(args)
        return 0
    if mode == "find":
        cmd_find(args)
        return 0
    narrative = ""
    if "--narrative" in args:
        i = args.index("--narrative")
        try:
            narrative = md_to_html(open(args[i + 1], encoding="utf-8").read())
            args = args[:i] + args[i + 2:]
        except (IndexError, OSError) as e:
            print(f"error: --narrative needs a readable file ({e})", file=sys.stderr)
            return 2
    paths = expand_paths([p for p in args if os.path.exists(p)])
    if not paths:
        print("error: no existing session JSONL paths given", file=sys.stderr)
        return 2
    agg = aggregate([parse(p) for p in paths])
    if mode == "stats":
        print(json.dumps(agg, indent=1))
    elif mode == "html":
        print(report_html(agg, narrative))
    else:
        print(report_md(agg))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
