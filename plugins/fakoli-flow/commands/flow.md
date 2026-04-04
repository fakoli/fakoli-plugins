---
description: Show fakoli-flow skills and current project state
allowed-tools:
  - Bash
---

List all available fakoli-flow skills with their commands and purposes, display the
workflow pipeline, then run detect-context.sh to show the current project state.

## Skills

| Skill | Command | Purpose |
|-------|---------|---------|
| Brainstorm | `/flow:brainstorm` | Design phase — refine ideas into approved specs, one question at a time |
| Plan | `/flow:plan` | Plan phase — translate an approved spec into an intent-driven task list |
| Execute | `/flow:execute` | Build phase — wave-based crew dispatch with critic gates after every code wave |
| Verify | `/flow:verify` | Check phase — sentinel runs evidence-gated acceptance criteria scorecard |
| Finish | `/flow:finish` | Ship phase — re-verify tests, then choose: merge / PR / keep / discard |
| Quick | `/flow:quick <task>` | Fast path — single agent + critic for small bounded changes (under 3 files) |

## Workflow

```
brainstorm → plan → execute → verify → finish
                                  ↑
                           quick ──┘  (skips brainstorm, plan, and execute waves)
```

`quick` is the fast path for bug fixes, parameter changes, and typo corrections.
Use the full pipeline when you need a spec, want wave-based parallelism, or the
change touches 3+ files.

## Project State

Run the SessionStart hook to show detected language and crew availability:

```bash
bash /Users/sdoumbouya/.claude/plugins/cache/fakoli-plugins/fakoli-flow/1.0.0/hooks/detect-context.sh
```

## Usage Examples

Start a design session:
```
/flow:brainstorm  →  "Design a retry mechanism with exponential backoff"
```

Jump straight to planning from an existing spec:
```
/flow:plan  →  "docs/specs/2026-04-04-retry-mechanism.md"
```

Execute an approved plan:
```
/flow:execute  →  "docs/plans/2026-04-04-retry-mechanism.md"
```

Verify work before shipping:
```
/flow:verify
```

Choose final disposition:
```
/flow:finish
```

Fix something small right now:
```
/flow:quick "add a timeout parameter to the retry function"
```
