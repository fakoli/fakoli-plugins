# Changelog

All notable changes to fakoli-state are documented here. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

Phases 6-8 are planned and actively scheduled. Each phase ships as its own PR into the fakoli-plugins monorepo.

- **Phase 6** — MCP server: 13 agent-facing tools, `.mcp.json` wiring, `bin/fakoli-state-mcp` bash wrapper, MCP integration tests, and `docs/mcp.md`.
- **Phase 7** — LLM augmentation: Anthropic provider implementation, `--use-llm` flags on `plan`, `score`, `expand`, RecordedLLMProvider for tests, and brainstorm skill bridge to `fakoli-flow:brainstorm`.
- **Phase 8** — GitHub sync: bidirectional Issues sync engine, `sync github` CLI command, state-keeper agent, reconciliation (`sync --fix`), nightly live-GitHub CI, `docs/github-sync.md`, marketplace.json regen, and feature-complete release. Phases 2-8 will be released as successive minor versions on top of 1.0.0.

---

## [1.4.1] — 2026-05-25

Docs-only patch release. Stages the deferred items from the PR #41 critic +
Greptile reviews into a single backlog document so Phase 6 work picks them
up explicitly without re-reading chat transcripts.

### Added

- `docs/tech-debt-backlog.md` — 31 open items + 11 already-closed (for
  reference), grouped into: Phase 6 must-close (5), Cleanup (16), Test
  quality (8), Performance (2). Each entry cites its source (Greptile,
  Critic-1/2/3/4) and includes a concrete fix sketch.

---

## [1.4.0] — 2026-05-25

Phase 5: Context engine. Delivers the context engine, review apply gate, three new CLI commands, one new hook subcommand, two new skills, two new plugin-owned agents, a new PostToolUse hook, state engine extensions, and a comprehensive test suite. The plugin now supports the complete claim → packet → work → submit → apply lifecycle.

### Added

- Context engine (`context/packets.py`) — `render_packet()` produces both markdown (for `.fakoli-state/packets/T001.md`) and JSON (for MCP `get_work_packet` in Phase 6). Pure function; no I/O.
- Review engine apply gate (`review/gates.py`) — `evidence_complete(task, evidence)` validates that submitted Evidence satisfies the task's `required_evidence` list; surfaces specific missing items.
- Three new CLI commands: `packet TASK_ID [--format md|json]`, `submit TASK_ID --commands ... --files-changed ... [--output-file --pr-url --commit-sha --known-limitations --actor]`, `apply TASK_ID [--approve | --reject] [--reason --reviewer]`.
- One new hook subcommand: `fakoli-state hook capture-evidence --command --exit-code --stdout-file --stderr-file --actor` — used by the new PostToolUse Bash hook.
- Two new skills: `skills/execute/SKILL.md` (full claim → packet → work → submit loop; coordinates with `fakoli-flow:execute` when installed) and `skills/finish/SKILL.md` (apply + ship decision: merge/PR/keep/discard).
- Two new plugin-owned agents: `agents/critic.md` (code reviewer; defers to `fakoli-crew:critic`) and `agents/sentinel.md` (evidence validator; defers to `fakoli-crew:sentinel`). Both `allowed-tools` exclude Edit/Write (Iron Rule at tool-permission level).
- New PostToolUse hook: `hooks/capture-evidence.sh` (Bash matcher) — captures stdout/stderr/exit-code of verification commands (`pytest`, `ruff`, `mypy`, `npm test`, `cargo test`, `bun test`) into `.fakoli-state/.evidence-buffer/` per-claim JSON files for later attachment to Evidence.
- State engine: 2 new event handlers (`evidence.submitted`, `task.applied`) both routed via `_apply_mutation`. `evidence.submitted` atomically inserts Evidence + transitions task to `needs_review` + auto-releases the active claim. `task.applied` combines `needs_review` → `accepted` → `done` in one transaction when `decision='accepted'`.
- 81 new tests (403 → 484): `test_context.py` (24 tests), `test_review.py` (20), `test_sqlite.py` extensions (16 new Phase 5 handler tests + the audit replay test for `evidence` + `applied`), `test_cli.py` extensions (17 new), `test_hooks.sh` extensions (5 new capture-evidence smoke tests).
- Coverage: context 93%, review 97%, state 95.70%, claims 99%, overall 91.16%.
- Audit guarantee extended: `TestReplayIncludesPhase5Events` byte-compares `sqlite3 .dump` after replaying the full lifecycle including `evidence.submitted` and `task.applied` (both accepted and rejected branches).

### Fixed

- Dead-code unreachable branch in `_handle_evidence_submitted` — `if commands_run is None` was never reachable because the field defaulted to `[]`. Fixed to `if not commands_run` which catches both None and empty (submitting evidence with no verification commands is meaningless).

---

## [1.3.0] — 2026-05-24

Phase 4: Claims manager. Delivers atomic claim/release/renew/next semantics with lease and heartbeat enforcement, git branch auto-creation, two new bash hooks, a claim skill, and a comprehensive test suite. The plugin now supports the complete claim-based coordination workflow for AI agents working in parallel.

### Added

- Claims manager (`claims/manager.py` — atomic claim/release/renew with lease and heartbeat semantics; Clock-injected for deterministic tests).
- Stale claim detector (`claims/stale.py` — runs on every CLI invocation; returns expired claims back to the ready pool with audit trail).
- Four new CLI commands: `claim TASK_ID [--worktree] [--force] [--actor]`, `release CLAIM_ID [--force] [--reason]`, `renew CLAIM_ID`, `next [--actor]`.
- Hook sub-app: `fakoli-state hook check-claim` and `fakoli-state hook record-file-change` (used by the new bash hooks).
- Git ops module: `git_ops/branch.py` auto-creates `agent/<task>-<slug>` branches on claim (with name-collision suffix, graceful no-op when git absent); `git_ops/worktree.py` for optional `--worktree` parallel-checkout.
- Two new hooks: `check-claim.sh` (PreToolUse on Edit|Write|NotebookEdit; warns when active claims exist) and `record-file-change.sh` (PostToolUse; appends file_changed events to the audit log).
- New skill: `skills/claim/SKILL.md` — workflow choreography for the claim → work → renew → release loop.
- State engine: 4 new event handlers (`claim.created`, `claim.released`, `claim.renewed`, `claim.stale`) all routed through `_apply_mutation` dispatch.
- 98 new tests (300 → 398): `test_claims.py` (concurrency-critical, `claims/` coverage 99%), `test_git_ops.py` (real git per test), `test_hooks.sh` (11 bash smoke tests), extended `test_sqlite.py` and `test_cli.py`.
- Audit guarantee extended: `TestReplayIncludesPhase4ClaimActions` byte-compares `sqlite3 .dump` after replaying `claim.created` → `claim.renewed` → `claim.released`; companion `test_replay_includes_claim_stale` covers the stale path.

### Fixed

- `claims/stale.py` event payload was missing the required `reason` field expected by `_handle_claim_stale` (caught by Wave 3 tests).
- `_handle_claim_released` was incorrectly requiring `release_reason` — payload field is optional and the ClaimManager legitimately passes None when no reason is given.

### Notes

- Stale claim reaping is automatic on every mutating CLI command (`claim`, `release`, `renew`, `next`); users don't need to think about it.
- Claims survive without git: when git is absent or cwd is not a git repo, the claim succeeds without a branch and prints a warning (record-only mode).

---

## [1.2.0] — 2026-05-24

Phase 3: Planning engine. Delivers the full planning runtime — deterministic PRD parser, six-dimension scoring engine, dependency and conflict-group inference, eight new CLI subcommands, two new skills, a new agent, and a PRD template doc. The plugin now supports the complete PRD-to-ready-tasks workflow without LLM augmentation.

### Added

- Planning engine: deterministic template parser (`planning/template.py` — turns structured markdown into Pydantic Requirements/Features/Tasks; full quick-start example documented at `docs/prd-template.md`).
- Six-dimension scoring engine (`planning/scoring.py` — rule-based heuristics for complexity, parallelizability, context_load, blast_radius, review_risk, agent_suitability; explanation string per task).
- Dependency and conflict-group inference (`planning/inference.py` — subset-overlap heuristic for dependencies, partial-overlap detection for conflict groups).
- Eight new CLI subcommands: `prd parse`, `prd review [--approve]`, `plan`, `score [TASK_ID]`, `expand TASK_ID` (Phase 7 scaffold), `review tasks`, `list [--status STATUS --feature F]`, `show TASK_ID`.
- Two new skills: `skills/prd/` (PRD authoring/review workflow) and `skills/plan/` (PRD → ready tasks workflow), both following the state-ops imperative-voice and scannable-description conventions.
- New agent: `agents/planner.md` (PRD-to-tasks specialist; defers to `fakoli-crew:guido` when fakoli-crew is installed; allowed-tools excludes Edit/Write to enforce the "propose, don't mutate" Iron Rule at the tool-permission level).
- PRD template doc (`docs/prd-template.md` — ~2,500 words; quick-start JSON-to-YAML converter example demonstrates every documented field).
- SQLite event router extended with 8 new actions: `prd.parsed`, `prd.reviewed`, `prd.approved`, `feature.created`, `task.created`, `task.scored`, `task.expanded`, `task.status_changed`; all routed via `_apply_mutation` dispatch; replay-from-empty handles all 8.

### Fixed

- `_insert_task_row` switched from `INSERT OR REPLACE` to `INSERT ... ON CONFLICT DO UPDATE` to preserve task row identity across `plan` re-runs. `INSERT OR REPLACE` is DELETE+INSERT, which trips `ON DELETE RESTRICT` on `claims.task_id` and `evidence.task_id` once work has begun. Regression test: `test_plan_is_idempotent`.

### Tests

- 122 new tests (174 → 296). `state/` coverage 95.05% (audit-critical), `planning/` ~93%, `cli` ~88%, overall 92.72%.
- Audit guarantee extended: `test_replay_includes_new_event_actions` byte-compares `sqlite3 .dump` before/after replaying a mixed sequence of all 8 new event actions.

---

## [1.1.0] — 2026-05-24

Phase 2: State engine. Delivers the full runtime core — data models, state machine, SQLite backend, event log, CLI, skill, hook, and test suite. The plugin is now operationally useful for tracking project state.

### Added

- State engine: Pydantic v2 models (14 entities) in `state/models.py` — `Project`, `Requirement`, `Feature`, `Task`, `Claim`, `Evidence`, `FileChange`, `Snapshot`, `TaskScore`, `SnapshotEntry`, `Config`, and supporting enums (`TaskStatus`, `ClaimStatus`, `EvidenceKind`).
- Pure state machine transitions in `state/transitions.py` — 17 transition functions plus `TransitionError` and gate helper predicates; no I/O, fully deterministic.
- Backend Protocol + concrete `SqliteBackend` in `state/sqlite.py` — WAL journal mode, JSONL event log (`events.jsonl`) written atomically on every mutation, full replay guarantee.
- DDL schema generator (`state/schema.py`) — foreign keys, composite indexes, schema versioning table; generates idempotent `CREATE TABLE IF NOT EXISTS` SQL.
- Clock Protocol with `SystemClock` and `FrozenClock` for deterministic tests — injected via `SqliteBackend(clock=...)`.
- Config loader (`config.py`) — reads `config.yaml` from the `.fakoli-state/` directory; Pydantic-validated; falls back to sensible defaults.
- PEP 561 `py.typed` marker — `fakoli_state` is now a typed package.
- CLI subcommand `init` — scaffolds `.fakoli-state/` directory in the caller's project: `config.yaml`, `state.db`, `events.jsonl`, `prd.md`, `packets/`, and `snapshots/`. Fixed a wrapper bug (`--project "$BIN_DIR"` → wrapper now passes `--project` to preserve the caller's working directory so `init` scaffolds in the correct location).
- CLI subcommand `status` — human-readable summary of project state; `--hook-format` flag emits compact key=value pairs for hook consumption.
- First skill: `state-ops` — covers common state inspection and manipulation workflows from within Claude Code.
- `SessionStart` hook `detect-state.sh` — detects `.fakoli-state/state.db` in the project root on session start and surfaces a brief status banner to the agent.
- 173 tests covering `state/models.py`, `state/transitions.py`, `state/sqlite.py`, CLI (`init`, `status`, `--version`), `config.py`, and the `detect-state.sh` hook; 94% overall coverage, 95% on `state/`.
- Audit-guarantee test `test_replay_from_empty_reconstructs_state_exactly` — replays `events.jsonl` from scratch against an empty database and asserts byte-for-byte equality with the live `state.db`.

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
