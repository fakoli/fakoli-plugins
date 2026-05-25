# Changelog

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
