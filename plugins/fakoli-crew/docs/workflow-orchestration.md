# Workflow Orchestration with fakoli-crew

Fakoli Crew agents execute tasks, but they need an orchestrator to coordinate waves,
enforce critic gates, and manage status files between agents. Two orchestration options
are available.

## Recommended: fakoli-flow

**fakoli-flow** is the crew-aware orchestrator built specifically for fakoli-crew. It
implements the wave protocol defined in `docs/flow-protocol.md` as a first-class plugin.

```bash
claude plugin install fakoli-crew
claude plugin install fakoli-flow
```

With both installed, you get the full pipeline:

```
/flow:brainstorm  →  design spec
/flow:plan        →  task list assigned to crew agents
/flow:execute     →  wave dispatch with critic gates
/flow:verify      →  sentinel acceptance criteria check
/flow:finish      →  merge / PR / keep / discard
```

fakoli-flow knows about every fakoli-crew agent — it dispatches the right specialist for
each task type, enforces file ownership, and runs the critic gate after every code wave.

See [fakoli-flow README](../../fakoli-flow/README.md) and
[fakoli-flow getting-started.md](../../fakoli-flow/docs/getting-started.md) for the full
walkthrough.

## Alternative: SuperPowers

The SuperPowers plugin still works alongside fakoli-crew and is a valid choice if you
prefer its brainstorming and planning UX, or if you are not yet ready to adopt
fakoli-flow.

- **SuperPowers** provides workflow orchestration: brainstorming → planning → execution → finishing
- **Fakoli Crew** provides specialist agents: guido, critic, welder, etc.

### The Combined Workflow

1. **SuperPowers brainstorming** designs the spec
2. **SuperPowers writing-plans** creates the implementation plan
3. **Fakoli Crew agents** execute the plan tasks (welder builds, critic reviews)
4. **SuperPowers finishing-a-development-branch** merges or creates a PR

### How It Works in Practice

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

The BAARA Next project used crew agents for execution across 6 phases:

1. Design spec (user stories, mockups, architecture)
2. Task list → 5 sub-plans with 50 tasks total
3. Fakoli Crew execution:
   - Wave 1: 2 welders in parallel (Plan A + Plan D)
   - Critic gate → fix MUST FIX issues
   - Wave 2: 2 welders in parallel (Plan B + Plan E)
   - Critic gate → fix MUST FIX issues
   - Wave 3: 1 welder (Plan C)
   - Critic gate → PASS
4. Git merge / push to GitHub

This produced 218 files, 44K lines, all typecheck clean, with 26 bugs caught by critic
gates across all 6 phases before they ever ran.

When this project ran, fakoli-flow did not yet exist. Today, fakoli-flow would orchestrate
these same waves automatically via `/flow:execute`.

## Choosing an Orchestrator

| | fakoli-flow | SuperPowers |
|---|---|---|
| Crew-aware dispatch | Yes — assigns agents by task type | No — you specify agents manually |
| Critic gates | Automatic after every code wave | Manual — you invoke `/agent:critic` |
| Status file protocol | Reads/writes automatically | Not integrated |
| Wave management | Built-in 5-wave pattern | Manual sequencing |
| Brainstorm UX | One question at a time | Interactive session |

For new projects, use **fakoli-flow**. For existing SuperPowers workflows, both approaches
work and can be mixed within the same project.
