---
description: Show available fakoli-crew agents and team compositions
allowed-tools:
  - Bash
---

List all 8 fakoli-crew agents with their roles, then suggest crew compositions for the
user's current task.

## All Agents

| Agent | Color | Role | Invoke When |
|-------|-------|------|-------------|
| guido | blue | Python architect | Designing interfaces, writing new modules, Pythonic refactors |
| critic | red | Code reviewer | Quality audits, finding bugs, import analysis, severity ratings |
| scout | cyan | Researcher | API docs, codebase exploration, dependency investigation |
| smith | green | Plugin engineer | plugin.json, commands, hooks, manifest structure |
| welder | yellow | Integration engineer | Wiring new code into existing systems, backward-compat refactors |
| herald | magenta | Documentation writer | READMEs, marketplace descriptions, branding, user-facing copy |
| keeper | green | Infrastructure engineer | CLAUDE.md, CI workflows, contributor docs, registry sync |
| sentinel | red | QA engineer | Test runs, validation scorecards, pre-release checks |

## Pre-Built Crews

### Code Quality
**Agents:** guido + critic + sentinel
**Use when:** You want to audit and improve an existing codebase.
```
1. critic audits — finds issues, assigns severity
2. guido rewrites — fixes MUST and SHOULD items with Pythonic alternatives
3. sentinel validates — runs tests, confirms nothing regressed
```

### Plugin Development
**Agents:** smith + guido + sentinel + herald
**Use when:** Building a new plugin or adding major features to an existing one.
```
Wave 1: scout (research existing patterns)
Wave 2: smith (manifest) + guido (code)
Wave 3: sentinel (validate) + herald (README)
```

### Research & Build
**Agents:** scout + guido + welder + critic
**Use when:** Integrating an external library or API you haven't used before.
```
Wave 1: scout (read the docs, map the API)
Wave 2: guido (design the wrapper/Protocol)
Wave 3: welder (wire into existing code)
Wave 4: critic (review the integration)
```

### Documentation Sprint
**Agents:** herald + keeper
**Use when:** Docs are stale, READMEs are generic, or the registry is out of sync.
```
Wave 1: herald (rewrite READMEs with specific value propositions)
Wave 2: keeper (sync CLAUDE.md, marketplace.json, registry)
Wave 3: sentinel (verify counts match, links resolve)
```

### Full Overhaul
**Agents:** All 8 in waves
**Use when:** Major version bump, structural refactor, or preparing for public launch.
```
Wave 1 (parallel): scout + critic
Wave 2 (parallel): guido + smith + herald
Wave 3 (sequential): welder
Wave 4 (parallel): critic + sentinel
Wave 5 (main): review scorecard, dispatch fixes
```

## Usage

To invoke an individual agent:
```
/agent:guido Design a Protocol for the new storage backend.
/agent:sentinel Validate everything before we tag v2.0.0.
/agent:herald Rewrite the README for fakoli-tts.
```

To use the crew skill for multi-agent orchestration, trigger it with phrases like:
- "assemble a crew for..."
- "use the crew to..."
- "coordinate agents to..."
