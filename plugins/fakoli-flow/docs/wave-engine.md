# The Wave Engine

How fakoli-flow orchestrates multi-agent execution with intent-driven plans.

## Overview

The wave engine is the execution core of fakoli-flow. It reads an intent-driven plan (acceptance criteria, not implementation code), groups tasks into dependency-ordered waves, dispatches specialist agents in parallel within each wave, and enforces critic gates between waves.

The result: complex multi-package, multi-concern projects get built by coordinated specialist agents with quality verified at every stage — without a human manually dispatching each agent.

## How It Works

```
/flow:execute

┌─────────────────────────────────────────────────┐
│  1. Load plan file                              │
│  2. Detect available agents (fakoli-crew?)      │
│  3. Group tasks into waves by dependencies      │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │  For each wave:        │◄──────────────────────┐
          │                        │                       │
          │  a. Dispatch agents    │                       │
          │     (parallel)         │                       │
          │                        │                       │
          │  b. Wait for all to    │                       │
          │     complete           │                       │
          │                        │                       │
          │  c. Handle BLOCKED /   │                       │
          │     NEEDS_REVIEW       │                       │
          │                        │                       │
          │  d. Run verification   │                       │
          │     (typecheck/lint)   │                       │
          │                        │                       │
          │  e. Run critic gate    │──── MUST FIX? ────────┘
          │                        │     dispatch welder
          │  f. Proceed to next    │     re-run critic
          │     wave               │
          └────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │  Final sentinel        │
          │  verification          │
          └────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │  Report summary        │
          └────────────────────────┘
```

## Wave Assignment

### From Dependencies

Each task in the plan can declare dependencies:

```markdown
### Task 5: Wire retry into orchestrator

**Intent:** Connect the retry module to the orchestrator's failure handling path.
**Depends on:** Task 3 (retry module), Task 4 (queue manager)
**Agent:** welder
```

The wave engine reads these and auto-groups:
- Tasks with no dependencies → Wave 1 (all run in parallel)
- Tasks depending only on Wave 1 tasks → Wave 2 (all run in parallel)
- Tasks depending on Wave 2 → Wave 3
- And so on

Tasks within the same wave are independent — they can run in parallel without conflict.

### Default Pattern (No Dependencies Declared)

When the plan doesn't declare explicit dependencies, the wave engine uses the crew's natural wave pattern:

```
Wave 1 — Research (parallel):
  scout tasks: read docs, explore codebase, map dependencies
  
Wave 2 — Build (parallel):
  guido tasks: design interfaces, create new modules
  smith tasks: manifests, commands, plugin structure
  herald tasks: documentation drafts

Wave 3 — Integrate (sequential):
  welder tasks: wire new code into existing systems

Wave 4 — Review (parallel):
  critic: code review with severity ratings
  sentinel: test suite, validation scorecard

Wave 5 — Fix cycle (if needed):
  welder: fix MUST FIX findings from critic
  critic: re-review → PASS required to proceed
```

This default pattern was proven across 6 phases of the BAARA Next project (44,268 lines, 218 files).

## Agent Dispatch

Each task names its agent. The wave engine dispatches via Claude Code's Agent tool:

```
Agent(
  subagent_type = "fakoli-crew:welder",
  model = "sonnet",
  prompt = """
    Task: Wire retry into orchestrator
    
    Intent: Connect the retry module to the orchestrator's failure handling path.
    
    Acceptance criteria:
    - Failed executions trigger retry with exponential backoff
    - Retries exhausted → route to DLQ
    - Each retry creates a new execution attempt
    
    Scope: packages/orchestrator/src/orchestrator-service.ts
    
    Upstream context:
    - Task 3 created retry.ts with shouldRetry() and calculateDelay()
    - Task 4 created queue-manager.ts with enqueueTimer()
    
    Verify: bun test — retry scenarios pass
  """
)
```

### What the Agent Receives

The dispatch prompt includes everything the agent needs to work independently:
- **Intent** — what to achieve (from the plan)
- **Acceptance criteria** — how to verify it's done (from the plan)
- **Scope** — which files to focus on (from the plan)
- **Upstream context** — decisions from prior waves (from agent status files)
- **Verify command** — how to confirm success (from the plan)

The agent does NOT receive:
- Implementation code (it decides how)
- The full plan (only its task)
- Other agents' conversation history (each agent has fresh context)

### Graceful Degradation

If fakoli-crew is not installed, the wave engine falls back to generic subagents:

```
Agent(
  subagent_type = "general-purpose",
  prompt = "..." (same task description)
)
```

The execution still works — you just lose the specialized agent expertise (TDD enforcement in welder, style guide awareness in guido, Staff Engineer review depth in critic).

## The Critic Gate

**This is non-negotiable.** After every wave that writes code, the critic reviews all modified files.

### How It Works

1. **Collect modified files.** Read all `docs/plans/agent-*-status.md` files from the completed wave. Extract the "Files Modified" section from each.

2. **Dispatch critic.**
```
Agent(
  subagent_type = "fakoli-crew:critic",
  prompt = "Review these files modified in Wave 2: [file list]. 
            Check against these acceptance criteria: [from plan].
            Report MUST FIX / SHOULD FIX / CONSIDER / NIT."
)
```

3. **Evaluate findings.**
   - **All PASS** → proceed to next wave
   - **SHOULD FIX / CONSIDER / NIT only** → proceed (log findings for later)
   - **MUST FIX found** → enter fix cycle

4. **Fix cycle.**
```
dispatch welder with critic's MUST FIX findings
  → welder fixes
    → re-dispatch critic on the same files
      → if still MUST FIX: repeat (max 3 cycles)
      → if PASS: proceed
      → if 3 cycles exhausted: surface to user as NEEDS_REVIEW
```

### Why Non-Negotiable

In the BAARA Next project, the critic gate caught:
- Phase 1: 10 MUST FIX (state machine violations, broken API contracts, unauthenticated RCE)
- Phase 4: 5 MUST FIX (missing SSE fields, wrong HTTP methods, phantom imports)
- Phase 5: 4 MUST FIX (migration data corruption, missing schemas, wrong counts)

**26 bugs total** that would have compounded into debugging nightmares. Each critic pass takes ~2 minutes. Each bug caught saves hours. The math is obvious.

## Language-Aware Verification

Between the wave completion and the critic gate, the engine runs language-specific verification:

| Language | Verification Command | What It Catches |
|----------|---------------------|-----------------|
| TypeScript | `npx tsc --noEmit` | Type errors, import mismatches |
| Python | `ruff check . && mypy .` | Lint violations, type errors |
| Rust | `cargo check` | Borrow checker, type errors, lifetime issues |
| Any | `<test command from plan>` | Failing tests from the current wave |

The project language is detected by SessionStart hook (Cargo.toml → Rust, pyproject.toml → Python, package.json → TypeScript).

If verification fails, the engine does NOT proceed to the critic — it dispatches welder to fix the verification errors first. There's no point in reviewing code that doesn't compile.

## Quick Mode

For small tasks (<3 files), the full wave engine is overkill. `/flow:quick` provides a fast path:

```
/flow:quick "add a timeout parameter to the retry function"

1. Detect scope — likely 1-2 files
2. Detect language — TypeScript (tsconfig.json found)
3. Dispatch single agent:
   Agent(subagent_type="fakoli-crew:welder", prompt="...")
4. Run verification: npx tsc --noEmit
5. Dispatch critic on modified files
6. If PASS → done
7. If MUST FIX → one fix cycle → done
```

No brainstorming, no planning, no waves. Just: agent → verify → critic → done.

**When to use quick mode:**
- Bug fixes affecting 1-2 files
- Adding a parameter, renaming a function, fixing a typo
- Any task where brainstorming would take longer than the fix

**When NOT to use quick mode:**
- New features spanning multiple files
- Architecture changes
- Anything you'd want a spec for

## Parallel Dispatch at Scale

The wave engine can dispatch many agents in parallel. Real-world examples:

### 2 Agents (Common)
```
Wave 1:
  welder-A: packages/store (Plan A)
  welder-B: packages/core (Plan B)
```

### 3 Agents (Proven in BAARA Next Phase 1)
```
Wave 2:
  welder-1: packages/store + packages/orchestrator
  welder-2: packages/agent + packages/executor
  welder-3: packages/transport + packages/server + packages/cli
```

### 5 Agents (Used in BAARA Next Phase 4)
```
Wave 1:
  welder-A: MCP server (27 tools)
  welder-D: Thread model (schema + CRUD)
  
Wave 2 (after Wave 1):
  welder-B: Chat SSE streaming
  welder-E: CLI mcp-server + chat REPL

Wave 3 (after Wave 2):
  welder-C: Web UI rewrite (20 tasks)
```

Each parallel agent targets different files/packages. The file ownership table prevents conflicts. If two agents accidentally touch the same file, the typecheck gate catches it.

## Status File Protocol

Agents communicate between waves via status files at `docs/plans/agent-<name>-status.md`. The wave engine reads these after each wave to:

1. Confirm all agents completed (status: COMPLETE)
2. Detect blockers (status: BLOCKED — surface to user)
3. Detect escalations (status: NEEDS_REVIEW — surface to user)
4. Extract "Files Modified" for the critic gate
5. Extract "Decisions" and "Notes for Specific Agents" for the next wave's dispatch prompts

The status file format is defined in the fakoli-crew flow protocol (`fakoli-crew/docs/flow-protocol.md`).

## Summary

The wave engine combines three proven patterns:

1. **Intent-driven plans** — agents decide HOW, the plan says WHAT
2. **Parallel wave execution** — independent tasks run simultaneously, dependent tasks wait
3. **Critic gates** — mandatory quality verification between every wave

The result is autonomous multi-agent execution that produces production-quality code — verified at every stage, with human oversight only when an agent escalates.
