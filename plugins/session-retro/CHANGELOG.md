# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-07-13

### Fixed
- `list`/`find` no longer crash with `UnicodeEncodeError` on default Windows
  cp1252 consoles: human output goes through an encoding-safe printer that
  degrades the `↳` topic marker to `->` instead of dying (#135). JSON/report
  modes are untouched.
- Forked Codex rollouts are no longer duplicated or misclassified (#134):
  - `expand_paths()` canonicalizes paths before deduplication, so the same
    rollout selected as `C:\...` and `C:/...` counts once;
  - only the FIRST `session_meta` record sets a rollout's identity — replayed
    parent metadata can no longer erase a non-null `parent_thread_id` and
    reclassify a subagent as a main session;
  - forked rollouts' cumulative token totals (which replay the parent's) are
    excluded from main-loop/input/cache sums instead of being charged twice.

### Added
- Delegated token totals that cannot be proven from the log format are now
  reported as unavailable (`tokens: null`, `workflow_tokens_available: false`,
  human-readable `measurement_notes`) instead of a measured `0` (#134).
  `report`/`html` render "n/a" and a note rather than a false "0% delegated".
- Workflow labels fall back to `agent_nickname`/`agent_path` (from spawn args
  or `session_meta.source.subagent.thread_spawn`) when the prompt text is an
  encrypted `gAAAA…` blob; encrypted payloads are also excluded from the
  human-turn list (#134).
- `codex_is_subagent` now also recognizes rollouts marked via
  `session_meta.source.subagent`.
- Test suite (`tests/test_session_stats.py`) now runs in CI via
  `.github/workflows/session-retro.yml`.

### Fixed (post-review)

- `report`/`html`/`stats` no longer crash on cp1252 consoles either: `main()`
  reconfigures stdout with `errors="replace"`, so the report's `█` bar
  characters degrade instead of raising (the initial fix only covered
  `list`/`find`).
- The HTML report renders unavailable token totals as `n/a` (runs table and
  doughnut legend) instead of a measured `0`, matching the markdown report.
- `workflow_by_type` no longer coerces unavailable totals to `0`: a type
  whose runs are all token-unavailable reports `tokens: null` (rendered
  `n/a`), mixed types carry an `unknown_runs` count, and the by-type table
  marks affected rows with `*`.
- Forked rollouts' replayed parent history is now also excluded from tool
  counts, assistant turns, skills/agent/workflow tallies, and the activity
  timeline — not just token sums.
- `expand_paths()` skips inputs already swept in by an earlier expansion
  instead of re-scanning all of `~/.codex/sessions` per duplicate spelling.

## [1.1.1] - 2026-06-26

### Fixed
- Added the `/session-retro` command advertised by the README.
- Renamed skill frontmatter `user_invocable` to `user-invocable`.
- Aligned manifest and skill descriptions with the project-local default output location.

## [1.1.0] - 2026-06-25

### Added
- Codex session discovery and parsing from `~/.codex/sessions/**/*.jsonl`.
- Automatic Codex rollout expansion: passing a main rollout includes sibling
  subagent rollouts that share the same `session_id`.
- Codex token splitting for main-loop output vs delegated subagent output,
  including reasoning output tokens.
- Focused parser tests for Claude compatibility and Codex main/subagent
  aggregation.

## [1.0.0] - 2026-06-23

### Added
- `session-retro` skill: produce a markdown retro from any Claude Code session.
- Session discovery — target any session, not just the current one: `list` (browse
  by date / branch / first-message topic) and `find` (search session content by
  keyword: a PR number, feature, filename, error).
- Interactive **single-page HTML site** (`html` mode): self-contained, no network
  or dependencies — KPI cards (incl. cache), an SVG token doughnut, hover-tooltip bar
  charts, a sortable workflow table, the interaction timeline, and the narrative
  rendered inline (`--narrative note.md`, via a tiny built-in markdown converter).
- Visualizations: **dynamic workflows in play** (by name), **agents & skills** (agent
  types across subagents + skills invoked), and an **activity timeline** (output
  tokens per hour with workflow-dispatch markers).
- Deeper retro structure: interaction analysis, **what went well / wrong / where we
  got lucky**, and a **Five Whys** root-cause pass (in `report` + the skill guidance).
- `scripts/session_stats.py` (stdlib-only) with `list` / `find` / `stats` /
  `report` / `html` modes: main-loop vs delegated-workflow token split, workflow
  taxonomy, tool distribution, ASCII charts, session cwd/branch, and multi-session
  (arc) combination.
- Configurable output location, defaulting to a `post-session-findings/` directory
  in the project the session worked in.
