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
- 7 specialist agents: guido, critic, scout, smith, welder, herald, keeper
- `/crew` command listing agents and basic crew compositions
- Agent frontmatter with `model: sonnet` default and `allowed-tools` declarations
- Each agent with role definition, trigger phrases, and behavioral rules
