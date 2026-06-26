# Changelog

All notable changes to the systems-thinking-plugin will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-02

### Added

- **docs/flow-protocol.md** — maps the 3-tier pipeline (Discovery, Extraction, Synthesis) to the fakoli-flow wave model. Defines Wave 1 (web-researcher + extraction-planner), Wave 2 (all five extraction agents in parallel), and Wave 3 (synthesis-brief-writer). Describes what each agent writes in its "Decisions" section so the wave engine can pass findings forward without re-reading all extraction outputs.
- **docs/status-file-template.md** — copy-paste status file template for wave-based execution. Includes status values (IN_PROGRESS / COMPLETE / NEEDS_REVIEW / BLOCKED), per-agent guidance on what to write in "Decisions", and a worked example for caveat-extractor.
- **fakoli-flow compatibility section in README.md** — "Works with fakoli-flow" section explaining how the orchestrator dispatches systems-thinking agents as a wave pipeline, with the wave mapping table and links to the new protocol docs.

### Changed

- **Version bumped** from 0.2.0 to 0.3.0 in plugin.json, pyproject.toml, and VERSION.

## [0.2.0] - 2026-03-14

### Added

- **web-researcher agent** — new discovery agent with WebSearch + WebFetch access for finding external source material (vendor docs, pricing pages, service quotas). Produces a structured Source Manifest for downstream extraction agents. Only agent with web access — all others remain read-only.
- **extraction-planner agent** — new haiku-powered dispatch planning agent that assesses material volume and produces a Dispatch Plan specifying how many extraction agents to spawn, what type each should be, and what scoped instructions each receives. Prevents extractor overload observed in large research sessions.
- **Collection phase in skill workflows** — complexity-mapper and architecture-risk-review now have optional web-researcher + extraction-planner steps before extraction. Context-sharding integrates extraction-planner for per-shard caveat extraction sizing.
- **Regression tests** — `test_skill_frontmatter_has_no_trigger_field` prevents re-introduction of non-standard frontmatter; `test_skill_descriptions_are_long_enough` enforces minimum 250-char descriptions for reliable auto-matching.
- **ORCHESTRATION_AGENTS test category** — web-researcher and extraction-planner are tested as orchestration agents (distinct from extraction and synthesis).
- **LICENSE file** — MIT license added to match manifest declaration.

### Fixed

- **Skill frontmatter** — removed non-standard `trigger` field from all 5 skills (silently ignored by Claude Code). Expanded all descriptions from 77-118 chars to 250-450 chars with specific user trigger phrases.
- **SessionStart hook** — added missing `"timeout": 5` to prevent potential indefinite hangs.
- **pattern-remix SKILL.md** — fixed duplicated `reference/previous_designs/` entry in Step 1.
- **discover-components.sh** — made executable (`chmod +x`) for consistency with other hook scripts.

### Changed

- **complexity-mapper workflow** — new steps: doc-indexer → (optional) web-researcher → extraction-planner → parallel extractors → synthesis. Previously launched extractors directly from doc-indexer output.
- **architecture-risk-review workflow** — added optional web-researcher and extraction-planner steps before caveat-extractor and dependency-mapper.
- **context-sharding workflow** — added optional web-researcher pre-step and extraction-planner for per-shard caveat extraction sizing.
- **decision-brief workflow** — accepts Source Manifests and Dispatch Plans as valid input types.
- **Agent count** — 9 agents (up from 7): 5 extraction, 2 synthesis, 2 orchestration.

## [0.1.3] - 2026-03-14

### Fixed

- **Stop hook false positives:** Quality gate no longer triggers on casual mentions of plugin names — now matches only actual agent/skill invocations in the transcript
- **UserPromptSubmit false positives:** Converted from static prompt hook (fired every message) to command-based gate that only injects the reminder when a systems-thinking skill is explicitly invoked via slash command or an active workflow exists in the transcript
- **Hook keyword duplication:** Extracted shared `discover-components.sh` so both hooks derive skill/agent lists from the directory structure at runtime — no hardcoded lists to drift out of sync

### Added

- `hooks/user-prompt-gate.sh` — scoped prompt injection, only activates on slash-command invocations or active transcript workflows
- `hooks/discover-components.sh` — shared component discovery sourced by both hook scripts; auto-detects new skills and agents

## [0.1.2] - 2026-03-13

### Fixed

- **stop-quality-gate.sh reliability:** Grep transcript file directly instead of loading into a shell variable (avoids `ARG_MAX` failures on large transcripts); dropped `set -e` to prevent silent early exits on `grep || fallback` patterns

## [0.1.1] - 2026-03-12

### Fixed

- **Stop hook scope:** Scoped Stop hook to only fire when systems-thinking components are present in the session transcript
- **Hook prompt errors:** Rewrote Stop hook from prompt type to command type to prevent file-access errors during hook execution

## [0.1.0] - 2026-03-11

### Added

- **7 subagents** in `.claude/agents/`
  - 5 extraction agents: `doc-indexer`, `doc-reader`, `caveat-extractor`, `cost-capacity-analyst`, `architecture-dependency-mapper`
  - 2 synthesis agents: `pattern-remix-planner`, `synthesis-brief-writer`
- **5 skills** in `.claude/skills/`
  - `pattern-remix` — generate first drafts from prior work
  - `complexity-mapper` — surface hidden operational/cost/implementation complexity
  - `context-sharding` — split large source material across parallel agents
  - `decision-brief` — package findings for stakeholders
  - `architecture-risk-review` — targeted failure mode and dependency review
- **2 prompt-based hooks** in `.claude/settings.json`
  - Pre-flight reminder: enforce extraction/synthesis separation
  - Completion quality check: verify assumptions, risks, unresolved questions, next steps
- **5 output contracts** defined in `docs/output-contracts.md`
  - Hidden Risk Summary, Complexity Heat Map, Decision Brief, Pattern Remix Draft, Context Packet
- **Reference directory** (`reference/`) with 4 subdirectories
  - `previous_designs/`, `vendor_docs/`, `prompts/`, `examples/`
  - All agents and skills are aware of and pull from this directory
- **Testing infrastructure** with 182 passing tests
  - Unit tests: hook prompts, YAML frontmatter, file structure
  - Contract tests: plugin layout, agent specs, skill specs, output contracts
  - Eval harness: scenario-based testing with graders (file_exists, section_check, schema_match, forbidden_check, composite)
  - 3 eval cases with realistic fixture documents
- **CI pipeline** via GitHub Actions (`.github/workflows/test.yml`)
  - Unit + contract tests on every PR
  - Eval tests on labeled PRs and nightly schedule
  - Plugin structure validation
- **Documentation**
  - `CLAUDE.md` — project instructions and conventions
  - `README.md` — usage guide with quick start
  - `docs/agent-design-principles.md` — extraction vs synthesis rules
  - `docs/repo-conventions.md` — naming, structure, and output conventions
  - `COMPATIBILITY_NOTES.md` — Cursor adaptation notes
  - `examples/usage-scenarios.md` — 4 worked scenarios
- **Design specs** preserved in `specs/` (00–11 numbered documents)
