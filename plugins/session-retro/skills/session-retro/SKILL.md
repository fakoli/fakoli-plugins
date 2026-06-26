---
name: session-retro
description: Analyze a Claude Code or Codex session (or a multi-session arc) from local JSONL logs and produce a markdown retro — token economy (main-loop vs delegated workflows), workflow taxonomy, tool distribution, interaction shape, and concrete recommendations. Use when the user asks to "do a session retro", "analyze this session", "pull stats on this session", "how many tokens did this session use", "session statistics / report", "post-session findings", "evaluate how we worked", or wants to review a long autonomous run. Reads only local ~/.claude and ~/.codex logs and writes to a project-local post-session-findings directory by default; sends nothing externally.
user-invocable: true
---

# Session Retro

Turn a Claude Code or Codex session's raw logs into an evaluable retro: where the
tokens went, what workflows ran, how the human steered, and what to change next
time.

## Toolkit (bundled)

`${CLAUDE_PLUGIN_ROOT}/scripts/session_stats.py` — stdlib-only Python, three modes:

```bash
P="${CLAUDE_PLUGIN_ROOT}/scripts/session_stats.py"
python3 "$P" list  [substr]                       # browse sessions (date/branch/topic)
python3 "$P" find  <keyword> [substr]             # find sessions by content (PR#, feature, file)
python3 "$P" stats  <a.jsonl> [b...]              # JSON aggregates (combined if >1)
python3 "$P" report <a.jsonl> [b...]              # markdown + ASCII charts
python3 "$P" html   <a.jsonl> [b...] [--narrative note.md]   # interactive single-page site
```

It does all the deterministic counting (tokens, tools, per-workflow agents/tokens/
minutes, timestamps) and ends the `report` with the ordered list of human turns.
**Your job is the judgment** — the interaction analysis and recommendations.

## Steps

1. **Locate the session(s) — any session, not only the current one.** Two
   discovery modes; both print a date, runtime, git branch when available,
   first-message **topic**, and the path for each session:
   - `session_stats.py list [substr]` — browse sessions, newest last. The **newest
     is almost always the current session** (its JSONL is still being written).
     `substr` filters by project/worktree path, e.g. `list anvil`.
   - `session_stats.py find <keyword> [substr]` — find sessions whose **content**
     mentions a keyword (a PR number like `find '#93'`, a feature name, a filename,
     an error message), ranked by hit count. This is how to locate "the session
     where we did X" when the user does not remember which one.

   Use the topic/branch/date breadcrumbs to confirm with the user which session(s)
   they mean, then pass the path(s) to `stats`/`report`. Default to the current
   (newest) session only when they do not name one. For Codex, passing a main
   rollout path automatically includes sibling subagent rollouts with the same
   `session_id`.

2. **Detect a multi-session arc (optional but valuable).** A feature often spans
   sessions in different worktrees. To find related ones: list sessions for the
   same repo family, look for adjacent timestamps (one ending ~minutes before the
   next begins), or search the local Claude/Codex session directories for a
   feature marker. Pass every related JSONL to `stats`/`report` — they combine
   automatically.

3. **Generate the deterministic report.**
   `session_stats.py report <session...> > /tmp/retro-skeleton.md`. This fills:
   session shape, token economy (generated vs delegated + the cache-read line),
   workflow taxonomy + most-expensive runs, tool distribution — and lists the
   human turns under "Interaction analysis (fill in)".

4. **Write the narrative — an honest retro, not a victory lap.** Read the human-turn
   list and skim the session for the key events (merges, failures, course-corrections,
   retries). Fill in the report's "(fill in)" sections:
   - **Interaction analysis** — one autonomous directive or step-by-step? Where did
     the human intervene, and were those the right calls to reserve for a human?
     Friction signals (e.g. repeated "is it stuck?" = a visibility gap).
   - **Retrospective:**
     - **What went well** — and *why*, so it can be repeated.
     - **What went wrong** — the real problems and the rework they caused.
     - **Where we got lucky** — outcomes that worked out but were not *earned* by the
       process: a near-miss caught by chance, a guess that happened to be right, an
       error that surfaced before it mattered. Luck is not skill; naming it shows
       where the process is fragile and should be hardened.
     - **Five Whys** — take the most important problem and ask "why" five times to
       reach the root cause, then name the systemic fix (not a band-aid).
   - **Recommendations** — concrete, grounded in the numbers and the Five Whys.

   Save these sections as a `narrative.md` — it feeds both the report and the site.

5. **Choose the destination, then assemble + save.** **Default: within the
   project** the session worked in — a `post-session-findings/<short-label>/`
   directory at the project root. Resolve that root from the session's `cwd` (it is
   in the `stats`/`report` output):
   `git -C "<cwd>" rev-parse --show-toplevel 2>/dev/null || echo "<cwd>"`.
   **Confirm the location with the user and honor any alternate they ask for** — the
   most common one is **outside the repo** (e.g. `~/post-session-findings/`) when the
   project is public/shared and the retro shouldn't be committed, or when they just
   want it kept separate. Create the dir and write **three deliverables**:
   - `SESSION-REPORT.md` — the `report` output with the three sections filled in.
   - `session-retro.html` — `html <session...> --narrative narrative.md`: a
     self-contained **interactive single-page site** (KPI cards, an SVG token
     doughnut, hover-tooltip bar charts, a sortable workflow table, the interaction
     timeline, and the narrative rendered inline). No network/deps. The headline
     deliverable — surface it to the user.
   - `session_stats.json` — `stats <session...>` for re-slicing.

   If writing inside a repo, mention they may want to `.gitignore` the directory.
   For a multi-session arc, pass every session path to `report`/`html`/`stats` and
   add a §0 table comparing the sessions + combined totals.

6. **Report back.** Give the path and the headline numbers (wall-clock, turns,
   human messages, generated-token split, workflow count, outcome). Offer to send
   the markdown file.

## Notes

- **Privacy:** reads only local `~/.claude/projects/**.jsonl` and
  `~/.codex/sessions/**.jsonl`; writes only to the destination you choose
  (default: a `post-session-findings/` dir in the project); never sends session
  contents anywhere.
- **Token vocabulary:** *generated/output* tokens are the real work; *cache-read*
  tokens (often the biggest number) are the context re-read each turn — cheap, not
  effort. Always report both and explain the difference.
- **Workflow types** are auto-classified from each run's summary (task-cycle =
  implement+verify, review = review/adversarial, apply-fixes, other).
- The numbers are a live snapshot — re-running mid-session yields larger totals as
  the current session keeps growing.
