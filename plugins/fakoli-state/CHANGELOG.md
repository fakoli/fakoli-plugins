# Changelog

All notable changes to fakoli-state are documented here. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

Phases 2-8 are planned and actively scheduled. Each phase ships as its own PR into the fakoli-plugins monorepo.

- **Phase 2** — State engine: Pydantic models, SQLite backend, JSONL event log, `init`/`status` CLI commands, state-ops skill, `detect-state.sh` SessionStart hook, and full unit + component test coverage.
- **Phase 3** — Planning engine (template path): `prd parse`, `prd review`, `plan`, `score`, `expand`, `review tasks`, `list`, `show` CLI commands, prd and plan skills, planner agent, and tests.
- **Phase 4** — Claims manager: `claim`, `release`, `renew`, `next` CLI commands, git branch auto-creation on claim, claim skill, `check-claim.sh` and `record-file-change.sh` hooks, and tests.
- **Phase 5** — Context engine: `packet`, `submit`, `apply` CLI commands, Review engine apply gate, execute and finish skills, `capture-evidence.sh` hook, critic and sentinel agents, and tests.
- **Phase 6** — MCP server: 13 agent-facing tools, `.mcp.json` wiring, `bin/fakoli-state-mcp` bash wrapper, MCP integration tests, and `docs/mcp.md`.
- **Phase 7** — LLM augmentation: Anthropic provider implementation, `--use-llm` flags on `plan`, `score`, `expand`, RecordedLLMProvider for tests, and brainstorm skill bridge to `fakoli-flow:brainstorm`.
- **Phase 8** — GitHub sync: bidirectional Issues sync engine, `sync github` CLI command, state-keeper agent, reconciliation (`sync --fix`), nightly live-GitHub CI, `docs/github-sync.md`, marketplace.json regen, and feature-complete release. Phases 2-8 will be released as successive minor versions on top of 1.0.0.

---

## [1.0.0] — 2026-05-24

Phase 1: Plugin scaffold. No executable state operations ship in this release — this entry records the structural foundation that all subsequent phases build on. Version 1.0.0 follows the fakoli-plugins repository convention that new plugins ship at 1.0.0 regardless of feature completeness (per `CLAUDE.md` § New Plugin Checklist).

### Added

- `.claude-plugin/plugin.json` — plugin manifest declaring name, version (`1.0.0`), description, author, repository, license, and marketplace keywords.
- `README.md` — positions fakoli-state against CCPM and issue-tracker-as-state patterns; documents the "5 must-do-better" list; install instructions (git clone until marketplace publication); Quick Start teaser for the intended `fakoli-state init` flow; architecture overview; 8-phase build status table; integration notes for fakoli-flow and fakoli-crew.
- `CHANGELOG.md` — this file; Keep a Changelog format.
- `LICENSE` — MIT license, copyright 2026 Sekou Doumbouya.
- `docs/specs/2026-05-24-fakoli-state-v0.md` — canonical build specification: data model, CLI command set, MCP tool surface, hook event mappings, phasing plan, and integration contracts.
- `bin/fakoli-state` — bash wrapper that invokes `uv run python -m fakoli_state.cli`; `--version` stub returns `1.0.0`.
- `bin/fakoli-state-mcp` — bash wrapper that invokes `uv run python -m fakoli_state.mcp_server`; stubbed pending Phase 6 with a clean error message instead of a raw Python traceback.
- `bin/pyproject.toml` — uv-managed Python project (Hatchling build backend); declares dependencies: Typer, Pydantic v2, FastMCP, and test tooling (pytest, ruff, mypy, responses).
- `bin/uv.lock` — locked dependency tree for reproducible installs.
- `bin/src/fakoli_state/__init__.py` — package init; exports `__version__ = "1.0.0"`.
- `bin/src/fakoli_state/cli.py` — Typer application; single `--version` flag functional; all other subcommands stubbed with `typer.echo("Not yet implemented")`.
- Skeleton directories establishing the plugin layout: `skills/`, `agents/`, `hooks/`, `tests/`, `docs/`.
