# Changelog

## 2.8.0 (2026-06-10)

### Added
- `references/status-file-schema` section in `communication.md`: formal required/optional fields, valid statuses, and orchestrator validation rules — malformed status files become NEEDS_REVIEW instead of silently consumed. Also fixes a real drift: `BLOCKED` was missing from the documented status enum even though fakoli-flow's wave engine has always polled for it
- `references/scout-template.md`: standard structure for scout reference files (VERIFIED vs DOCUMENTED fact marking, exact-strings-over-paraphrase rules); scout now points at it
- `references/critic-checklist.md`: the full evolvable review checklist, extracted from the critic prompt; new SHOULD FIX items (silent fail-open, concurrency assumptions)

### Changed
- **critic**: prompt slims to the inline MUST FIX safety floor + an instruction to Read the full checklist reference before each review — checklist growth no longer requires an agent version bump, and the safety floor applies even if the reference is unavailable
- **sentinel**: documented the Haiku model choice and the orchestrator's sonnet-override escape hatch for oversized validations (partial-output reads must be declared, never verdicted on)
- **guido**: polyglot detection quantified — ≥80% one language auto-detects silently, 50–79% auto-detects with a statement, below 50% asks; replaces the ambiguous "comparable file counts" heuristic
- **keeper**: Iron Rule boundary clarified — files you edit (in full) plus files your edit directly references; not transitive reads of everything a workflow invokes

### Added
- **critic**: two-stage review order — Stage 1 spec compliance (each acceptance criterion located in code and cited file:line; unmet criteria are MUST FIX labeled `[SPEC]`), Stage 2 the existing code-quality checklist. Adopted from superpowers' spec-compliance/code-quality review split: leading with quality lets a review polish its way past a missing requirement
- **sentinel**: scorecards now end with a machine-readable fenced-JSON verdict block (`{"verdict", "pass", "fail", "na", "failures": [{"check", "fix_owner"}]}`) so orchestrators (fakoli-flow, scripts, CI) can branch on results without scraping prose
- **scout**: gained the Bash tool for read-only live verification — `curl -sI` liveness checks on documented endpoints, header inspection for version/deprecation signals, grep over changelogs/lockfiles. GET/HEAD against public surfaces only; every reference fact now marked VERIFIED (observed this session) or DOCUMENTED (docs claim it)

---

## 2.6.0 (2026-06-02)

### Added
- Added Cursor companion files under `.cursor/agents/` for all 8 crew roles, mirroring the existing `.codex/agents/` pattern. Each points at the canonical `agents/<role>.md` prompt as the source of truth, so Claude Code behavior is unchanged.
- Mapped the read-only roles (`critic`, `sentinel`) to Cursor's `readonly: true` subagent flag — the closest faithful equivalent to their Claude `tools:` allowlists, since Cursor does not honor per-subagent tool allowlists.
- Added `.cursor-plugin/plugin.json` so the plugin installs natively via Cursor's plugin marketplace (auto-discovers `.cursor/agents/`, `skills/`, `commands/`).

### Changed
- Companion `model` is set to `inherit` (Cursor uses the user-selected model); exact per-role Cursor model IDs are deferred until verified against a live Cursor install.
- Updated `docs/getting-started.md` to document the three-harness model/selection split (Claude / Codex / Cursor).

## 2.5.0 (2026-06-02)

### Added
- Added OpenAI/Codex custom-agent companion files under `.codex/agents/` with OpenAI-specific `model` and `model_reasoning_effort` selections for all 8 crew roles.
- Added a root regression test covering both Claude agent frontmatter model tiers and OpenAI/Codex custom-agent model mappings.

### Changed
- Restored Claude-specific agent frontmatter model tiers: `guido`/`critic` use `opus`, core build/research/docs/infra agents use `sonnet`, and `sentinel` uses `haiku`.
- Updated `docs/getting-started.md` to document the split between Claude model selection and OpenAI/Codex model selection.

## 2.4.0 (2026-06-01)

### Changed
- Agents write status files to the orchestrator-provided path (default `.fakoli/runs/<run-id>/`), no longer hardcoded `docs/plans/`.

---

## 2.3.0 (2026-05-26)

Minor release. Five plugin-surface critic agents move to a dedicated plugin so plugin-development teams can install only the review layer; everything else in fakoli-crew is unchanged.

### Removed — five plugin-surface critics moved to `fakoli-plugin-critic`

- `agents/agent-critic.md` — now at `fakoli-plugin-critic/agents/agent-critic.md`.
- `agents/skill-critic.md` — now at `fakoli-plugin-critic/agents/skill-critic.md`.
- `agents/hook-critic.md` — now at `fakoli-plugin-critic/agents/hook-critic.md`.
- `agents/mcp-critic.md` — now at `fakoli-plugin-critic/agents/mcp-critic.md`.
- `agents/structure-critic.md` — now at `fakoli-plugin-critic/agents/structure-critic.md`.

Agent system prompts are byte-for-byte unchanged in the extraction — only the namespace moved. Recipes that dispatched via `fakoli-crew:<critic>` must update the prefix to `fakoli-plugin-critic:<critic>` AND install the new plugin. The remaining 8 generalist agents (guido, critic, scout, smith, welder, herald, keeper, sentinel) are not affected.

### Changed

- `plugin.json` description switched from "thirteen specialist AI agents" to "eight specialist AI agents" with a note pointing at `fakoli-plugin-critic` for the moved critics.
- `README.md` agent table collapses from 13 rows to 8; a migration callout above the table explains the move.
- `tests/RECIPES.md` + `tests/test_critics.sh` updated to dispatch the five critics via the new namespace.

### Why

Plugin-development teams that only want the audit layer were previously forced to install the 8-agent generalist crew alongside. Splitting the layers lets each plugin be installed independently — `fakoli-crew` for engineering work, `fakoli-plugin-critic` for plugin-surface audits, both together for full coverage. The five critics are tightly coupled to plugin internals (manifest schema, hook contract, MCP server shape, etc.) and not used outside plugin-dev contexts, so the split is a clean cleavage.

## 2.2.0 (2026-05-26)

Minor release: adds 5 new cross-plugin specialist critic agents and the
`tests/` infrastructure to verify them. Existing 8 agents (guido, critic,
scout, smith, welder, herald, keeper, sentinel) are unchanged. The new
critics extend fakoli-crew from "team of generalist engineering reviewers"
to "team of generalist + 5 plugin-development specialists" so the crew can
review the surface of any Claude Code plugin (its own or any other).

First subject of the new audit pass was fakoli-state v1.9.0 — see
`plugins/fakoli-state/docs/audits/2026-05-26-plugin-audit.md` for the full
findings and `plugins/fakoli-state/CHANGELOG.md` § 1.10.0 for the welder
closures.

### Added — 5 new cross-plugin specialist critic agents

- `agents/agent-critic.md` (color: **magenta**, model: opus, tools: Read, Grep, Glob) — reviews `<plugin>/agents/*.md`. Checks: frontmatter validity (name/description/color/model/tools), color-collision detection across siblings, description-must-have-3-`<example>`-blocks-each-with-`<commentary>` discipline, `allowed-tools:` vs `tools:` antipattern (silently-ignored command-key on agent files), allowed-tools tightness (no `Bash` on review-only agents), defer-to validity (no dangling references), model selection appropriateness, file-length proportionality.
- `agents/skill-critic.md` (color: **teal**, model: opus, tools: Read, Grep, Glob) — reviews `<plugin>/skills/*/SKILL.md`. Checks: frontmatter validity (`name:` + triggering `description:`), one-question-at-a-time discipline, hard-gate presence on irreversible actions, decision-flow diagram presence for skills with 3+ steps, lazy-loading discipline (body short; supporting material in `references/`), the no-fuzzy-detection rule (`if X seems available` is SHOULD FIX; explicit `claude plugin list | grep -q "^X"` shell check is the bar), referenced paths must exist on disk.
- `agents/hook-critic.md` (color: **gray**, model: opus, tools: Read, Grep, Glob, Bash) — reviews `<plugin>/hooks/*.sh` + `hooks.json`. Checks: shebang must be `#!/usr/bin/env bash`, `${CLAUDE_PLUGIN_ROOT}` usage for plugin-internal paths, no-piped-grep antipattern (use `jq` for JSON), stdin handling correctness (PostToolUse reads stdin; SessionStart doesn't), idempotency, performance on hot events (PreToolUse fires per Edit/Write), `hooks.json` matcher patterns + event-name validity + command file existence. **Critical contract-awareness rule:** before flagging `set -e` or its absence, hook-critic MUST detect the plugin's hook contract by reading `hooks.json` and the plugin's docs for "non-blocking" language. If non-blocking (e.g., fakoli-state): `set -e` is MUST FIX. If standard: `set -euo pipefail` absence is SHOULD FIX.
- `agents/mcp-critic.md` (color: **white**, model: opus, tools: Read, Grep, Glob) — reviews `.mcp.json` + MCP server implementation source. Checks: `.mcp.json` schema validity (`mcpServers.<name>.type/command/args`), `${CLAUDE_PLUGIN_ROOT}` in `args` for portable resolution, tool `@mcp.tool()` decorations with `description=` strings, typed parameter annotations (no untyped `Any` without justification), structured error returns (no raw `repr()` or unstructured exceptions), no secret-leak in audit prints or returned strings, stdio vs sse transport choice rationale, actor-identification requirement on mutating tools (non-empty actor validation).
- `agents/structure-critic.md` (color: **brown**, model: opus, tools: Read, Grep, Glob, Bash) — reviews `plugin.json` manifest + marketplace.json entry + registry index entry + README surface tables + CHANGELOG Keep-a-Changelog discipline + version-string sync across every source of truth (plugin.json, pyproject.toml if Python, `__init__.py` if Python, marketplace.json entry, registry/index.json entry). Bash needed for running `scripts/generate-index.sh --check` and version-grep across multiple files. **Standalone** — does NOT delegate to `plugin-dev:plugin-validator`.

Color collisions checked vs the existing 8 agents (guido=blue, critic=red, scout=cyan, smith=orange, welder=green, herald=pink, keeper=purple, sentinel=yellow). The 5 new critic colors (magenta, teal, gray, white, brown) are all unused by every existing crew agent, so the 13-agent palette has no duplicates.

### Added — `tests/` infrastructure

fakoli-crew is a pure-markdown plugin (no `pyproject.toml`, no Python module) and had no test directory prior to this release. Phase 10 scaffolds it bash-first, matching the precedent set by `plugins/fakoli-state/tests/test_hooks.sh`:

- `tests/README.md` (NEW) — conventions doc: bash-only (zero pip dependencies inherited from the test suite), script layout, the manual-verification model (bash cannot dispatch a Claude Code subagent from a shell context — agent invocation happens inside a session by following the recipe).
- `tests/fixtures/audit-targets/` (NEW) — 5 deliberately-broken plugin fixtures, one per critic. Each contains exactly one antipattern its critic must surface at MUST FIX severity:
  - `bad-agent.md` — missing `name` frontmatter; uses `allowed-tools:` instead of `tools:`.
  - `bad-skill.md` — vague description ("a skill that helps with things"); no decision flow.
  - `bad-hook.sh` + `bad-hooks.json` — `set -e` against an adjacent `hooks.json` documenting a non-blocking contract; no `${CLAUDE_PLUGIN_ROOT}` usage on plugin-internal path.
  - `bad-mcp.json` — `.mcp.json` missing the `args` field.
  - `bad-plugin.json` — `plugin.json` missing `version`; `description` shorter than the spec floor.

  Each fixture starts with a leading comment block enumerating its antipatterns and the expected severities so future maintainers do not accidentally "fix" the deliberate bugs.

- `tests/RECIPES.md` (NEW) — one section per critic. Lists (a) which fixture to feed it, (b) the exact Agent dispatch one-liner, (c) the expected severity tokens to look for in the resulting status file, (d) pass/fail interpretation.
- `tests/test_critics.sh` (NEW, executable) — recipe-printer bash runner. `--list` outputs each critic + fixture + expected severity + RECIPES.md pointer. Safe to add to CI as a smoke check that the recipe table stays in sync with the critic roster. Does NOT attempt to dispatch Claude Code agents from bash (impossible from a shell context).

### README

- Agent table grows from 8 rows to 13 rows: existing 8 agents unchanged in rows 1-8; 5 new critic agents (agent-critic, skill-critic, hook-critic, mcp-critic, structure-critic) added as rows 9-13 with one-line trigger-phrase descriptions matching the existing column format.

---

## 2.1.1 (2026-05-25)

Cleanup patch on top of 2.1.0. Resolves remaining critic CONSIDER/NIT items.

### Fixed
- `agents/welder.md`: split the welder-specific TDD rule from the Iron Rule pointer onto its own paragraph so the two rules cannot drift into one over time
- `skills/debugging/SKILL.md`: converted the bare code-formatted `references/case-studies.md` path into a proper markdown link, matching the cross-reference style used elsewhere in the plugin
- `skills/crew-ops/references/iron-rule.md`: appended a one-line note explaining why `scout` and `sentinel` are absent from the bound-agents list (scout is read-only by role; sentinel does not modify source files)
- `CHANGELOG.md`: corrected the 2.1.0 "Frontmatter compliance" bullet which had the field-rename direction reversed (the actual change was `allowed-tools:` → `tools:`, not the other way around)
- `agents/critic.md`: restored the critic-specific debugging-methodology rule ("Never suggest 'try changing X' without first completing Phases 1-3") which the 2.1.0 Iron Rule deduplication accidentally removed because it was filed under a section header named "The Iron Rule" — but was semantically different from the canonical read-before-edit Iron Rule (which critic already has as the "Non-Negotiable Rule" at the top of the file). The rule is now restored as "Critic's Debugging Rule", mirroring how welder's TDD rule was preserved (Greptile finding P2)

---

## 2.1.0 (2026-05-25)

Review-fix minor release. Agent semantics and workflow logic are unchanged — all changes are frontmatter compliance, color normalization, deduplication through shared references, and trigger phrase improvements.

### Frontmatter compliance
- All 8 agent files (`guido`, `critic`, `scout`, `smith`, `welder`, `herald`, `keeper`, `sentinel`): renamed the no-op `allowed-tools:` field to the canonical `tools:` field per official Claude Code agent frontmatter spec; switched `model: sonnet` → `model: inherit` to defer model selection to the caller
- Added `<commentary>` blocks to all 8 agent files explaining behavioral intent behind key frontmatter and prompt decisions
- Deduplicated Iron Rule prose across all 8 agent files by pointing to the shared `skills/crew-ops/references/iron-rule.md` reference instead of repeating inline text

### Color normalization
- Fixed `herald` agent color: `magenta` → `pink` (magenta is not a valid Claude Code agent color)

### Deduplication via shared references
- New reference file `skills/crew-ops/references/iron-rule.md` — canonical Iron Rule wording shared by all agents
- New reference file `skills/crew-ops/references/agent-roster.md` — canonical agent roster shared by commands and skills
- New reference file `skills/debugging/references/case-studies.md` — concrete debugging case studies extracted from the debugging skill body

### Trigger phrases
- `skills/crew-ops/SKILL.md`: added trigger phrases to frontmatter, rewrote opening sentence in imperative form, split Skills section, added pointer to agent roster reference
- `skills/debugging/SKILL.md`: added trigger phrases to frontmatter, added link to `case-studies.md` reference

### New references
- `skills/crew-ops/references/iron-rule.md`
- `skills/crew-ops/references/agent-roster.md`
- `skills/debugging/references/case-studies.md`

---

## 2.0.1 (2026-05-24)

Evaluation-audit patch release. No agent semantics, tool allowlists, or workflow logic changed — all fixes are documentation, frontmatter, and structural.

### Fixed
- Dangling reference pointers in `guido` and `welder` agents that cited
  `references/*.md` paths which did not exist in those agents' directories; updated
  to point at the actual reference files under `skills/crew-ops/references/`
- Added `crew-ops` skill to the README Skills table — it shipped in 2.0.0 but was
  missing from the table

### Changed
- Resolved agent color collisions: `keeper` green→purple, `sentinel` red→orange. All
  8 agents now have unique colors (blue, cyan, green, magenta, orange, purple, red,
  yellow)
- `debugging` and `crew-ops` skills: added `name:` frontmatter, rewrote descriptions
  in third-person trigger form, converted debugging's second-person "When to Use"
  block to imperative form
- `crew-ops` SKILL.md cites reference files inline by name (`wave-patterns.md`,
  `file-ownership.md`, `communication.md`, plus the four language-style references)
- `/crew` command metadata: added `argument-hint`, expanded description to mention
  task-aware crew suggestion, cross-referenced the `crew-ops` skill, and refreshed
  the agent color column to match the new collision-free palette
- Standardized "read-before-modify" Iron Rule wording in `smith`, `guido`, `keeper`,
  and `herald` to match the existing `welder`/`critic` phrasing
- Documented `smith` ↔ `keeper` routing boundary explicitly in each agent
- Tightened `guido`'s polyglot guidance to require asking which subsystem the
  request targets rather than silently defaulting
- Replaced fragile `../../fakoli-flow/...` relative links in `docs/*` with absolute
  GitHub URLs that resolve in both GitHub-rendered and installed-plugin contexts

---

## 2.0.0 (2026-04-02)

### Added
- **sentinel** agent — QA engineer with evidence-based pass/fail scorecards; every PASS
  cites a command output, every FAIL names a fix owner
- **debugging skill** — systematic 4-phase root cause analysis used automatically by
  critic, welder, and sentinel when diagnosing failures (`skills/debugging/SKILL.md`)
- **crew-ops skill** — internal orchestration skill for multi-agent wave coordination
  (`skills/crew-ops/SKILL.md`) with reference library:
  - `wave-patterns.md` — wave execution patterns with real BAARA Next examples
  - `communication.md` — status file protocol and inter-agent coordination
  - `file-ownership.md` — file ownership rules preventing concurrent edit conflicts
  - `guido-style.md`, `python-style.md`, `rust-style.md` — language style guides
  - `welder-patterns.md` — integration patterns in TypeScript, Python, and Rust
- **flow-protocol.md** — formal contract between fakoli-crew agents and any compatible
  orchestrator (agent dispatch protocol, status file format, wave compatibility table,
  capabilities registry)
- **parallel-execution.md** — guide to dispatching multiple agents simultaneously
- **getting-started.md** — onboarding guide with real-world BAARA Next examples
- **Pre-Built Crews** in `/crew` command: Code Quality, Plugin Development, Research &
  Build, Documentation Sprint, Full Overhaul

### Changed
- Agent count: 7 → 8 (added sentinel)
- Wave pattern formalized to 5 waves with standing critic gate after every code wave
- Plugin description updated to reflect full agent roster and debugging capability

---

## 1.0.0 (initial release)

### Added

**8 specialist agents** — each with a defined role, system prompt, trigger phrases, behavioral rules, `model: sonnet` default, and an explicit `allowed-tools` declaration:

| Agent | Role |
|-------|------|
| **guido** | Polyglot software architect (TypeScript, Python, Rust) — interface design, type system patterns, test-first methodology |
| **critic** | Staff Engineer code reviewer — MUST FIX / SHOULD FIX / CONSIDER / NIT severity ratings; reads every file before commenting |
| **scout** | Researcher — API documentation, codebase mapping, dependency investigation, pattern inventory |
| **smith** | Plugin engineer — plugin.json manifests, commands, hooks, Claude Code plugin structure |
| **welder** | Integration engineer — wires new code into existing systems, backward-compatible refactors, TDD enforced |
| **herald** | Documentation writer — READMEs, marketplace descriptions, user-facing copy |
| **keeper** | Infrastructure engineer — CLAUDE.md, CI workflows, contributor docs, registry sync |
| **sentinel** | QA engineer — evidence-based pass/fail scorecards; every PASS cites a command output, every FAIL names a fix owner |

**Wave-based execution model** — agents run in 5 structured waves with a standing critic gate after every code-writing wave:

```
Wave 1: scout (research — no code written)
Wave 2 (parallel): guido + smith + herald (build)
  ── CRITIC GATE ──
Wave 3: welder (integrate)
  ── CRITIC GATE ──
Wave 4: sentinel (final verification)
Wave 5: keeper (infrastructure) + orchestrator reviews findings
```

**Pre-built crew compositions** — four ready-to-use team configurations for common scenarios:

- **Code Quality** (`guido + critic + sentinel`) — audit and improve an existing codebase: critic finds issues, guido rewrites them idiomatically, sentinel verifies nothing regressed
- **Plugin Development** (`smith + guido + sentinel + herald`) — scaffold a new plugin through three waves: scout researches patterns, smith and guido build in parallel, sentinel and herald validate and document
- **Research & Build** (`scout + guido + welder`, critic as gate) — integrate an unfamiliar library or API: scout maps it, guido designs the wrapper, welder wires it in
- **Full Overhaul** (all 8 agents) — major version bumps and structural refactors across all five waves with critic as standing gate throughout

**File ownership protocol** — each agent declares the files it owns per session; concurrent edits to the same file are prevented at the protocol level, not caught after the fact

**Inter-agent communication via status files** — agents write `docs/plans/agent-<name>-status.md` on completion, including status (`COMPLETE` / `BLOCKED` / `NEEDS_REVIEW`), files modified, decisions made, and notes for downstream agents; the next wave's dispatch prompts are built from these files

**`/crew` command** — lists all 8 agents with roles and invocation triggers, then suggests the appropriate pre-built crew or custom wave composition for the user's current task
