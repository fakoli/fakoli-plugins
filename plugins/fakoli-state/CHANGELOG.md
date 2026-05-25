# Changelog

All notable changes to fakoli-state are documented here. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

Phase 8 remains scheduled. It ships as its own PR into the fakoli-plugins monorepo.

- **Phase 8** — GitHub sync: bidirectional Issues sync engine, `sync github` CLI command, state-keeper agent, reconciliation (`sync --fix`), nightly live-GitHub CI, `docs/github-sync.md`, marketplace.json regen, and feature-complete release.

---

## [1.7.0] — 2026-05-25

Phase 7: LLM augmentation. Adds an `LLMProvider` Protocol with an Anthropic-backed implementation (ephemeral prompt caching on the system block) and a `RecordedLLMProvider` test double, wires opt-in `--use-llm` flags into `plan`, `score`, and `expand`, and ships a brainstorm skill that bridges to `fakoli-flow:brainstorm`. The deterministic planning engine is unchanged — LLM enrichment is strictly additive and falls back cleanly on missing key, missing recording, or mid-operation failure.

### Added

- `bin/src/fakoli_state/planning/llm.py` — `LLMProvider` Protocol + `AnthropicProvider` (with ephemeral prompt-caching on the system block per the claude-api skill guidance) + `RecordedLLMProvider` for deterministic tests + `LLMResponse` Pydantic model + `LLMProviderError`. Default model: `claude-sonnet-4-6`; API key sourced from `ANTHROPIC_API_KEY` env var.
- `--use-llm` flag on `fakoli-state plan`, `score`, and `expand`. Off by default — opt-in augmentation that enriches deterministic output (score explanations, short task descriptions, sub-task proposals for complex tasks).
- `bin/src/fakoli_state/planning/inference.py::expand_task` — new function returning `list[SubtaskProposal]`. Deterministic path returns `[]`; with provider + `complexity >= 4`, calls LLM to propose 2-5 sub-tasks. JSON-parse-tolerant; malformed responses fall back to `[]` with a warning.
- `plugins/fakoli-state/skills/brainstorm/SKILL.md` — interview-style PRD authoring skill. Bridges to `fakoli-flow:brainstorm` when installed; standalone otherwise.
- `docs/llm.md` — provider config, prompt-caching usage, `RecordedLLMProvider` test pattern, failure modes.
- 46 new tests: 29 in `tests/test_llm.py` (provider unit tests), 17 in `tests/test_llm_integration.py` (engine integration via `RecordedLLMProvider`), plus 10 new CLI flag tests in `tests/test_cli.py`.

### Changed

- `planning.scoring.score_task` / `score_all` — new kw-only `provider: LLMProvider | None = None`. Default behavior unchanged.
- `planning.template.parse_prd` — new kw-only `provider: LLMProvider | None = None`. Default behavior unchanged.
- LLM failures during augmentation print a warning to stderr; the engine returns the deterministic-only result. LLM augmentation never aborts a planning operation.

### Technical notes

- One ephemeral cache breakpoint on the system block per Anthropic call. Repeated `score --use-llm` runs against the same task batch hit the cache and pay only for new user tokens.
- `RecordedLLMProvider` keys are `sha256(system + "\n---\n" + user)` — tests pre-compute via `RecordedLLMProvider.record_key(...)`.

Tests: 613 → 640 + Wave 3a additions (Wave 3a may add a few more — total to be confirmed at sentinel time).

---

## [1.6.0] — 2026-05-25

Phase 6: MCP server. Exposes 13 agent-facing tools via FastMCP (stdio), wires them into Claude Code via `.mcp.json`, adds the `progress.noted` audit event, and ships 50 MCP integration tests. Any agent in a project with fakoli-state installed now has direct programmatic access to the full state engine without shelling out to the CLI.

### Added

- `bin/src/fakoli_state/mcp_server.py` — FastMCP (stdio) server with 13 agent-facing tools. Read-only tools: `get_project_summary`, `list_tasks`, `get_task`, `get_next_task`, `generate_work_packet`, `check_conflicts`, `get_dependency_graph`. Mutating tools: `claim_task`, `release_task`, `renew_claim`, `submit_progress`, `submit_completion_evidence`, `update_task_status`. Stale-claim reaping runs at the top of `get_project_summary` and all six mutating tools. The server opens a fresh `SqliteBackend` per tool call (`Path.cwd() / .fakoli-state`) — agents in different cwds see their own state, no leakage.
- `plugins/fakoli-state/.mcp.json` — wires `fakoli-state-mcp` as a stdio MCP server via `${CLAUDE_PLUGIN_ROOT}/bin/fakoli-state-mcp`. Claude Code agents in any project with this plugin installed automatically see the 13 tools.
- `progress.noted` event action — audit-only, structurally parallel to `file_changed`. New `ProgressNotedPayload` in `state/payloads.py` and a no-op handler in `sqlite.py`. Emitted by `submit_progress`.
- `docs/mcp.md` — 645-line full tool reference covering each tool's signature, return shape, error cases, integration notes for fakoli-flow / fakoli-crew, and the documented error envelope contract.
- 50 new MCP integration tests in `tests/test_mcp.py` via the FastMCP in-process Client. 2 additional `progress.noted` payload tests in the existing payload test suite.

### Changed

- `bin/fakoli-state-mcp` — wrapper now executes `python -m fakoli_state.mcp_server` via `uv run` (fully functional). The Phase-6 "not yet implemented" guard block is removed.

### Technical notes

- Error envelope: tools raise `fastmcp.exceptions.ToolError(message)` with a human-readable string. The spec's structured `{code, message, target_id, payload}` envelope is deferred — the documented contract lives in `docs/mcp.md`.
- The process-per-request connection pattern keeps the server a thin shim. No shared in-process state, no connection pooling concerns across concurrent agent calls.

Tests: 530 → 580 (+50 MCP integration tests, +2 payload tests). Ruff clean.

---

## [1.5.0] — 2026-05-25

Phase 6 prep: backend / state-engine refactors that unblock the MCP server
(landing next in Phase 6 proper) by closing the five must-fix items from the
PR #41 critic and Greptile reviews tracked as P6-1..P6-5 in
`docs/tech-debt-backlog.md`.

### Added

- `bin/src/fakoli_state/cli/` — new package replacing the 2,499-line `cli.py`
  monolith. Per-command modules: `init_status`, `prd`, `plan`, `claim`,
  `packet_apply`, `hooks`, plus `_helpers` for shared utilities and
  `__init__.py` as the Typer-app assembler. Public import path
  (`from fakoli_state.cli import app`) is unchanged. (P6-4)
- `bin/src/fakoli_state/state/payloads.py` — 17 per-action Pydantic v2 payload
  models (`ProjectCreatedPayload`, `PrdParsedPayload`,
  `EvidenceSubmittedPayload`, etc.) all using `ConfigDict(extra="forbid")`.
  `SqliteBackend._apply_mutation` now validates `event.payload_json` against
  the model for `event.action` once before dispatch, replacing the 17-elif
  chain with a `dict[str, (PayloadModel, handler)]` table. Handler signatures
  normalize to `(conn, payload: TypedPayload, event: Event)` — handlers read
  fields via attribute access rather than `payload.get(...)`. (P6-5)
- `Backend` Protocol gains three methods previously only on the SqliteBackend
  reach-through: `get_feature(feature_id)`, `list_events(target_id,
  target_kind, limit)`, `get_latest_evidence(task_id)`. The CLI no longer
  touches `backend._conn` directly; the three call sites in
  `cli/_helpers.py` (`_fetch_recent_events`, `_fetch_latest_evidence`)
  collapse into Protocol calls. (P6-1)
- `PENDING_EVENT_ID = "PENDING"` sentinel on `state.backend`. Callers
  construct events as `Event(id=PENDING_EVENT_ID, ...)` and the backend
  assigns the real `E000001`-format ID inside `apply_event`'s BEGIN IMMEDIATE
  transaction, closing the read-before-lock race that allowed event drops
  under concurrent claim/release. (P6-2)
- 37 new test cases in `tests/test_sqlite.py::TestPayloadValidation`
  covering each payload model's happy path and `extra="forbid"` rejection
  plus dispatch-level `ValidationError` propagation.
- 7 new test cases in `tests/test_sqlite.py::TestBackendProtocolExtensions`
  covering the three new Protocol methods.

### Changed

- All CLI commands and `claims.stale.detect_and_release_stale()` now emit
  events via `PENDING_EVENT_ID` instead of pre-allocating IDs through
  `backend.next_event_id()`. `next_event_id()` remains for backward
  compatibility but is documented as the legacy path.
- `SqliteBackend.apply_event` rewrites `event.id` in place when the sentinel
  is passed and returns the updated event so callers can recover the assigned
  ID without re-querying.

### Removed

- `bin/src/fakoli_state/cli.py` — replaced by the package above. Imports
  resolve identically.
- `TaskStatus.stale` from `state.models` and the corresponding
  `task_to_stale` / `task_stale_to_ready` transitions. The state was
  structurally unreachable — only claims can be stale, and the task returns
  directly to `ready` when the claim is reaped. Task lifecycle ASCII diagram
  in `docs/specs/2026-05-24-fakoli-state-v0.md` updated. CL-16 (claim.stale
  task transition skips the intermediate `stale` state) is resolved as a
  side-effect. (P6-3)
- `cli/_helpers.py::_fetch_recent_events` and `_fetch_latest_evidence` —
  callers now go through the Protocol methods.

### Migration notes

- External code calling `apply_event` should switch to passing
  `Event(id=PENDING_EVENT_ID, ...)` to get race-free ID assignment. Pre-built
  events with concrete IDs still work (the replay path requires this) but the
  pre-allocation path is racy under concurrency.
- Subclasses of `Backend` must implement the three new methods or accept the
  `NotImplementedError` from the Protocol default.
- The CLI external surface (`fakoli-state <subcommand>`) is unchanged.

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
