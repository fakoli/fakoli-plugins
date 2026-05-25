# fakoli-state roadmap

**Last updated:** 2026-05-26 (after Phase 9 → Phase 10 ship + backlog hygiene)
**Source of truth:** this file. Archived phase backlogs at [`phase-9-backlog.md`](phase-9-backlog.md) and [`phase-11-backlog.md`](phase-11-backlog.md) are kept for historical audit only — do not add new items there.
**Companion:** [`tech-debt-backlog.md`](tech-debt-backlog.md) for non-roadmap debt (12 OPEN CL/TQ/PS items from PR #41 critics; tracked by origin PR, closed across phases). Items there are not duplicated here unless a roadmap item naturally touches the same file.

## How this is organized

- **Version target** = which fakoli-state minor release the item is planned for.
  - `next` = could land in the next minor (v1.11 candidate); mostly Phase 10 audit carry-forward — mechanical, low-risk, high-leverage.
  - `v2.0` = breaking-change worthy or major capability expansion; provider-protocol scale-out and immediate-apply conflict resolution.
  - `v2.1` = follow-on providers (Jira, GitHub Projects), snapshot subcommand, MCP sync surface.
  - `v2.x` = anytime in the v2 line; doc/composition cleanups and hygiene that don't need a fixed release.
  - `unscheduled` = wanted but not committed; revisit when an adjacent item forces a touch.
- **Theme** = capability group (sync providers, conflict resolution, snapshot/replay, MCP surface, doc agents, hooks, etc.). Themes are durable across versions; an item may shift versions, its theme rarely does.
- **Item IDs** preserved verbatim from origin (`P9B-N` from phase-9-backlog, `P11-XX-XN` from phase-11-backlog) so commit messages, audit cross-references, and the [Phase 10 audit](audits/2026-05-26-plugin-audit.md) stay stable. Every ID in the archived backlogs appears here exactly once (except P11-SK-S5, see [Closed / shipped](#closed--shipped-cross-reference)).

**Status legend** (carried over from origin files):
`OPEN` = unscheduled within target; `TARGETED-VN.M` = scheduled for that release; `SPEC-FIRST` = needs a design doc before implementation; `Phase 11` = Phase 10 audit defer, picks up in the next planning pass.

---

## Version: next (v1.11 / v2.0 candidate)

These are the Phase 10 plugin-audit deferrals — 56 live items the five critics raised at SHOULD FIX, CONSIDER, or NIT severity. None are breaking. The bulk close as mechanical batches; see [Cross-cutting themes](#cross-cutting-themes-high-leverage-batches) for the recommended welder fan-out.

### Theme: Audit honesty (mutating-tool input validation)

- **[P11-MC-S1]** All 6 mutating MCP tools (`mcp_server.py:459-464,526-530,572-576,679-684,733-741,972-977`) accept actor as plain `str` with no non-empty validation; empty actor persists into audit trail at every emitted event. Add `_require_actor(name, field="actor") -> str` helper near `_resolve_state_dir`; call as first line of every mutating tool body. _Single helper closes 6 sites; highest forensics-criticality._
- **[P11-MC-S2]** `list_tasks.status: str | None` not constrained — typo like `"in-progress"` or `"DONE"` returns silently empty list. Replace with `Literal[...]` matching `TaskCountsByStatus` fields verbatim.
- **[P11-MC-S4]** `get_next_task` accepts `actor` parameter but never uses it — contract lie. Remove from signature. _Trivial; schema-truthfulness win._

### Theme: MCP schema fidelity

- **[P11-MC-S3]** Return type `list[dict[str, Any]]` / `dict[str, Any]` strips field-level schema from Claude's view across `list_tasks`, `get_task`, `get_next_task`. Define `TaskSummary` or reuse `Task` Pydantic model from `state.models`; drop `json.loads(model_dump_json())` shim. _Closes P11-MC-N1 simultaneously._
- **[P11-MC-C1]** Every tool re-resolves `Path.cwd()` per call; future `os.chdir()` would silently address different project. Capture `_STATE_DIR` at module import.
- **[P11-MC-C2]** `_reap_stale` swallows all exceptions silently; no surfacing in `claude --debug` traces. Add `logger.warning("stale-claim reaping failed: %s", exc)` inside except. _Adjacent to CL-3 in tech-debt-backlog (`_reap_stale_claims` bare except) — close both in the same patch._
- **[P11-MC-C3]** `WorkPacketResponse.content: Any` allowed but narrower union possible. Switch `Any` → `str | dict[str, Any]`.
- **[P11-MC-N1]** `json.loads(t.model_dump_json())` triple-roundtrips data through JSON. Replace with `t.model_dump(mode="json")`. _Closed automatically by P11-MC-S3._
- **[P11-MC-N2]** `DependencyEdge` constructed with `**{"from": dep_id, "to": t.id}` splat to dodge keyword. Add comment or switch to `DependencyEdge.model_validate(...)`.

### Theme: Skill hygiene (no-fuzzy-detection rule)

See [Theme 1](#theme-1--no-fuzzy-detection-rule-across-skills) for batch-fix leverage notes.

- **[P11-SK-S1]** `skills/execute/SKILL.md:8,15,256` — fuzzy detection for `fakoli-flow:execute`. Add Step 0 `claude plugin list 2>/dev/null | grep -q "^fakoli-flow"`; branch on exit code. Mirror `brainstorm/SKILL.md:48`.
- **[P11-SK-S2]** `skills/finish/SKILL.md:8,245-246` — fuzzy detection for `fakoli-flow:finish`. Add explicit `claude plugin list` check at top of Step 1.
- **[P11-SK-S3]** `skills/claim/SKILL.md:15,250` — fuzzy detection for `fakoli-flow` and `fakoli-crew:welder/scout`. Wrap each "when X is installed" section in shell check or move prose to `references/composition.md`.
- **[P11-SK-S4]** `skills/finish/SKILL.md:177-212` — fuzzy detection for sync provider availability. Replace prose with `test -n "$GITHUB_REPOSITORY"`, `gh auth status >/dev/null 2>&1`, `fakoli-state sync github --health`.
- **[P11-SK-S6]** `skills/brainstorm/SKILL.md:194-197` — fuzzy detection for LLM availability. Add explicit `test -n "$ANTHROPIC_API_KEY"` check; document branches; or move to `references/llm-augmentation.md`.

### Theme: Skill hygiene (phase-status drift)

See [Theme 5](#theme-5--phase-status-table-drift-across-skills).

- **[P11-SK-S7]** `skills/state-ops/SKILL.md:119-132` — phase-availability tables contradict `execute/SKILL.md` (`fakoli-state conflicts` "pending" vs "available"). Reconcile via single `references/phase-status.md`.
- **[P11-SK-S8]** `skills/state-ops/SKILL.md:67-96` — Steps 2 and 3 labeled "Phase 3 — pending" but every other skill uses `list`/`show` as available. Update to "available" matching rest of plugin.
- **[P11-SK-S9]** `skills/state-ops/SKILL.md:1-4` — description is longest in plugin (60+ words), weak trigger phrase. Add concrete trigger phrases in quotes; trim capability list.

### Theme: Skill hygiene (workflow discipline)

- **[P11-SK-C2]** `skills/brainstorm/SKILL.md:70-110` — six-question discipline explicit but stopping rule "material" is interpretive. Add concrete stopping rule — max 1 follow-up if under 5 words, never chain more than 8 total.
- **[P11-SK-C3]** `skills/plan/SKILL.md:107-137` — Step 3 documents Phase 7 limitation as 4-step workflow buried in paragraph. Promote to `### Step 3a — Author subtasks manually` block or extract.
- **[P11-SK-C4]** `skills/prd/SKILL.md:76-84` — Step 1 lacks explicit one-question-per-message discipline (weaker than brainstorm). Mirror brainstorm.
- **[P11-SK-C5]** `skills/execute/SKILL.md:70-84` — Step 2 abort flow happens after packet fetch; dishonest agent skips it. Move Step 2 ahead of packet fetch.
- **[P11-SK-C6]** `skills/finish/SKILL.md:109-116` — `--reason` requirement for `apply --reject` buried in prose. Promote to callout at top of section.

### Theme: Skill hygiene (drive-by NITs)

- **[P11-SK-N1]** `skills/brainstorm/SKILL.md:228` — Phase 7 Notes table cell has `\|` escape that may render literally. Use HTML entity `&#124;`.
- **[P11-SK-N2]** `skills/claim/SKILL.md:138-143` — example ISO timestamp drifts vs `execute/SKILL.md:121`. Pick one wall-clock date or use placeholder.
- **[P11-SK-N3]** `skills/state-ops/SKILL.md:22` — "State-ops is NOT for" sentence repeats 4x in one paragraph. Format as bulleted list.
- **[P11-SK-N4]** `skills/prd/SKILL.md:200-215` — Phase 3 Limitations section duplicates content at lines 39-46. Delete one table or merge columns.

### Theme: Hooks (hot-path perf)

See [Theme 3](#theme-3--hot-path-perf-budget-on-hook-scripts).

- **[P11-HK-S1]** `hooks/check-claim.sh:36-59` — hot-path perf budget violation; spawns `python3` twice (100-300ms) on every Edit/Write/NotebookEdit; exceeds declared 200ms. Consolidate into single `python3 -c` printing both fields; mirror `record-file-change.sh:35-58` pattern.
- **[P11-HK-S2]** `hooks/record-file-change.sh:95-106` — hot-path perf budget violation; `_escape_json()` spawns 4 `python3` instances on fallback path; 5-6 total spawns. Move JSON escaping into original extraction `python3` block; emit pre-escaped values.
- **[P11-HK-N1]** `hooks/record-file-change.sh:55-57` — three `printf … | sed -n 'Np'` invocations; each `sed` is a fork. Replace with single `read` / `mapfile`. _Drive-by during P11-HK-S2._
- **[P11-HK-N2]** `hooks/check-claim.sh:95` — `>/dev/null || true` discards CLI stdout; future structured JSON warning silently dropped. Add inline comment cross-referencing CLI subcommand contract docs. _Drive-by during P11-HK-S1._

### Theme: Hooks (contract documentation)

See [Theme 4](#theme-4--hook-contract-undocumented-at-plugin-level).

- **[P11-HK-S3]** `README.md` / new `hooks/README.md` — non-blocking contract undocumented at plugin/doc level; future maintainer will reintroduce `set -e`. Add hook-contract section. _Single-paragraph fix; high-leverage._

### Theme: Hooks (robustness)

- **[P11-HK-C2]** All four `.sh` files — no diagnostic fallback when hook silently fails. Support `FAKOLI_STATE_HOOK_DEBUG=1` env var redirecting stderr to `.fakoli-state/.hook-debug.log`.
- **[P11-HK-C3]** `hooks/detect-state.sh:29` — `$("$CLI" status --hook-format 2>&1)` merges stderr into status line shown to Claude. Drop `2>&1`; capture separately for diagnostic-fallback branch.
- **[P11-HK-C4]** `hooks/capture-evidence.sh:27` + `check-claim.sh:17` + `record-file-change.sh:14` — implicit assumption hook cwd is project root via relative `STATE_DIR=".fakoli-state"`. Replace with `STATE_DIR="${CLAUDE_PROJECT_DIR:-$PWD}/.fakoli-state"`.
- **[P11-HK-C5]** `hooks/detect-state.sh:14-20` — language detection uses sequential overwrites; polyglot projects mislabeled. Either emit comma-joined list or guard each line. _Cross-plugin coordination opportunity with `fakoli-flow/hooks/detect-context.sh`._

### Theme: Agents (description completeness)

- **[P11-AG-S1]** `agents/critic.md:12-22` — description has only 1 `<example>` block (rubric floor 2; convention 3). Add 2 more with `<commentary>`: one for fakoli-crew fallback path, one for SHOULD-FIX-only verdict.
- **[P11-AG-S2]** `agents/planner.md:12-40` — description has only 2 `<example>` blocks; below 3-example convention. Add a third covering re-planning after PRD rejection / incremental conflict.
- **[P11-AG-S3]** `agents/sentinel.md:12-19` — description has only 1 `<example>` block AND example lacks `<commentary>`. Add 2 more examples + `<commentary>` to every example.
- **[P11-AG-S4]** `agents/sentinel.md:23-28` — `allowed-tools:` used instead of `tools:`. Rename key. _Reviewer may upgrade to MUST FIX for systemic consistency with the 5 Phase 10 MUST FIX agents — costs nothing if bundled with S3/S5._
- **[P11-AG-S5]** `agents/sentinel.md:1-103` — file is 103 lines, at proportionality floor; missing Composition, Inputs, "NOT" boundary, Status File Output sections. Expand to ~140-180 lines mirroring `critic.md` structure.
- **[P11-AG-C4]** `agents/planner.md:76-80` — composition mentions only `fakoli-crew:guido` as defer-to; missing scout/critic acknowledgment. Add one-line note.
- **[P11-AG-N1]** `agents/sentinel.md:103` — missing trailing newline. _Drive-by during P11-AG-S3/S4/S5._

### Theme: Documentation (install messaging, surface counts)

See [Theme 7](#theme-7--install-messaging-drift-in-readme--changelog).

- **[P11-ST-S1]** `README.md:37-48` — install section says "not yet in marketplace" but root `.claude-plugin/marketplace.json` contains v1.9.0 entry. Replace manual-clone paragraph with `/plugin marketplace add fakoli/fakoli-plugins && /plugin install fakoli-state@fakoli-plugins` flow.
- **[P11-ST-S2]** `CHANGELOG.md:7-14` — `[Unreleased]` opens with past-tense summary of v1.9.0; content already lives under dated section. Trim leading sentence; keep forward-looking v2.x notes.
- **[P11-ST-S3]** `.gitignore:7` — covers `bin/.pytest_cache/` but plugin-root `.pytest_cache/` not ignored locally. Add `.pytest_cache/` so rule survives a future repo split.
- **[P11-ST-S4]** `README.md:17,39,49,190` — internally inconsistent install messaging — 4 different phrasings about "once published". Settle on single install story; sweep all 4 sites. _Batches with P11-ST-S1._
- **[P11-ST-C1]** `README.md` (new section near top) — no top-level surface-count table. Add header: "ships 6 agents, 7 skills, 4 hooks, 0 commands, 1 CLI, 1 MCP server with 13 tools."
- **[P11-ST-C2]** `CHANGELOG.md:9-14` — forward-looking v2.x items name LinearIssuesProvider / MondayBoardsProvider / webhooks without issue/PR links. Append `(see docs/roadmap.md § "v2.0" — P9B-1 / P9B-2 / P9B-5)` or equivalent anchor links.
- **[P11-ST-C3]** `README.md:5-7` — minimal badge set; no CI / test-count badges. Add CI status badge (once live-GitHub nightly workflow public) and `tests: 964` count badge.
- **[P11-ST-N1]** `README.md:132` — "Phase 9 (this release, v1.9.0)" parenthetical will stale on v1.10.0 ship. Replace with "Phase 9 shipped in v1.9.0" for tense-stability. _Drive-by during P11-ST-S1/S4._

---

## Version: v2.0 (breaking-change candidates)

The big-ticket capability expansion. Provider-protocol scale-out (Linear, Monday), the conflict-resolution completion (`*_applied` variants), the spec-first webhook listener, and the config-shape transition that enables per-provider settings.

### Theme: Sync providers (multi-provider expansion)

The `SyncProvider` Protocol shipped in v1.8.0 was deliberately registry-driven so contributors can add providers without engine changes. v1.8.0 / v1.9.0 ship `github_issues` only.

- **[P9B-1]** `LinearIssuesProvider` (`linear_issues`). **OPEN, v2.0.** GraphQL-only API; httpx client with respx mocking. Status mapping needs a per-team workflow inspection step. Step-by-step contributor guide already in `docs/sync-providers.md` § "Step-by-step: add Linear support". Acceptance: provider module + GraphQL transport + full-lifecycle respx tests + `.github/workflows/fakoli-state-live-linear.yml` gated on `LINEAR_API_KEY` secret + `fakoli-state sync linear_issues --health` works.
- **[P9B-2]** `MondayBoardsProvider` (`monday_boards`). **OPEN, v2.0.** Monday has people-columns and per-board custom columns; `provider_metadata` dict carries the bulk of the shape. Auth via Monday API key. REST+JSON (Monday's GraphQL is opt-in per workspace). Same acceptance shape as P9B-1.

### Theme: Sync infrastructure (push-based + conflict completion)

- **[P9B-5]** Webhook-based sync (vs polling). **SPEC-FIRST, v2.0.** `--watch` polls every N seconds; for providers that publish webhooks (GitHub, Linear, Monday, Jira), accept push-based sync via a long-running listener. Webhook secret in `.fakoli-state/config.yaml`; HMAC verification on every payload. Needs design doc first: engine's current "one fetch round-trip per task per pass" assumption does not hold under webhooks (out-of-order events, duplicates, races). Spec scope: `fakoli-state webhook-listen --provider X --port 8080` subcommand, event de-duplication via `(provider_id, external_id, last_modified)` tuple, out-of-order queueing with configurable max-delay, per-provider HMAC verification, polling fallback when listener crashes.
- **[P9B-6]** Immediate-apply `*_applied` resolution variants. **TARGETED-V2.0.** Phase 9 T5 deferred wiring `remote_wins_applied` / `local_wins_applied` per TODOs at `cli/sync.py:1054` and `:1068`. Conflict-safety design (re-fetch on moving target, retry/back-off contract) needs specifying first. Acceptance: `remote_wins_applied` calls `_apply_remote_to_local` inline inside the pull loop; `local_wins_applied` calls `provider.push_task(...)` inline with a defined retry/back-off contract for the race where a parallel remote edit lands between decision and push; `*_applied` tokens join the controlled vocabulary in `docs/github-sync.md`; 4+ new tests in `test_cli_sync.py`.

### Theme: Configuration (provider config schemas)

- **[P9B-9]** Provider config schemas in `config.yaml`. **SPEC-FIRST, v2.0** (co-required with P9B-1 Linear). Current `sync.providers` config key is a flat list; as soon as providers need per-provider config (Linear team ID, Monday board ID, Jira project key + workflow map), the flat list becomes a nested map. Design doc decides: does the new map shape coexist with the flat list, or replace it? Migration path: a list of strings is shorthand for "the listed providers with empty config" — keeps v1.9.0 configs valid.

---

## Version: v2.1 (follow-on capability)

### Theme: Sync providers (workflow-aware integrations)

- **[P9B-3]** `JiraIssuesProvider` (`jira_issues`). **OPEN, v2.1.** Jira's workflow/status taxonomy is per-project; provider needs a one-time discovery call to map fakoli-state's 11 `TaskStatus` values to the project's actual statuses. Auth via PAT + email pair. Acceptance: same shape as P9B-1 plus `--discover-statuses` flag that writes the discovered mapping into `.fakoli-state/config.yaml` under `sync.providers.jira_issues.status_map`.
- **[P9B-4]** `GitHubProjectsProvider` (`github_projects`). **OPEN, v2.1.** Sibling to `github_issues` but for Projects v2 (the newer board surface). Shares the gh-CLI / httpx transport from `github_issues` but addresses a different remote object kind. Probably co-locates in `sync/providers/github_projects.py`.

### Theme: Snapshot / replay

- **[P9B-7]** `fakoli-state snapshot` subcommand. **OPEN, v2.1.** Phase 5 (v1.4.0) removed the pre-created `.fakoli-state/snapshots/` directory because nothing wrote to it. Intent was always to ship a `sqlite3 .backup` wrapper. Acceptance: `fakoli-state snapshot [--retention 30d|count:N]` writes `.fakoli-state/snapshots/YYYY-MM-DDTHH-MM-SSZ.db`; `--list` shows existing snapshots with size + age; `--restore <name>` restores atomically (temp file, swap via rename); documented in `docs/specs/2026-05-24-fakoli-state-v0.md` § Snapshots.

### Theme: MCP surface (sync tools)

- **[P9B-8]** MCP sync tools surface. **OPEN, v2.1.** MCP server (Phase 6) exposes 13 read/mutate tools but does NOT expose `sync_*` tools. Agents that want sync today must shell out via Bash. Acceptance: 4 new MCP tools — `sync_run(provider, *, direction='both', task_id=None)`, `sync_health(provider)`, `sync_status()`, `sync_reconcile(*, fix=False)`. Tool errors map cleanly to `ToolError(message)` with the same exception classes the CLI handles. Documented in `docs/mcp.md` § Sync tools; tests in `tests/test_mcp.py`.

---

## Version: v2.x (anytime within v2 line)

Hygiene and structural cleanups that don't need a fixed release. Pick up opportunistically when an adjacent welder pass touches the file.

### Theme: Agents (composition deduplication)

See [Theme 6](#theme-6--composition-duplication-across-three-docstate-agents).

- **[P11-AG-C1]** `agents/docs-scribe.md:1-366` — 366 lines (near 400 ceiling); ~60 lines duplicate `marketplace-scribe.md` and `state-keeper.md` composition prose. Extract shared "three doc/state specialists" composition into `docs/specs/internal-agents.md`; link from all three agents.
- **[P11-AG-C2]** `agents/marketplace-scribe.md:1-308` — same composition duplication (lines 144-161, 292-308). Same fix as C1.
- **[P11-AG-C3]** `agents/state-keeper.md:1-293` — same duplication pattern (lines 94-107). Same fix as C1.

### Theme: Skills (subdirectory extraction)

- **[P11-SK-C1]** All 7 `SKILL.md` files — no `references/`, `examples/`, or `scripts/` subdirectories; bodies bundle phase-status tables and composition prose. Extract to `references/phase-status.md`, `references/composition.md`, etc. Closes ~20-30% of SKILL.md body weight. _High leverage — enables Theme 5 (phase-status drift) and Theme 1 (no-fuzzy-detection) batches._

### Theme: Hooks (concurrency hardening)

- **[P11-HK-C1]** `hooks/capture-evidence.sh:232` + `record-file-change.sh:113` — race-prone append on shared files (`events.jsonl`, `orphan.json`); JSON records can exceed `PIPE_BUF` when `STDOUT_EXCERPT` is near `MAX_EXCERPT=4000`. Add `flock` guard OR document at-most-rare interleave and have replay tolerate truncation. _May defer further to v2.x sync-hardening pass._

---

## Version: unscheduled (wanted, not committed)

Items that have a clear fix shape but no compelling forcing function. Revisit when an adjacent item forces a touch on the same file or when a config-driven matcher framework lands.

### Theme: Hooks (config-driven matchers)

- **[P11-HK-N3]** `hooks/capture-evidence.sh:119-128` — hardcoded verification-command pattern list; Phase 6+ TODO already flagged. Track as deferred config-driven matcher. _Aligned with `tech-debt-backlog.md` CL-10 (`capture-evidence.sh` + `gates.py` pattern sets not aligned)._

---

## Cross-cutting themes (high-leverage batches)

Items spanning multiple critics/areas that benefit from cohesive treatment. These come from the [Phase 10 audit](audits/2026-05-26-plugin-audit.md) and supersede the "items by critic" view when planning Phase 11 welder fan-out. Each theme is welder-sized and self-contained.

### Theme 1 — No-fuzzy-detection rule across skills

**Closes:** P11-SK-S1, P11-SK-S2, P11-SK-S3, P11-SK-S4, ~~P11-SK-S5~~, P11-SK-S6 (originally 6 SHOULD FIX items; **5 live** — P11-SK-S5 closed in Phase 10 Fix #6, see [Closed / shipped](#closed--shipped-cross-reference)).
**Pattern:** every skill that conditionally bridges to fakoli-flow, fakoli-crew, a sync provider, or LLM augmentation uses prose-only "when X is installed" framing without a `claude plugin list 2>/dev/null | grep -q "^X"` shell check. `brainstorm/SKILL.md:48` and `finish/SKILL.md:249-254` (the Phase 10 Fix #6 closure) are the reference implementations every other skill should mirror.
**Welder effort:** ~3 lines per site, 5 sites — single welder pass, ~50 minutes.

### Theme 2 — Non-empty actor validation across MCP mutating tools

**Closes:** P11-MC-S1 (1 SHOULD FIX, 6 sites).
**Pattern:** all 6 mutating MCP tools accept `actor: str` / `claimed_by: str` with no `.strip()` non-empty check; empty actor persists into the audit trail.
**Fix shape:** single `_require_actor(name: str, field: str = "actor") -> str` helper near `_resolve_state_dir`; call as first line of every mutating tool body.
**Welder effort:** define helper + 6 one-liners — single welder pass, ~30 minutes.

### Theme 3 — Hot-path perf budget on hook scripts

**Closes:** P11-HK-S1, P11-HK-S2 (and P11-HK-N1 as drive-by).
**Pattern:** `check-claim.sh` spawns python3 twice; `record-file-change.sh` spawns python3 5-6 times. Each cold python3 spawn is 50-150ms; declared budget is 200ms on hot events. Pattern in `record-file-change.sh:35-58` already proves the consolidation works (1 spawn).
**Welder effort:** consolidate each script's extraction + escaping into single python3 round-trip — ~2 hours per script, 2 scripts.

### Theme 4 — Hook contract undocumented at plugin level

**Closes:** P11-HK-S3 (1 SHOULD FIX).
**Pattern:** the non-blocking contract lives only in script-header comments (3/4 hooks have identical "Rules: no set -e, no piped grep, always exit 0, complete in < 200ms" comments) but is absent from README and `docs/`. Future maintainer who hasn't read every script will reintroduce `set -e` and silently break PreToolUse.
**Fix shape:** new `hooks/README.md` OR `docs/hooks.md` section OR README "Hooks" row expansion. Single paragraph: "All fakoli-state hooks are non-blocking: must `exit 0` regardless of internal failure, must not use `set -e`/`set -u`/`set -o pipefail`, must wrap CLI calls with `|| true`, and must complete in < 200ms on hot events. SessionStart hook may take up to 1s."
**Welder effort:** ~15 minutes.

### Theme 5 — Phase-status table drift across skills

**Closes:** P11-SK-S7, P11-SK-S8 (2 SHOULD FIX); enabled by P11-SK-C1 (extract to `references/`).
**Pattern:** `fakoli-state conflicts` is "pending" in state-ops, "available" in execute. `list`/`show` are "pending" in state-ops Step 2/3 but available in every other skill. State-ops is the laggard; the plugin is at v1.9.0 / Phase 10 per the brief.
**Fix shape:** single source of truth at `references/phase-status.md` (or `docs/phase-status.md`); skills link to it instead of inlining tables.
**Welder effort:** create reference doc + update 7 SKILL.md references — ~2 hours.

### Theme 6 — Composition duplication across three doc/state agents

**Closes:** P11-AG-C1, P11-AG-C2, P11-AG-C3 (3 CONSIDER).
**Pattern:** docs-scribe, marketplace-scribe, and state-keeper each carry near-identical "three doc/state specialists inside fakoli-state" composition tables. If the split ever changes, three files need to update in lockstep.
**Fix shape:** extract to `docs/specs/internal-agents.md`; agents link to it.
**Welder effort:** ~1 hour.

### Theme 7 — Install messaging drift in README + CHANGELOG

**Closes:** P11-ST-S1, P11-ST-S2, P11-ST-S4, P11-ST-N1 (3 SHOULD FIX + 1 NIT).
**Pattern:** README has 4 different phrasings about "once published"; CHANGELOG `[Unreleased]` narrates the just-shipped v1.9.0; README has stale "Phase 9 (this release)" parenthetical. All four are downstream effects of v1.9.0 shipping without a docs-scribe sweep.
**Fix shape:** single README sweep + CHANGELOG trim. Single docs-scribe pass.
**Welder effort:** ~1 hour.

---

## Closed / shipped (cross-reference)

Items that originated in the archived backlogs but have already shipped, kept here for cross-reference traceability.

| ID | Title | Closed in |
|---|---|---|
| **P11-SK-S5** | `skills/finish/SKILL.md:247-252` — fuzzy detection for `fakoli-crew:sentinel`; no shell check | **Phase 10 Fix #6** — welder closed this as a bonus while fixing the dangling `/fakoli-state:sentinel` slash-command reference at the same lines. Removed the broken snippet AND added the `claude plugin list 2>/dev/null \| grep -q "^fakoli-crew"` shell gate (mirroring `brainstorm/SKILL.md:48`), with explicit branches for exit-0 (dispatch fakoli-crew:sentinel) vs non-zero (fall through to plugin-local sentinel agent). See [`docs/plans/agent-welder-t11-status.md`](plans/agent-welder-t11-status.md) § "Fix 6 approach" for the welder's full decision rationale. |
| P9-1 | Audit-event honesty — `sync.pull.completed` emitted on deferred branches | Phase 9 T5 |
| P9-2 | `local_moved`-only path set `sync_state="in_sync"` instead of `local_ahead` | Phase 9 T5 |
| P9-3 | `SyncAuditPayload` single all-optional model accepted nonsense | Phase 9 T3 |
| P9-4 | `RecordedLLMProvider.record_key` ignored `max_tokens` / `temperature` | Phase 9 T6 |
| P9-5 | Brainstorm-flow bridge used fuzzy detection | Phase 9 T6 |
| P9-6 | `expand --use-llm` had no `--format prd` UX | Phase 9 T6 |
| P9-7 | Multi-provider config — no way to opt out of every sync provider | Phase 9 T5 |
| P9-8 | Two new plugin-owned doc agents — `marketplace-scribe`, `docs-scribe` | Phase 9 T4 |

See [`tech-debt-backlog.md`](tech-debt-backlog.md) § "Phase 8 / Phase 9 closures (sync + LLM cleanups)" for the full implementation detail and test counts on P9-1..P9-8.

---

## Companion: tech-debt-backlog.md (not duplicated here)

These items remain owned by [`tech-debt-backlog.md`](tech-debt-backlog.md) and are not duplicated into roadmap scope unless a roadmap item naturally touches the same file. Listed here for cross-reference only.

| ID | Source | Status |
|---|---|---|
| CL-1, CL-2, CL-3, CL-4, CL-5, CL-8, CL-10, CL-11, CL-12, CL-13 | PR #41 critics | OPEN |
| TQ-1, TQ-2, TQ-3, TQ-4, TQ-6, TQ-7, TQ-8 | PR #41 Critic-4 | OPEN |
| PS-1 | PR #41 Critic-2 | OPEN |

**Adjacency hint:** Phase 10 finding **P11-MC-C2** (silent `_reap_stale` exception swallow) is adjacent to **CL-3** (`_reap_stale_claims` bare except). The welder closing P11-MC-C2 should consider closing CL-3 in the same patch. Phase 10 finding **P11-HK-N3** (`capture-evidence.sh` hardcoded matcher list) is aligned with **CL-10** (`capture-evidence.sh` + `gates.py` pattern sets not aligned).
