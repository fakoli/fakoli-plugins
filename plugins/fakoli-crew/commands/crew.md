---
description: List all 9 fakoli-crew agents with roles, and (if a task is supplied) suggest a crew composition tailored to that task. Pairs with the `crew-ops` skill, which handles multi-agent orchestration once a crew is chosen.
argument-hint: "[optional task description]"
allowed-tools:
  - Bash
---

List all 9 fakoli-crew agents with their roles, then suggest crew compositions for the user's current task (passed as the command argument, if any).

For deeper orchestration — wave patterns, file ownership, status-file protocol — invoke the `crew-ops` skill (triggers: "assemble a crew for…", "coordinate agents to…").

## All Agents

See [`skills/crew-ops/references/agent-roster.md`](../skills/crew-ops/references/agent-roster.md) for the canonical 9-agent roster (names, colors, roles, and file paths).

## Pre-Built Crews

### Code Quality
**Agents:** guido + critic + sentinel (+ warden when the change touches auth, input handling, dependencies, or plugin permissions)
**Use when:** You want to audit and improve an existing codebase.
```
1. critic audits — finds issues, assigns severity
2. guido rewrites — fixes MUST and SHOULD items with idiomatic TypeScript alternatives
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
**Agents:** scout + guido + welder (critic as gate)
**Use when:** Integrating an external library or API you haven't used before.
```
Wave 1: scout (read the docs, map the API)
Wave 2: guido (design the wrapper/interface)
  ── CRITIC GATE ──
Wave 3: welder (wire into existing code)
  ── CRITIC GATE ──
```

### Documentation Sprint
**Agents:** herald + keeper + sentinel
**Use when:** Docs are stale, READMEs are generic, or the registry is out of sync.
```
Wave 1: herald (rewrite READMEs with specific value propositions)
  ── CRITIC GATE ──
Wave 2: keeper (sync CLAUDE.md, marketplace.json, registry)
Wave 3: sentinel (verify counts match, links resolve)
```

### Full Overhaul
**Agents:** All 9 in waves (critic as standing gate, warden as security gate)
**Use when:** Major version bump, structural refactor, or preparing for public launch.
```
Wave 1:             scout (research)
Wave 2 (parallel):  guido + smith + herald (build)
  ── CRITIC GATE ──
Wave 3:             welder (integrate)
  ── CRITIC GATE ──
Wave 4 (parallel):  sentinel (final verification) + warden (security audit)
Wave 5:             keeper (infrastructure) + orchestrator reviews findings
```

## Usage

To invoke an individual agent:
```
/agent:guido Design an interface for the new storage backend.
/agent:sentinel Validate everything before we tag v2.0.0.
/agent:herald Rewrite the README for fakoli-tts.
```

To use the crew skill for multi-agent orchestration, trigger it with phrases like:
- "assemble a crew for..."
- "use the crew to..."
- "coordinate agents to..."
