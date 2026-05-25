# Changelog

All notable changes to fakoli-state are documented here. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

v1.8.0 ships feature-complete v0 per the spec at
docs/specs/2026-05-24-fakoli-state-v0.md. Future minor bumps will
land additional sync providers (Monday, Linear, Jira), webhook-based
sync (vs polling), and the Phase 9 immediate-apply conflict resolution
wired to `*_applied` audit events.

---

## [1.8.0] — 2026-05-25

Phase 8: bidirectional sync. Adds a multi-provider `SyncProvider` Protocol
abstraction with GitHub Issues as the first concrete implementation, wires
opt-in `fakoli-state sync` CLI surface with bidirectional push/pull, four
conflict-resolution strategies, watch-loop polling, and full reconciliation
between SQLite state / filesystem / git. The Protocol is registry-driven
so Monday, Linear, Jira, and custom providers can plug in without engine
changes — see docs/sync-providers.md for the contributor guide.

The schema gains a sync_mappings table (SCHEMA_VERSION 2 → 3) with an
auto-upgrade path for existing v1.7.x databases; the diff is purely
additive. See docs/migrations.md.

### Added — Sync abstraction layer

- `bin/src/fakoli_state/sync/` package — `SyncProvider` Protocol (`push_task`, `fetch_task`, `list_tasks`, `delete_task`, `health_check`), `ExternalRef` + `ExternalTask` + `ProviderHealth` Pydantic models, `SyncProviderError` hierarchy (`AuthenticationFailed`, `RateLimitExceeded`, `ProviderUnavailable`, `SyncConflict`), `RecordedSyncProvider` test double (sha256 length-prefixed keyed), `PROVIDER_REGISTRY` + `register_sync_provider` / `get_sync_provider` / `list_sync_providers`. snake_case `provider_id` discipline.
- `bin/src/fakoli_state/sync/providers/github_issues.py` — `GitHubIssuesProvider` concrete impl. Auto-registers as `"github_issues"` on package import. Dual transport: `gh` CLI primary, `httpx` + `GITHUB_TOKEN` fallback. Status mapping: 11 TaskStatus values → `status:*` labels; only `done` closes the issue. Body footer convention (`---\n_synced from fakoli-state task {task_id}_`) is round-trippable via `_strip_footer`. Label preservation across pushes (HTTP transport reads existing labels first, preserves non-`status:*`).
- `bin/src/fakoli_state/sync/clients/gh_cli.py` — subprocess wrapper for `gh issue create/edit/view/list/close`. Stderr-scan error classification (auth/rate-limit/network).
- `bin/src/fakoli_state/sync/clients/github_http.py` — httpx wrapper with Link-header pagination + 1000-page safety cap + `responses`-style HTTP mocking via respx in tests.
- `bin/src/fakoli_state/sync/reconciliation.py` — `ReconciliationEngine.scan() / fix(dry_run=False)` covering 6 discrepancy kinds: orphan_branch, orphan_packet, orphan_worktree, stale_claim, missing_sync_mapping, drift_sync_state. The first 4 have full fix paths; the latter 2 emit operator-facing CLI commands (`fakoli-state sync provider <id> --pull --task T001`) for Phase 9 immediate-apply.

### Added — State schema (SCHEMA_VERSION 3)

- `sync_mappings` table: composite PK `(task_id, external_system)` + `UNIQUE(external_system, external_id)` (prevents cross-task collisions) + `FK ON DELETE CASCADE` to tasks + `external_url` + `provider_metadata_json`. Auto-upgrade from v1/v2 dbs in `_check_schema_version`; purely additive.
- New Pydantic models: `SyncMapping`, `SyncState`, `ConflictResolutionStrategy` (enums), `ExternalSystem` (snake_case enum).
- New payload models in `state/payloads.py`: `SyncMappingUpsertedPayload`, `SyncMappingDeletedPayload`, `SyncAuditPayload`. All `extra="forbid"`.
- New event handlers in `state/sqlite.py`: `_handle_sync_mapping_upserted`, `_handle_sync_mapping_deleted`, `_handle_sync_audit` (no-op like file_changed / progress.noted).
- New Backend Protocol methods: `get_sync_mapping(task_id, *, external_system=None)`, `list_sync_mappings(external_system=None)`, `apply_sync_mapping(mapping, *, actor='system')` (uses PENDING_EVENT_ID for race-free assignment).
- Nine new `sync.*` audit-event actions: `sync.batch.started/completed`, `sync.push.started/completed/failed`, `sync.pull.started/completed/failed`, `sync.conflict_detected`.

### Added — CLI surface

- `fakoli-state sync` — runs reconciliation only (scan + print report).
- `fakoli-state sync --fix --yes` — reconciliation + apply remediations (`--yes` required for non-interactive; refuses without `--yes` on cron/CI).
- `fakoli-state sync <provider>` — push+pull all tasks via the named provider.
- `fakoli-state sync github` — backwards-compat alias for `sync github_issues`.
- `fakoli-state sync provider <id>` — generic provider invocation.
- Flags: `--push` (push-only), `--pull` (pull-only), `--task T001` (single-task), `--watch --interval N` (long-running poll loop with per-iteration error recovery), `--health` (provider auth probe, works pre-init), `--fix` (forces remote_wins conflict strategy).
- Conflict resolution: per-task `SyncMapping.conflict_resolution_strategy` ∈ {`local_wins`, `remote_wins`, `prompt`, `manual_merge`}. Resolution events emit `*_deferred` audit strings (truthful — actual mutations happen on the next pass; Phase 9 will wire immediate apply). `manual_merge` writes `.fakoli-state/.sync-conflicts/<task_id>.md`; batch exits 2 if any task needed operator input.

### Added — Plugin-owned agent

- `plugins/fakoli-state/agents/state-keeper.md` (color `teal`, model `opus`) — specialized agent for sync drift detection + reconciliation triage. Defers to `fakoli-crew:keeper` when crew is installed.

### Added — Documentation

- `docs/github-sync.md` (245 lines, 12 sections) — user-facing GitHub Issues sync reference.
- `docs/sync-providers.md` (280 lines, 11 sections) — contributor-facing Protocol reference with a step-by-step Linear-provider walkthrough.
- `docs/live-tests.md` — operator runbook for the nightly live-GitHub CI.
- `docs/migrations.md` — already shipped in 1.7.1; documents the v1/v2 → v3 auto-upgrade.

### Added — Nightly CI

- `.github/workflows/fakoli-state-live-github.yml` — daily cron at 06:00 UTC. Gated on `secrets.FAKOLI_STATE_TEST_GH_TOKEN` (job exits 0 with a notice if secret missing). Runs `pytest -m live_github -v` against a real test repo.
- `tests/test_github_issues_live.py` — 3 live tests (lifecycle, label preservation, rate-limit handling). All decorated `@pytest.mark.live_github`; excluded from default `pytest -q` via `addopts = "-m 'not live_github'"` in pyproject.toml. Cleanup contract: every test closes its own issues + leaves a `[fakoli-test]` UUID prefix for orphan sweeping.

### Changed

- `bin/pyproject.toml` — dropped unused `responses>=0.25` dev dep; added `httpx>=0.27` runtime; added `respx>=0.21` dev (for httpx-side HTTP mocking); registered `live_github` pytest marker.
- `cli/__init__.py` — wires the new `sync_app` Typer sub-app into the main CLI.

### Tests

- 750 → 917 baseline tests (+167) plus 3 live-github tests (excluded from default).
- Across waves: 58 sync_provider tests, 23 sync_mapping tests, 82 github_issues_provider tests, 37 reconciliation tests, 42+ cli_sync tests, 4 follow-up + Wave 3 fix-cycle additions.
- Ruff clean. Migration auto-upgrade path tested for v0/v1/v2 → v3.

### Migration notes

- Schema bumps 2 → 3. Existing v1.7.x databases auto-upgrade on first `fakoli-state` invocation under 1.8.0. The diff is purely additive (new table, no shape changes to existing tables). No manual action required.
- The `responses` dev dep has been dropped; if you have a custom test that imported it, switch to `respx` for httpx mocking.
- `fakoli-state sync` is a NEW command. Existing CLI commands are unchanged.

---

## [1.7.1] — 2026-05-25

Backlog cleanup. Closes 14 items from the deferred review backlog
(`docs/tech-debt-backlog.md`) — 6 correctness fixes (welder), 5 doc/config
cleanups, and the leftover deferrals from the PR #47 critic review. No
behavior changes visible to existing CLI / MCP callers.

### Fixed (correctness — welder backlog wave)

- CL-1: `hooks/check-claim.sh` now invokes the `hook check-claim --file --actor` CLI subcommand (Phase 5) instead of parsing `status --hook-format` output (Phase 4 leftover that fired on any claim regardless of file scope).
- CL-3: `_reap_stale_claims` no longer swallows `SchemaMismatch`; narrowed catch to `(StateLocked, TransactionAborted)` so DDL drift surfaces loudly.
- CL-8: `_handle_evidence_submitted` rejects double-submit with a different `evidence_id` for the same claim; emits the established `warn.idempotent_no_op` JSONL tombstone instead of inserting a duplicate row.
- CL-11: `planning.template.parse_prd` accepts an optional `clock: Clock`; `_parse_tasks` now requires a clock injection instead of calling `datetime.now()` directly.
- CL-13: `SqliteBackend.next_event_id` now raises `RuntimeError` via `_require_conn()` instead of returning the hardcoded `"E000001"` when the connection is closed — eliminates the silent collision-on-reopen footgun.
- PS-1: `ClaimManager._check_group_conflicts` collapses 1+N round-trips into 2 via a single bulk `list_tasks()` + in-memory `dict[task_id, Task]` lookup.

### Fixed (small cleanups)

- CL-7: `agents/critic.md` and `agents/sentinel.md` color collisions with fakoli-crew — state/critic purple → magenta, state/sentinel cyan → gray.
- CL-9: `review.gates._contains_test_keyword` no longer matches `pytest --collect-only` / `--co` (zero-test runs were satisfying the "tests pass" evidence gate).
- CL-14: `skills/finish/SKILL.md` text updated — the apply flow emits a single `task.applied` event, not the nonexistent `review.created` + `task.status_changed` pair.
- PS-2: `init` no longer pre-creates `.fakoli-state/snapshots/`; the directory will be created on first use when `fakoli-state snapshot` ships.

### Fixed (PR #47 critic deferrals)

- S2 / Greptile-G1 (already in 1.7.0): noted closed.
- S5: `template.DESCRIPTION_SHORT_THRESHOLD` is now public; CLI `plan --use-llm` help text references the constant rather than the literal "50".
- N1: comment in `parse_prd` clarifies that HTML-comment stripping runs before the LLM augmentation pass.
- N2: `parse_prd`'s reserved `prd_id` parameter now uses `# noqa: ARG001` instead of the `_ = prd_id` discard idiom.
- N3: `planning.llm._DEFAULT_MODEL` carries a "Last verified" date comment so future maintainers know when to refresh.
- N5: removed the unused `responses>=0.25` dev dependency (the test suite mocks the anthropic SDK at the `unittest.mock` level since `anthropic` uses `httpx`, not `requests`).

### Documentation

- `docs/evidence-buffer.md` (NEW) — format, lifecycle, orphan.json policy, sentinel interaction, cleanup. Closes CL-15.
- `docs/tech-debt-backlog.md` status markers updated: P6-1..P6-5 marked DONE (closed in PR #44); CL-7/CL-9/CL-14/CL-15/PS-2 DONE (this PR); TQ-5 DONE (PR #42 fixup).

### Tests

- 639 → 653 pytest tests (+14): 6 for CL-9 collection-only exclusion, 3 for CL-3 SchemaMismatch propagation, 1 for CL-8 double-submit guard + strengthened existing CL-8 test, 2 for CL-11 clock injection, 1 for CL-13 require-conn guard, 1 for PS-1 N+1 → 2 query collapse.
- 18 → 21 bash hook tests (+3 for CL-1 invocation surface).

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
