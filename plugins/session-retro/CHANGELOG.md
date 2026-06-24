# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
