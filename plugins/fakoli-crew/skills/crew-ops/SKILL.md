---
description: Orchestrate fakoli-crew agents as coordinated teams for complex multi-step projects
---
# Crew Operations

## Available Agents

| Agent | Role | Best For |
|-------|------|----------|
| guido | TypeScript architect | Interface design, type system patterns, project structure |
| critic | Code reviewer | Quality audits, finding bugs, import analysis |
| scout | Researcher | API docs, codebase exploration, technical references |
| smith | Plugin engineer | Manifests, hooks, commands, plugin structure |
| welder | Integration engineer | Refactoring, wiring new code into existing systems |
| herald | Documentation writer | READMEs, descriptions, branding, user-facing copy |
| keeper | Infrastructure engineer | CI/CD, CLAUDE.md, contributor docs, registry |
| sentinel | QA engineer | Testing, validation, verification scorecards |

## Pre-Built Crews

- **Code quality**: guido + critic + sentinel
- **Plugin development**: smith + guido + sentinel + herald
- **Research & build**: scout + guido + welder (critic as gate)
- **Full overhaul**: all 8 in waves

## Skills

| Skill | Purpose |
|-------|---------|
| `/crew` | List agents and crew compositions |
| Debugging | Systematic 4-phase root cause analysis (see `skills/debugging/SKILL.md`) |

## Wave Pattern

1. **Research**: scout gathers information
2. **Build** (parallel): guido + smith + herald create new artifacts
   - **── CRITIC GATE ──** critic reviews all modified files (non-negotiable)
3. **Integrate**: welder wires it together
   - **── CRITIC GATE ──** critic reviews the integration
4. **Final Verification**: sentinel produces evidence-based scorecard
5. **Infrastructure + Judge**: keeper syncs infra, orchestrator reviews findings

**Critic is a standing gate, not a wave agent.** It fires after every wave that writes code.

### Compressed 3-Wave Pattern (for smaller tasks)

For tasks with 1-5 file changes, collapse to 3 waves:
1. **Build** (parallel): appropriate agents create/modify
2. **── CRITIC GATE ──** critic reviews
3. **Verify**: sentinel validates

Use the full 5-wave pattern when >5 files change or multiple concerns overlap.

## File Ownership

Each agent owns specific files. No two agents modify the same file. If overlap is needed,
one agent is primary and the other coordinates via status files.

## Communication

Agents write status to `docs/plans/agent-<name>-status.md`:
- Status: IN_PROGRESS | COMPLETE | NEEDS_REVIEW
- Decisions: key choices other agents need to know
- Files Modified: list of changed files

See references/ for detailed patterns.
