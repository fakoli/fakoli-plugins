---
description: Execute phase — wave-based crew dispatch with critic gates and evidence-based verification
---

# Execute — Execute Phase

Load an intent-driven plan, group tasks into dependency-ordered waves, dispatch specialist agents in parallel within each wave, run language-aware verification and a mandatory critic gate between waves, then dispatch the sentinel for final sign-off.

<HARD-GATE>
The critic gate runs after EVERY wave that writes code. It is not optional and cannot be skipped. Proceed to the next wave only after the critic returns PASS (or SHOULD FIX / NIT with no MUST FIX findings).

This gate is mechanically enforced, not just instructed: while a run is armed (see Step 1), the plugin's PreToolUse hook denies dispatch of any agent other than critic or welder once a code-writing agent has completed and the critic has not yet reviewed. Arm the gate at run start and disarm it on every exit path.
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

### Step 1: Load the Plan and Derive the Run ID

Read the plan file fully. Extract:
- Plan header (Goal, Language, Crew)
- All tasks with their Intent, Acceptance criteria, Scope, Agent, Verify, and Depends on fields
- Build a dependency graph in memory

If the plan file does not exist or cannot be found, ask the user for the path. Do not proceed without it.

**Derive the run ID immediately after loading the plan.** The run ID is the single
source of truth for all status-file paths in this execution:

```
<run-id> = <sanitized-plan-basename>-<YYYYMMDDHHmmss UTC>
```

Sanitization rules for the plan basename (applied in order):
1. Strip the file extension.
2. Lowercase everything.
3. Replace every character outside `[a-z0-9-]` with `-`.
4. Collapse consecutive `-` into one; trim leading/trailing `-`.

The timestamp includes seconds so two runs of the same plan started in the same
minute cannot collide on a scratch root.

Example: plan file `docs/plans/2026-06-01-retry-mechanism.md` loaded at 14:30:07 UTC
on 2026-06-01 → `run-id = 2026-06-01-retry-mechanism-20260601143007`.

**Default scratch root:** `.fakoli/runs/<run-id>/` (relative to the project root).
Log the resolved absolute path once:

```
[execute] Run ID: 2026-06-01-retry-mechanism-20260601143007
[execute] Scratch root: /abs/project/.fakoli/runs/2026-06-01-retry-mechanism-20260601143007/
```

All status-file references in this run use the absolute scratch root path. Every
agent dispatch prompt receives the absolute path for its own status file.

**Arm the critic gate.** After creating the scratch root, write the run ID to the
gate-arming file:

```bash
mkdir -p .fakoli && printf '%s\n' "<run-id>" > .fakoli/gate-armed
```

While this file exists, the plugin's hooks enforce the critic gate mechanically:
when a code-writing crew agent (guido, smith, welder) completes, only critic or
welder dispatches are permitted until a critic review completes. Arming requires
fakoli-crew agent types; generic-fallback runs are not hook-enforced (the prompt
rules below still apply).

**Disarm on every exit path.** When the run ends — final summary delivered, run
aborted, or control handed back to the user for an unresolved escalation — remove
the gate state:

```bash
rm -f .fakoli/gate-armed .fakoli/gate-state.json
```

A stale arming file older than 24 hours is ignored by the hooks (abandoned-run
protection), but never rely on that: disarm explicitly.

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

For a one-page quick reference covering the DSL, agent capability matrix, and language-verification commands, see `references/wave-engine-ref.md`. For the full design rationale and worked real-world examples, see `docs/wave-engine.md`.

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
4. **Upstream context** — decisions and notes from prior wave status files (extracted from the run scratch directory)
5. **Verify command** (from plan)
6. **Status file instruction** — tell the agent to write its result to the absolute path
   `<scratch-root>/agent-<name>-status.md` where `<scratch-root>` is the run's scratch root

For a complete, ready-to-copy example of a dispatch prompt with all six fields filled in (plus annotation of what makes a prompt effective), see `references/example-dispatch-prompt.md`.

---

## Status File Protocol

Agents write status files to the run scratch directory: `<scratch-root>/agent-<name>-status.md`.
`<scratch-root>` is the absolute path logged at Step 1 (default: `.fakoli/runs/<run-id>/`).
The wave engine reads these after each wave to confirm completion, surface escalations, and extract files-modified + decisions for the next wave.

For the full format specification — status values, reading rules, writing rules, and worked examples for welder and critic — see `references/status-protocol.md`. The summary that follows covers only the operational protocol the execute skill enforces.

### Reading Status Files After Each Wave

After dispatching a wave, wait for all `<scratch-root>/agent-*-status.md` files to show a terminal status (COMPLETE, NEEDS_REVIEW, or BLOCKED).

**Polling protocol:**
1. Read all `<scratch-root>/agent-*-status.md` files.
2. If any shows `IN_PROGRESS`: wait 10 seconds and re-read.
3. If still `IN_PROGRESS` after 5 minutes: surface to user as a timeout — "Agent `<name>` has been IN_PROGRESS for 5 minutes. Check for errors or re-dispatch."

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

Read all `<scratch-root>/agent-*-status.md` files from the completed wave. Extract every file listed in "Files Modified". Deduplicate.

### Step 2: Dispatch Critic

```
Agent(
  subagent_type = "fakoli-crew:critic",
  prompt = """
    Review the code written in Wave <N>. Review in two stages, in this order:

    STAGE 1 — Spec compliance. For each acceptance criterion below, find the
    code that satisfies it and cite file:line. A criterion with no satisfying
    code is MUST FIX (label it [SPEC]). Do not start Stage 2 until every
    criterion has a verdict.

    STAGE 2 — Code quality. Correctness under failure, API contracts, state
    machine integrity, security, concurrency, dead code.

    Files to review:
    - path/to/file1.ts
    - path/to/file2.ts

    Acceptance criteria to check against:
    <acceptance criteria from the plan tasks that this wave addressed>

    Report findings as:
    - MUST FIX: unmet acceptance criteria [SPEC], correctness bugs, security issues, broken contracts, data corruption risk
    - SHOULD FIX: quality issues worth addressing but not blocking
    - CONSIDER: suggestions for improvement
    - NIT: minor style issues

    Write your review to: <scratch-root>/agent-critic-status.md
  """
)
```

The two-stage order matters: a review that starts with code quality can polish
its way past a missing requirement. Spec compliance first means "beautiful code
that doesn't do what the plan asked" is caught as MUST FIX, not missed as
clean-looking.

Replace `<scratch-root>` with the absolute path logged at the start of this run.

### Step 3: Evaluate Findings

Read `<scratch-root>/agent-critic-status.md`.

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

    Write your scorecard to: <scratch-root>/agent-sentinel-status.md
    Status: COMPLETE (all pass) or NEEDS_REVIEW (any fail).

    End the scorecard with a machine-readable verdict in a fenced json block:
    {"verdict": "READY" | "NOT_READY", "pass": <n>, "fail": <n>, "na": <n>,
     "failures": [{"check": "<name>", "fix_owner": "<agent>"}]}
  """
)
```

Replace `<scratch-root>` with the absolute path logged at the start of this run.

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
| `fakoli-crew:warden` | `general-purpose` with prompt: "You are a security auditor. Review only for exploitability — injection, secret leakage, supply-chain risk, auth bypass, plugin permission surfaces. Report findings by severity (CRITICAL/HIGH block, MEDIUM/LOW advise) with file:line and the attack story. Report, do not fix." |
| `fakoli-crew:sentinel` | `general-purpose` with prompt: "You are verifying that all acceptance criteria are met. Run each check command and report the exact output." |
| `fakoli-crew:smith` | `general-purpose` with prompt: "You are creating plugin manifests and command files." |
| `fakoli-crew:herald` | `general-purpose` with prompt: "You are writing documentation and README files." |
| `fakoli-crew:keeper` | `general-purpose` with prompt: "You are managing infrastructure and configuration files." |

Note in the execution log when running on generic subagents. All critic gate rules and verification rules still apply.

---

## Final Summary

Before reporting, disarm the critic gate — the run is over:

```bash
rm -f .fakoli/gate-armed .fakoli/gate-state.json
```

(Do this on every exit path, including aborts and unresolved escalations — see Step 1.)

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

---

## Further Reading

- `references/status-protocol.md` — full status file format specification
- `docs/wave-engine.md` — detailed wave engine design and real-world examples
