---
description: Fast path — skip the full workflow for small tasks under 3 files
---

# Quick (`/flow:quick`)

## Overview

Skip brainstorming, planning, and wave execution for tasks that are too small to justify them.

**Core principle:** One agent, one pass, critic gate, done.

**Invocation:**
```
/flow:quick "add timeout param to retry"
/flow:quick "fix import path in auth module"
/flow:quick "rename voice_Id to voice_id throughout"
```

The task description is passed inline. No spec file. No plan file. No waves.

---

## When to Use Quick Mode

**Appropriate for:**
- Bug fixes touching 1-2 files
- Adding or renaming a parameter
- Fixing a typo or incorrect import
- Updating a comment or docstring
- Adjusting a constant or default value
- Any task where writing a spec would take longer than the fix itself

**Not appropriate for:**
- New features that touch 3 or more files
- Architecture changes (new modules, new data models, interface changes)
- Anything the user would want a spec or design discussion for first
- Tasks with multiple independent sub-tasks
- Anything requiring database migrations or security-critical logic

**If the scope is unclear:** estimate it first (Step 1). If the estimate exceeds 2-3 files, stop and suggest `/flow:brainstorm` instead.

---

## Step 1: Estimate Scope

Before dispatching an agent, estimate how many files this task will touch.

Read the relevant files. Look at:
- The file most likely to change (from the task description)
- Any files that import it or are imported by it
- Test files that cover that code

If the estimate is 3 or more files: stop. Tell the user:

```
This task looks like it will touch 3+ files (<list them>). Quick mode is intended for changes under 3 files.

Suggested path: `/flow:brainstorm` to spec the change, then `/flow:plan` + `/flow:execute`.

To override and use quick mode anyway: `/flow:quick --force "<task>"`
```

If the estimate is under 3 files: continue.

---

## Step 2: Detect Language

```bash
ls tsconfig.json 2>/dev/null && echo "TypeScript"
ls Cargo.toml 2>/dev/null && echo "Rust"
ls pyproject.toml 2>/dev/null || ls setup.py 2>/dev/null && echo "Python"
```

This determines the verification command used in Step 4.

---

## Step 3: Dispatch a Single Agent

Select the agent based on the task type:

| Task type | Agent |
|-----------|-------|
| Code changes, bug fixes, parameter additions | `welder` |
| Design questions, naming, interface decisions | `guido` |
| Research, library lookup, API verification | `scout` |

Default: `welder`.

**If fakoli-crew is installed:**

```
Agent(
  subagent_type="fakoli-crew:welder",
  prompt="<task description>

Scope: <list the files identified in Step 1>
Language: <detected language>

Make the change. Keep it minimal — only touch what the task requires. Do not refactor unrelated code."
)
```

**If fakoli-crew is not installed:** Perform the task directly. Apply the same scope constraint — only touch what the task requires.

---

## Step 4: Run Verification

After the agent completes (or after making the change directly), run the language-appropriate verification command. Do not skip this step.

**TypeScript:**
```bash
npx tsc --noEmit && bun test
```

**Python:**
```bash
ruff check . && mypy . && pytest
```

**Rust:**
```bash
cargo check && cargo test
```

Read the full output. Check the exit code.

- If **exit 0, zero errors**: continue to Step 5.
- If **exit non-zero or errors present**: go to the fix cycle (Step 6).

---

## Step 5: Dispatch Critic on Modified Files

Collect the files the agent modified. Dispatch the critic:

**If fakoli-crew is installed:**

```
Agent(
  subagent_type="fakoli-crew:critic",
  prompt="Review the following files for correctness, style, and completeness:

<list modified files>

Task that was performed: <task description>

Return: PASS, SHOULD FIX (minor issues, non-blocking), or MUST FIX (blocking issues that prevent shipping)."
)
```

**If fakoli-crew is not installed:** Review the modified files yourself. Apply the same PASS / SHOULD FIX / MUST FIX judgment.

---

## Step 6: Evaluate Result

### If PASS

Report to user:

```
Done. Task complete.

Files changed: <list>
Verification: PASS (npx tsc --noEmit && bun test — 34/34 passed)
Critic: PASS
```

Done. No finish step required for quick mode unless the user asks to ship.

---

### If MUST FIX

One fix cycle only.

Dispatch welder (or fix directly) with the critic's MUST FIX items:

```
Agent(
  subagent_type="fakoli-crew:welder",
  prompt="Fix the following issues identified by code review:

<critic's MUST FIX items>

Files: <list>
Do not change anything outside these issues."
)
```

Re-run verification (Step 4). Re-run critic (Step 5).

If still MUST FIX after one cycle: stop. Report to user:

```
Quick mode fix cycle did not resolve all issues.

Remaining issues:
<list>

Suggested path: Use `/flow:execute` for a full wave-based fix with multiple review cycles.
```

Do not loop. One fix cycle is the limit for quick mode.

---

### If SHOULD FIX

Log the suggestions. Proceed as PASS. Report both:

```
Done. Task complete.

Files changed: <list>
Verification: PASS
Critic: PASS (with suggestions logged below)

Suggestions (non-blocking):
- <suggestion 1>
- <suggestion 2>
```

---

## Quick Mode Does Not Replace the Full Workflow

Quick mode has no spec, no plan, no multi-wave execution, and no sentinel. It is intentionally limited.

If the user asks for something that sounds small but turns out to require a design decision, stop quick mode and say so:

```
This change requires a design decision: <state the decision>.

Quick mode skips brainstorming. To make this decision properly: `/flow:brainstorm "<topic>"`.
```

---

## Summary of the Quick Mode Flow

```
/flow:quick "<task>"
      |
      v
1. Estimate scope — >3 files? Stop, suggest brainstorm
      |
      v
2. Detect language (TypeScript / Python / Rust)
      |
      v
3. Dispatch agent (welder default, guido for design)
      |
      v
4. Run verification (tsc + bun test | ruff + mypy + pytest | cargo check + cargo test)
      |
      v
5. Dispatch critic on modified files
      |
      +-- PASS ---------> Done. Report to user.
      |
      +-- MUST FIX -----> One fix cycle -> re-verify -> re-critic
      |                       |
      |                       +-- PASS -----> Done.
      |                       +-- MUST FIX -> Stop. Escalate to /flow:execute.
      |
      +-- SHOULD FIX ---> Log suggestions. Done.
```
