# session-retro

Turn a Claude Code or Codex session's raw logs into an evaluable retro — token
economy, workflow taxonomy, tool distribution, interaction shape, and
recommendations.

Built from a real post-mortem of a 23-hour autonomous run: the kind of analysis
you want after a long session to understand *where the tokens went, what the
agents did, and how you and the coding agent actually collaborated.*

## Use it

Type `/session-retro`, or ask: "do a session retro", "pull stats on this
session", "how many tokens did this session use", "analyze how we worked".

## What you get

An **interactive single-page site** (`session-retro.html` — self-contained, no
network or dependencies) plus a `SESSION-REPORT.md` and `session_stats.json`, saved
**in the project by default** (or any location you choose). They cover:

- **Session shape** — wall-clock, turns, human messages, tool calls, workflows, cache.
- **Token economy** — *generated* tokens split main-loop vs delegated-to-workflows
  (an SVG doughnut), plus the *cache-read* line (the context re-read each turn).
- **Dynamic workflows in play** — every workflow by name and invocation count.
- **Agents & skills** — agent types across all subagents, and skills invoked.
- **Activity timeline** — output tokens per hour with workflow-dispatch markers, so
  the session's rhythm (bursts, idle stretches) is visible at a glance.
- **Workflow analysis** — runs/agents/tokens/minutes by type, and a **sortable** table
  of the most expensive runs.
- **Tool distribution** — what the orchestrator actually spent its calls on.
- **An honest retrospective** — interaction analysis, **what went well / what went
  wrong / where we got lucky**, a **Five Whys** root-cause pass on the biggest problem,
  and recommendations (written with judgment, grounded in the numbers).

Multi-session arcs are supported: pass several session logs and the stats combine,
with a comparison table and combined totals.

## How it works

`scripts/session_stats.py` (stdlib-only, no dependencies) parses
`~/.claude/projects/**/*.jsonl` and `~/.codex/sessions/**/*.jsonl`. **Target any
session, not just the current one** — browse with `list` or search session content
with `find`:

```bash
session_stats.py list [substr]            # browse sessions (date / branch / topic)
session_stats.py find <keyword> [substr]  # find sessions mentioning a keyword (PR#, feature, file)
session_stats.py stats  <a.jsonl> [b...]  # JSON aggregates (combined if >1)
session_stats.py report <a.jsonl> [b...]  # markdown + ASCII charts
session_stats.py html   <a.jsonl> [b...] [--narrative note.md]  # interactive single-page site
```

For Codex, passing a main rollout path automatically includes sibling subagent
rollouts with the same `session_id`, so delegated workflow tokens are split out
without manually listing every child JSONL. The script does the deterministic
counting + discovery + the interactive site; the skill adds the narrative.

## Privacy

Reads only local `~/.claude` and `~/.codex` logs. Writes only to the location you
choose (default: a `post-session-findings/` dir in the project). Sends nothing
externally.

## License

MIT
