---
description: Execute phase — wave-based crew dispatch with critic gates and evidence-based verification
---

# Execute — Execute Phase

Load an intent-driven plan, group tasks into dependency-ordered waves, dispatch specialist agents in parallel within each wave, run language-aware verification and a mandatory critic gate between waves, then dispatch the sentinel for final sign-off.

<HARD-GATE>
The critic gate runs after EVERY wave that writes code. It is not optional and cannot be skipped. Proceed to the next wave only after the critic returns PASS (or SHOULD FIX / NIT with no MUST FIX findings).
</HARD-GATE>

---

## Process Flow

```
Start
  |
  v
[1. Load plan]
  Parse tasks, dependencies, agent assignments, verify commands.
  |
  v
[2. Detect agents]
  Is fakoli-crew installed? Log available agents. Note fallback.
  |
  v
[3. Group into waves]
  Apply dependency rules (see Wave Assignment section below).
  |
  v
[For each wave:]
  |
  v
  [a. Dispatch agents in parallel]
     One Agent tool call per task. All tasks in the wave start simultaneously.
     |
  [b. Wait for completion]
     Read agent status files. Poll until all show COMPLETE, BLOCKED, or NEEDS_REVIEW.
     |
  [c. Handle escalations]
     BLOCKED -> surface to user, wait for resolution, then re-dispatch.
     NEEDS_REVIEW -> surface to user, wait for decision, then continue.
     |
  [d. Run language verification]
     TypeScript: npx tsc --noEmit
     Python:     ruff check . && mypy .
     Rust:       cargo check
     If fail -> dispatch welder to fix -> re-run verification.
     Do NOT proceed to critic until verification passes.
     |
  [e. Run critic gate (non-negotiable)]
     Collect modified files from status files.
     Dispatch critic with file list + acceptance criteria.
     PASS or SHOULD FIX/NIT -> proceed.
     MUST FIX -> enter fix cycle (max 3 iterations, then escalate).
  |
  v
[After all waves: Dispatch sentinel]
  Final verification with evidence gate.
  |
  v
[Report summary]
```

---

## Step-by-Step Rules

### Step 1: Load the Plan

Read the plan file fully. Extract:
- Plan header (Goal, Language, Crew)
- All tasks with their Intent, Acceptance criteria, Scope, Agent, Verify, and Depends on fields
- Build a dependency graph in memory

If the plan file does not exist or cannot be found, ask the user for the path. Do not proceed without it.

### Step 2: Detect Available Agents

Run: `claude plugin list 2>/dev/null | grep fakoli-crew`

If fakoli-crew is detected, use `subagent_type="fakoli-crew:<agent>"` for dispatch.
If not detected, use `subagent_type="general-purpose"` for all agents (graceful degradation — see section below).

Log detected status once:
```
[execute] Language: TypeScript | Crew: fakoli-crew v2.0.0 | Waves: 3
```
or:
```
[execute] Language: Python | Crew: not installed (generic subagents) | Waves: 2
```

### Step 3: Group into Waves

Apply the dependency rules below to form waves. All tasks within a wave are independent and can run in parallel. Tasks across waves are sequential.

---

## Wave Assignment Rules

### From Declared Dependencies

Read each task's "Depends on" field. Tasks with no dependencies are Wave 1. Tasks whose dependencies are all in Wave N are Wave N+1.

**Algorithm:**
1. Assign all tasks with `Depends on: (none)` to Wave 1.
2. For each remaining task, find the maximum wave number of all its dependencies. Assign this task to that wave + 1.
3. Repeat until all tasks are assigned.

**Example:**
```
Task 1: no deps       -> Wave 1
Task 2: no deps       -> Wave 1
Task 3: depends on 1  -> Wave 2
Task 4: depends on 2  -> Wave 2
Task 5: depends on 3,4 -> Wave 3
```

Tasks 1 and 2 run in parallel. Tasks 3 and 4 run in parallel (after Wave 1). Task 5 runs alone.

### Default Pattern (No Dependencies Declared)

When the plan does not declare dependencies, use the crew's natural wave pattern:

```
Wave 1 — Research (parallel):
  All scout tasks: read docs, explore codebase, map dependencies.

Wave 2 — Build (parallel):
  All guido tasks: design interfaces, create new modules.
  All smith tasks: manifests, commands, plugin structure.
  All herald tasks: documentation drafts.

Wave 3 — Integrate (sequential):
  All welder tasks: wire new code into existing systems.

Wave 4 — Review (parallel):
  critic: code review with severity ratings.
  sentinel: test suite, validation scorecard.

Wave 5 — Fix cycle (if MUST FIX found in Wave 4):
  welder: fix MUST FIX findings.
  critic: re-review -> PASS required to proceed.
```

This pattern was validated across 6 phases of the BAARA Next project (44,268 lines, 218 files).

---

## Parallel Dispatch Pattern

Tasks within the same wave dispatch simultaneously in a single message. Do not wait for one to finish before starting the next.

**Two agents (common):**
```
Agent(subagent_type="fakoli-crew:guido", prompt="Task 1 — [full prompt]")
Agent(subagent_type="fakoli-crew:smith", prompt="Task 2 — [full prompt]")
```

**Three agents:**
```
Agent(subagent_type="fakoli-crew:welder", prompt="Task 3 — [full prompt]")
Agent(subagent_type="fakoli-crew:welder", prompt="Task 4 — [full prompt]")
Agent(subagent_type="fakoli-crew:guido", prompt="Task 5 — [full prompt]")
```

Each agent targets different files. File ownership ensures no two agents in the same wave modify the same file. If the plan has tasks in the same wave that target overlapping files, re-order them into sequential waves before dispatching.

### What Each Agent Dispatch Prompt Must Include

Construct the prompt for each agent from its plan task. Include:

1. **Task name and intent** (from plan)
2. **Acceptance criteria** (from plan, verbatim)
3. **Scope** — exact file paths (from plan)
4. **Upstream context** — decisions and notes from prior wave status files (extracted from `docs/plans/agent-*-status.md`)
5. **Verify command** (from plan)
6. **Status file instruction** — tell the agent to write its result to `docs/plans/agent-<name>-status.md`

Example dispatch prompt:
```
Task: Implement retry with exponential backoff

Intent: Failed executions must be retried with increasing delay before routing to the dead letter queue.

Acceptance criteria:
- Configurable max retries (default 3) and initial delay (default 1000ms)
- Delay doubles each attempt with +/-10% jitter to prevent thundering herd
- Retries exhausted -> route to DLQ, not silent failure
- Each retry creates a new execution attempt linked to the same thread

Scope: packages/orchestrator/src/retry.ts

Upstream context (from Wave 1 scout):
- packages/orchestrator/src/queue-manager.ts exists with enqueueTimer()
- No existing delay utility found; implement one inline

Verify: bun test packages/orchestrator/src/retry.test.ts

When done, write your status to: docs/plans/agent-welder-status.md
Use the standard format: Status, Wave, Timestamp, Files Modified, Files Read, Decisions, Notes for Specific Agents.
```

---

## Status File Protocol

Agents write status files at `docs/plans/agent-<name>-status.md`. The wave engine reads these after each wave.

### Status File Format

```markdown
# Agent <Name> Status

**Status:** IN_PROGRESS | COMPLETE | NEEDS_REVIEW | BLOCKED
**Wave:** <number>
**Timestamp:** <ISO 8601>

## Files Modified
- `path/to/file.ts` — what was changed

## Files Read (not modified)
- `path/to/file.ts` — why it was read

## Decisions
Key choices downstream agents must honor:
1. Decision with rationale

## Notes for Specific Agents
- **<agent-name>:** specific instruction for that agent

## Blockers (if BLOCKED)
What is preventing progress and what is needed to resolve it
```

### Reading Status Files After Each Wave

After dispatching a wave, wait for all `docs/plans/agent-*-status.md` files to show a terminal status (COMPLETE, NEEDS_REVIEW, or BLOCKED).

Extract from each completed status file:
- "Files Modified" — needed for the critic gate
- "Decisions" — needed for the next wave's upstream context
- "Notes for Specific Agents" — pass directly to the named agent in the next wave

### Handling Escalations

**BLOCKED:** The agent hit an obstacle it cannot resolve alone.
1. Read the "Blockers" section of the status file.
2. Surface to the user: "Agent `<name>` is blocked: `<blocker text>`. How should we proceed?"
3. Wait for the user's resolution.
4. Re-dispatch the agent with the resolution in the prompt.

**NEEDS_REVIEW:** The agent completed work but flagged a judgment call.
1. Read the status file fully.
2. Surface to the user: "Agent `<name>` needs a decision: `<issue text>`."
3. Wait for the user's decision.
4. If the decision changes scope, note it in the next wave's upstream context.
5. Continue execution.

Never silently swallow a BLOCKED or NEEDS_REVIEW status. Every escalation must reach the user.

---

## Language-Aware Verification

Run this between wave completion and the critic gate. If verification fails, fix it before running the critic — there is no point reviewing code that does not compile.

| Language | Verification Command |
|---|---|
| TypeScript | `npx tsc --noEmit` |
| Python | `ruff check . && mypy .` |
| Rust | `cargo check` |

**If verification fails:**
1. Log the exact error output.
2. Dispatch welder: `Agent(subagent_type="fakoli-crew:welder", prompt="Fix these verification errors: [exact output]. Scope: [files from status]")`
3. Wait for welder status file showing COMPLETE.
4. Re-run verification.
5. If it fails again, log and dispatch welder again (max 2 cycles before escalating to user).

---

## Critic Gate

**This gate is non-negotiable. It runs after every wave that wrote code.**

### Step 1: Collect Modified Files

Read all `docs/plans/agent-*-status.md` files from the completed wave. Extract every file listed in "Files Modified". Deduplicate.

### Step 2: Dispatch Critic

```
Agent(
  subagent_type = "fakoli-crew:critic",
  prompt = """
    Review the code written in Wave <N>.

    Files to review:
    - path/to/file1.ts
    - path/to/file2.ts

    Acceptance criteria to check against:
    <acceptance criteria from the plan tasks that this wave addressed>

    Report findings as:
    - MUST FIX: correctness bugs, security issues, broken contracts, data corruption risk
    - SHOULD FIX: quality issues worth addressing but not blocking
    - CONSIDER: suggestions for improvement
    - NIT: minor style issues

    Write your review to: docs/plans/agent-critic-status.md
  """
)
```

### Step 3: Evaluate Findings

Read `docs/plans/agent-critic-status.md`.

| Verdict | Action |
|---|---|
| No MUST FIX (all PASS, SHOULD FIX, CONSIDER, NIT) | Proceed to next wave. Log SHOULD FIX items. |
| One or more MUST FIX | Enter fix cycle. |

### Step 4: Fix Cycle (when MUST FIX found)

```
Fix cycle iteration (max 3):

  Dispatch welder with MUST FIX list:
  Agent(
    subagent_type = "fakoli-crew:welder",
    prompt = "Fix these MUST FIX findings from the critic:
              [exact MUST FIX text from critic status file]
              Files: [file list]"
  )
  Wait for welder COMPLETE.
  Re-dispatch critic on the same files.
  Wait for new critic status.

  If no MUST FIX -> proceed.
  If still MUST FIX -> repeat (up to 3 total iterations).
  If 3 iterations exhausted and still MUST FIX:
    Surface to user: "Critic found issues that could not be resolved in 3 cycles:
                      [MUST FIX list]. Please review and decide how to proceed."
    Wait for user decision before continuing.
```

**SHOULD FIX / CONSIDER / NIT:** Log these. Do not enter a fix cycle for them. They are surfaced in the final summary for the user to decide on.

---

## After All Waves: Sentinel

After all waves complete and all critic gates pass, dispatch the sentinel for final verification:

```
Agent(
  subagent_type = "fakoli-crew:sentinel",
  prompt = """
    Final verification for: <plan goal>

    Run each acceptance criterion check. For every pass, cite the exact command
    and its output — not a claim. For any failure, report the exact error.

    Acceptance criteria from the plan:
    <all acceptance criteria from all tasks>

    Verify command for each task:
    <list of verify commands from the plan>

    Language verification:
    TypeScript: npx tsc --noEmit && bun test
    Python:     ruff check . && mypy . && pytest
    Rust:       cargo check && cargo test

    Write your scorecard to: docs/plans/agent-sentinel-status.md
    Status: COMPLETE (all pass) or NEEDS_REVIEW (any fail).
  """
)
```

Read the sentinel's scorecard. If any criterion fails: do not declare the execution complete. Surface the failure to the user.

---

## Graceful Degradation (No fakoli-crew)

If fakoli-crew is not installed, the wave engine falls back to generic subagents. Execution still proceeds — you lose the specialized agent expertise but not the process.

Substitution table:

| fakoli-crew agent | Generic fallback |
|---|---|
| `fakoli-crew:guido` | `general-purpose` with prompt: "You are a senior engineer creating new modules and interfaces." |
| `fakoli-crew:welder` | `general-purpose` with prompt: "You are a senior engineer integrating code into existing systems." |
| `fakoli-crew:scout` | `general-purpose` with prompt: "You are researching a codebase. Read files and report findings only — make no changes." |
| `fakoli-crew:critic` | `general-purpose` with prompt: "You are a Staff Engineer doing a code review. Report MUST FIX, SHOULD FIX, CONSIDER, and NIT findings." |
| `fakoli-crew:sentinel` | `general-purpose` with prompt: "You are verifying that all acceptance criteria are met. Run each check command and report the exact output." |
| `fakoli-crew:smith` | `general-purpose` with prompt: "You are creating plugin manifests and command files." |
| `fakoli-crew:herald` | `general-purpose` with prompt: "You are writing documentation and README files." |
| `fakoli-crew:keeper` | `general-purpose` with prompt: "You are managing infrastructure and configuration files." |

Note in the execution log when running on generic subagents. All critic gate rules and verification rules still apply.

---

## Final Summary

After the sentinel returns COMPLETE, report:

```
Execution complete.

Waves: <N>
Tasks: <count> completed
Files modified: <count> (<list of paths>)
Critic findings: <count> MUST FIX resolved, <count> SHOULD FIX logged
Sentinel: PASS — all <N> acceptance criteria met
Time elapsed: <duration>

SHOULD FIX items logged (not blocking):
- <file>: <finding>
```

If the sentinel returns NEEDS_REVIEW, report each failing criterion and wait for the user's decision before declaring completion.
