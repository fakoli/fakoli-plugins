# Changelog

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
