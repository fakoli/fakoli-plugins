---
description: Show fakoli-flow's 6 skills, the workflow pipeline, and the currently detected project state (language, crew availability). Takes no arguments — use `/flow:<skill-name>` to actually trigger a skill.
argument-hint: ""
allowed-tools:
  - Bash
---

List all available fakoli-flow skills with their commands and purposes, display the
workflow pipeline, then run detect-context.sh to show the current project state.

## How invocation works

`/flow` (no suffix) is this menu — it shows what's available and the current project context, but does not run a skill. To run a skill, invoke it directly by name: `/flow:brainstorm`, `/flow:plan`, `/flow:execute`, `/flow:verify`, `/flow:finish`, or `/flow:quick`. The harness routes these to the matching `skills/<name>/SKILL.md` file. Arguments accepted by each skill (spec path, plan path, free-form task) are listed in the table below.

## Skills

| Skill | Command | Purpose |
|-------|---------|---------|
| Brainstorm | `/flow:brainstorm` | Design phase — refine ideas into specs through collaborative dialogue |
| Plan | `/flow:plan` | Plan phase — break approved specs into intent-driven task lists for crew execution |
| Execute | `/flow:execute` | Execute phase — wave-based crew dispatch with critic gates and evidence-based verification |
| Verify | `/flow:verify` | Verify phase — evidence-based validation with sentinel dispatch and pass/fail scorecard |
| Finish | `/flow:finish` | Ship phase — merge, PR, keep, or discard with pre-merge verification |
| Quick | `/flow:quick <task>` | Fast path — skip the full workflow for small tasks under 3 files |

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

The SessionStart hook runs `detect-context.sh` automatically when a session begins and
prints the detected language and crew availability to the session context. Running `/flow`
re-detects context on each invocation, so the output always reflects the current project
state — no need to scroll back to the start of the conversation.

```
[fakoli-flow] Language: TypeScript | Crew: fakoli-crew 2.0.0 | Skills: brainstorm, plan, execute, verify, finish, quick
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
