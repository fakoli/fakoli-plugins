# Using Fakoli Crew with SuperPowers

Fakoli Crew and the SuperPowers plugin complement each other:

- **SuperPowers** provides workflow orchestration: brainstorming → planning → execution → finishing
- **Fakoli Crew** provides specialist agents: guido, critic, welder, etc.

## The Combined Workflow

1. **SuperPowers brainstorming** designs the spec
2. **SuperPowers writing-plans** creates the implementation plan
3. **Fakoli Crew agents** execute the plan tasks (welder builds, critic reviews)
4. **SuperPowers finishing-a-development-branch** merges or creates a PR

## How It Works in Practice

When SuperPowers dispatches a subagent for a task, specify a fakoli-crew agent:

```
Instead of a generic implementer subagent, use:
/agent:welder [task description from the plan]
```

For review steps:
```
/agent:critic Review the implementation against the spec.
```

## Execution Pattern from BAARA Next

The BAARA Next project used this exact combination across 6 phases:

1. SuperPowers brainstorming → design spec (user stories, mockups, architecture)
2. SuperPowers writing-plans → 5 sub-plans with 50 tasks total
3. Fakoli Crew execution:
   - Wave 1: 2 welders in parallel (Plan A + Plan D)
   - Critic review → fix MUST FIX issues
   - Wave 2: 2 welders in parallel (Plan B + Plan E)
   - Critic review → fix MUST FIX issues
   - Wave 3: 1 welder (Plan C)
   - Critic review → PASS
4. SuperPowers finishing → git init, push to GitHub

This produced 218 files, 44K lines, all typecheck clean, 19 smoke tests passing.

## The Future: fakoli-flow

A dedicated workflow orchestration plugin (fakoli-flow) is planned to replace the SuperPowers dependency with crew-aware orchestration. Until then, SuperPowers + fakoli-crew is the recommended stack.
