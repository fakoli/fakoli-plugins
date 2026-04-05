# The Wave Engine: How We Ship 44K Lines of Code with Multi-Agent Teams

Late in 2025 we built BAARA Next — a 10-package TypeScript monorepo for a durable task execution engine. By the end: 44,268 lines of code, 218 files, 19 smoke tests, 6 phases, 0 MUST FIX bugs shipped to production.

Eight AI agents did most of the writing. We did the orchestration.

This post explains the execution model that made it work: wave-based dispatch, critic gates, intent-driven plans, and the specific coordination patterns that let multiple agents build into the same codebase without colliding.

---

## The Problem with Sequential Agent Dispatch

The naive approach to multi-agent development is sequential: dispatch agent A, wait for it to finish, dispatch agent B. This works for small tasks. For a project with 10 interdependent packages and 6 distinct phases, it has two problems.

First, it is slow. If welder-A can build `packages/store` while welder-B builds `packages/agent` — and neither touches the other's files — there is no reason to wait.

Second, sequential dispatch does not force you to think about dependencies. When you have to group tasks into waves, you discover the dependency graph. You realize that `packages/orchestrator` cannot be built until `packages/core` defines the interfaces it depends on. You realize that the web UI cannot be built until the server's SSE endpoints are stable. Making these dependencies explicit up front prevents agents from building against assumptions that will be invalidated by later work.

The wave engine makes dependency structure the organizing principle of execution.

---

## How Waves Work

A wave is a set of tasks that can run in parallel because they have no dependencies on each other within the wave. Tasks in Wave N depend only on the outputs of Wave N-1 (or earlier). Tasks within the same wave target different files or packages entirely.

The engine auto-assigns tasks to waves from declared dependencies:

```markdown
### Task 5: Wire retry into orchestrator

**Intent:** Connect the retry module to the orchestrator's failure handling path.
**Depends on:** Task 3 (retry module), Task 4 (queue manager)
**Agent:** welder
```

Tasks with no declared dependencies run in Wave 1, all in parallel. Tasks depending only on Wave 1 tasks run in Wave 2. And so on.

When dependencies are not declared, the engine falls back to the crew's natural five-wave pattern:

**Wave 1 — Research.** scout reads everything. Maps imports, finds existing patterns, documents the API surface. No code is written in Wave 1. This is the input to every downstream wave.

**Wave 2 — Build (parallel).** guido designs interfaces and type definitions. smith creates or updates manifests and plugin structure. herald drafts documentation. These three run simultaneously because they target different files.

**Critic gate.** Before Wave 3 starts, critic reviews every file modified in Wave 2. This is non-negotiable and will be explained in detail below.

**Wave 3 — Integrate.** welder reads every artifact from Waves 1 and 2, then wires them into the existing codebase. Backward-compatible refactors, test suite updates, import path fixes.

**Critic gate.** Same as before. Full review of welder's output.

**Wave 4 — Final Verification.** sentinel runs the test suite, checks version sync across `plugin.json` / `package.json` / source, and produces a pass/fail scorecard. Every PASS cites a command output. sentinel does not write a single character of code.

**Wave 5 — Infrastructure.** keeper updates `CLAUDE.md`, CI workflows, and the registry. The orchestrator reviews the sentinel scorecard. MUST FIX findings go back to welder. PASS on all checks means the session closes.

---

## Parallel Dispatch at Scale

The real leverage comes from running multiple agents simultaneously within a wave. BAARA Next Phase 1 used three welders in parallel:

```
Wave 2 (parallel):
  welder-1: packages/store + packages/orchestrator
  welder-2: packages/agent + packages/executor
  welder-3: packages/transport + packages/server + packages/cli
```

Each welder got the full output of Wave 1 — guido's interfaces, core types, error definitions — as upstream context in its dispatch prompt. Each targeted a distinct set of packages. None touched files owned by the others.

Phase 4 ran five agents across three sequential sub-waves:

```
Wave 1 (parallel):
  welder-A: MCP server — 27 tools, 12 tasks
  welder-D: Thread model — schema + CRUD, 6 tasks

Wave 2 (parallel, after Wave 1):
  welder-B: Chat SSE streaming — 6 tasks
  welder-E: CLI mcp-server + chat REPL — 6 tasks

Wave 3 (after Wave 2):
  welder-C: Web UI rewrite — 20 tasks
```

The sub-wave structure within Phase 4 reflects real dependencies. The web UI cannot stream chat before the server's SSE endpoints exist. The CLI chat REPL cannot connect before the streaming layer is in place. Declaring these as sequential sub-waves rather than sequential tasks preserves parallelism within each sub-wave while enforcing the ordering that the architecture requires.

---

## The Critic Gate

The critic gate is the most important pattern in the whole system. After every wave that writes code, before the next wave begins, the critic agent reviews all modified files.

The critic is not a wave agent. It has no scheduled slot. It fires unconditionally after code-writing waves. You cannot skip it.

Here is the exact mechanism:

1. The wave engine collects all `docs/plans/agent-*-status.md` files written by agents in the completed wave. Each status file includes a "Files Modified" section.

2. The wave engine dispatches the critic against those files, with the plan's acceptance criteria as the review brief.

3. The critic reads every file before making a single comment. It checks: state machine integrity, API contract compliance, unauthenticated execution paths, resource leaks, dead code, type safety, error handling on external calls. It reports findings as MUST FIX / SHOULD FIX / CONSIDER / NIT.

4. If MUST FIX items exist, welder is dispatched to fix them. The critic reviews again. Maximum three cycles.

5. Once MUST FIX is cleared, the next wave proceeds.

Each critic pass takes approximately two minutes. Here is what those two minutes caught in BAARA Next:

- **Phase 1:** 10 MUST FIX — state machine violations where execution status transitioned from `assigned` directly to `failed` without passing through `running`, broken API contracts, an unauthenticated endpoint that accepted arbitrary shell commands
- **Phase 4:** 5 MUST FIX — missing SSE fields that would have caused silent client disconnects, wrong HTTP methods on two endpoints, phantom imports referencing modules that had been renamed
- **Phase 5:** 4 MUST FIX — a migration that would have corrupted existing records, missing schema definitions, wrong row counts in two seed files

26 bugs in total. Every one of them would have been harder to find after the fact. A state machine violation found in a code review takes two minutes to fix. A state machine violation found after the system is deployed and executions are getting stuck in `assigned` status takes hours to diagnose and requires a data migration to repair.

The math is obvious. The critic gate is not a nice-to-have.

---

## What Each Agent Receives

Each agent in a wave gets a focused dispatch prompt. It contains exactly what the agent needs and nothing it does not.

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

The agent receives the intent, the acceptance criteria, the scope, the upstream context extracted from prior waves' status files, and the verification command. It does not receive the full plan, the other agents' conversation histories, or implementation code to copy. It reads the actual codebase, applies its domain expertise, and produces output against the acceptance criteria.

The `upstream context` section is how the wave engine threads information across waves without requiring agents to share conversation history. When welder-A finishes and writes its status file noting that `retry.ts` exports `shouldRetry()` and `calculateDelay()`, the wave engine reads that status file and injects those decisions into welder-B's dispatch prompt. Each agent starts with fresh context but has the facts it needs from prior waves.

---

## Intent-Driven Plans, Not Implementation Blueprints

The wave engine executes plans, not recipes. Tasks describe what to achieve and how to verify it. They do not describe how to implement it.

This matters for two reasons. First, agents are more accurate about the codebase than a plan written before execution. A plan written on Tuesday that specifies a function signature may be wrong by Wednesday if the codebase evolved. An agent reading the codebase on Wednesday has accurate information.

Second, acceptance criteria stay correct across implementation divergence. "Failed executions trigger retry with exponential backoff" is as true at the end of execution as it was at the beginning. "Use `setTimeout` with `Math.pow(2, attempt)`" may be wrong the moment an agent discovers that the project already has a delay utility with a different interface.

In the prescriptive-plan phases of BAARA Next, 30 to 40 percent of the implementation code written into plans was modified by agents during execution. The plans were right about what to build. They were partially wrong about how to build it. Intent-driven task descriptions eliminate the how entirely and let the agents be right about it instead.

---

## Language-Aware Verification

Before the critic gate runs, the wave engine runs language-specific verification to ensure the code even compiles:

| Language | Verification Command | What It Catches |
|----------|---------------------|-----------------|
| TypeScript | `npx tsc --noEmit` | Type errors, import mismatches |
| Python | `ruff check . && mypy .` | Lint violations, type errors |
| Rust | `cargo check` | Borrow checker, type errors, lifetime issues |
| Any | test command from plan | Failing tests from the current wave |

Language detection happens automatically: `Cargo.toml` signals Rust, `pyproject.toml` signals Python, `package.json` signals TypeScript. If verification fails, the engine dispatches welder to fix the errors before calling the critic. There is no point reviewing code that does not compile.

This sequencing matters. The critic is expensive — it reads every modified file carefully. Running it against code that has type errors wastes its review on surface problems that welder can fix in seconds.

---

## The Results

BAARA Next, measured at the end of Phase 6:

- **218 files** across 10 packages
- **44,268 lines** of TypeScript
- **19 smoke tests** covering the core execution path
- **6 phases**, each with its own wave structure
- **0 MUST FIX** bugs in the final sentinel scorecard

The 26 bugs caught by critic gates before they reached the final review did not make it to production. The three welders that ran in parallel in Phase 1 did not produce merge conflicts. The five agents that ran in Phase 4's three sub-waves did not build against each other's assumptions because upstream context flowed correctly through status files.

The wave engine is not magic. It is discipline made structural: research before building, parallel work where possible, sequential work where necessary, and a mandatory quality gate after every phase of writing.

---

## Quick Mode for Small Tasks

The full wave engine is overkill for a bug fix that touches one file. `/flow:quick` provides a fast path: single agent dispatch, language verification, critic review, one fix cycle if needed, done. No brainstorming, no planning, no waves.

Use quick mode for bug fixes affecting one or two files, parameter additions, and renames. Use the full wave engine for anything spanning multiple files, multiple packages, or multiple concerns.

---

## The Practical Lesson

Building with AI agents at scale requires the same engineering discipline that building distributed systems requires: explicit dependency management, state isolation between components, mandatory quality gates, and a clear protocol for how information flows between parts of the system.

The wave engine applies these principles to agent coordination. Waves are the dependency graph made executable. Critic gates are the quality invariant enforced structurally rather than by convention. Status files are the inter-agent communication protocol. Intent-driven plans are the interface contract between the orchestrator and the agents.

Each of these is a choice you can make without the wave engine. The wave engine makes them the default.

---

*The wave engine is the execution core of fakoli-flow. fakoli-crew provides the specialist agents — welder, critic, sentinel, and the rest — that the engine dispatches. The 26-bug figure comes from live BAARA Next project data across 6 phases of development.*
