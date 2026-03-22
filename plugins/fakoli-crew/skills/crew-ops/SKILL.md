---
description: Orchestrate fakoli-crew agents as coordinated teams for complex multi-step projects
---
# Crew Operations

## Available Agents

| Agent | Role | Best For |
|-------|------|----------|
| guido | Python architect | Interface design, code structure, Pythonic patterns |
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
- **Research & build**: scout + guido + welder + critic
- **Full overhaul**: all 8 in waves

## Wave Pattern

1. **Research** (parallel): scout agents gather information
2. **Build** (parallel): guido + smith create new code/structure
3. **Integrate** (sequential): welder wires it together
4. **Review** (parallel): critic + sentinel validate
5. **Judge** (main window): review findings, send back if needed

## File Ownership

Each agent owns specific files. No two agents modify the same file. If overlap is needed,
one agent is primary and the other coordinates via status files.

## Communication

Agents write status to `docs/plans/agent-<name>-status.md`:
- Status: IN_PROGRESS | COMPLETE | NEEDS_REVIEW
- Decisions: key choices other agents need to know
- Files Modified: list of changed files

See references/ for detailed patterns.
