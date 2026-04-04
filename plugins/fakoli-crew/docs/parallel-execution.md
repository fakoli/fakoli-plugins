# Parallel Agent Execution

The fakoli-crew supports running multiple agents in parallel — not just sequentially in waves.

> **Automated orchestration:** If you are using **fakoli-flow**, the wave engine manages
> parallel dispatch automatically — you do not need to invoke agents manually. See
> [fakoli-flow/docs/wave-engine.md](../../fakoli-flow/docs/wave-engine.md) for how the
> engine groups tasks into waves and dispatches agents in parallel within each wave.

## When to Parallelize

- **Multiple packages** in a monorepo that don't depend on each other
- **Multiple plans** that target different areas of the codebase
- **Research tasks** where scout agents explore independent sources

## How to Dispatch in Parallel

Use the Agent tool with multiple agents in a single message:

```
[Agent 1: welder] Build packages/store following Plan A...
[Agent 2: welder] Build packages/orchestrator following Plan B...
```

Both agents run simultaneously. Each produces its own status file.

## Conflict Prevention

- Each agent targets different files/packages
- The file ownership table determines who writes what
- If two agents need the same file, one is primary and the other communicates via status file

## Typecheck as Gate

After parallel agents complete, run a typecheck before the critic:

```bash
npx tsc --noEmit  # all packages must pass
```

If typecheck fails, the parallel agents made conflicting edits. Fix these before proceeding to critic review.

## Real-World: 3 Parallel Welders

In BAARA Next Phase 1, three welders ran simultaneously:
- Welder 1: packages/store + packages/orchestrator
- Welder 2: packages/agent + packages/executor
- Welder 3: packages/transport + packages/server + packages/cli

All three completed. Typecheck found 0 errors (the agents resolved conflicts during their runs). Critic then reviewed the combined output.
