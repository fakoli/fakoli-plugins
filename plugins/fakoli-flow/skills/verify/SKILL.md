---
description: Verify phase — evidence-based validation with sentinel dispatch and pass/fail scorecard
---

# Verify (`/flow:verify`)

## Overview

Verification is not an opinion. It is a command you ran, output you read, and a result you can cite.

**Core principle:** Every PASS must cite fresh command output from this session. Every FAIL must cite what the output actually showed.

**This skill is invoked:**
- Automatically after `/flow:execute` completes
- Manually when the user runs `/flow:verify`
- By `/flow:quick` after the agent finishes

---

## Step 1: Detect Project Language

Run the following to determine which verification commands apply:

```bash
# Check for language markers in order of specificity
ls tsconfig.json 2>/dev/null && echo "TypeScript"
ls Cargo.toml 2>/dev/null && echo "Rust"
ls pyproject.toml 2>/dev/null || ls setup.py 2>/dev/null && echo "Python"
```

| Marker file | Language |
|-------------|----------|
| `tsconfig.json` or `package.json` | TypeScript |
| `Cargo.toml` | Rust |
| `pyproject.toml` or `setup.py` | Python |

If multiple markers exist, prefer the most specific: `tsconfig.json` > `package.json`.

If no marker is found: ask the user before proceeding.

---

## Step 2: Run Language-Appropriate Checks

Run the full command for the detected language. Do not split it. Do not skip a step because the previous one passed.

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

Capture the full output of each command. Read exit codes. Count errors explicitly — do not skim.

---

## Step 3: Dispatch Sentinel (if fakoli-crew is available)

If `fakoli-crew` is installed, dispatch the sentinel agent with the acceptance criteria from the plan.

**How to find the plan:**

```bash
ls docs/plans/ | sort | tail -1
```

Read the most recent plan file. Extract the acceptance criteria for each task (the `**Acceptance criteria:**` bullet points under each task heading).

**Dispatch:**

```
Agent(
  subagent_type="fakoli-crew:sentinel",
  prompt="Run verification against the following acceptance criteria. For every criterion, run the exact verify command from the plan, read the full output, and report PASS or FAIL with evidence. Do not claim PASS without a command output from this session to cite.

Acceptance criteria:
<paste criteria from plan>

Plan file: docs/plans/<filename>
Language: <detected language>
"
)
```

**If fakoli-crew is not installed:** Skip sentinel dispatch. Run the criteria checks yourself using the verify commands listed in the plan. Apply the same evidence gate.

---

## Step 4: The Evidence Gate

This is non-negotiable. Every PASS must cite a specific piece of fresh evidence. Every FAIL must state what the output showed.

### What counts as evidence

| Evidence type | Example |
|---------------|---------|
| Exit code 0 from test command | `bun test` exited 0, 34/34 tests passed |
| Zero errors in typecheck output | `npx tsc --noEmit` output: (empty) |
| Expected value present in output | `pytest` output contains `5 passed` |
| File exists at expected path | `ls src/retry.ts` exits 0 |

### What does NOT count as evidence

| Not evidence | Why it fails |
|--------------|--------------|
| "Should work" | Expectation is not observation |
| Output from a previous session | Stale — the code may have changed |
| An agent's claim without command output | Agent reports are not verification |
| Partial output ("first 10 lines looked fine") | Partial proves nothing — errors appear at the end |
| "Looks good" | This is an opinion |

### When evidence conflicts with expectation

If a command exits non-zero, or output contains errors, or an expected value is absent:

- Mark that criterion **FAIL**
- Do not retry the same command hoping for a different result
- Do not move the goalposts ("this criterion wasn't really required")
- Report the actual output in the FAIL entry

---

## Step 5: Produce Pass/Fail Scorecard

Report the results in this exact format:

```
## Verification Scorecard

Language: TypeScript
Plan: docs/plans/2026-04-04-feature-name.md

### Type Check
PASS — `npx tsc --noEmit` exited 0, no output (zero errors)

### Tests
PASS — `bun test` exited 0: 34/34 tests passed, 0 failed

### Acceptance Criteria

- [PASS] Retry function accepts optional timeout parameter
  Evidence: `bun test src/retry.test.ts` — "timeout test" passed
- [PASS] Default timeout is 5000ms when not provided
  Evidence: test output shows "default timeout: 5000ms"
- [FAIL] Timeout triggers RateLimitError on expiry
  Evidence: `bun test` output shows 1 failed test: "expected RateLimitError, got TimeoutError"

---
Result: 2/3 criteria PASS — NOT READY TO SHIP
```

If all criteria pass:

```
Result: 3/3 criteria PASS — READY TO SHIP
```

---

## Step 6: Report to User

Present the scorecard. Then:

- If **all PASS**: "Verification complete. All criteria met. Run `/flow:finish` to ship."
- If **any FAIL**: State what failed and stop. Do not proceed to finish. Do not suggest retrying without fixing the underlying issue first.

---

## Red Flags — Stop and Report

Do not proceed past this skill if any of these are true:

- A command exited non-zero
- Typecheck output contains any error lines
- Any test failed
- An acceptance criterion produced no verifiable output
- The plan file cannot be found (cannot verify criteria without it)

State the problem explicitly. Return control to the user.

---

## Common Mistakes

**Claiming PASS because a prior session looked fine.**
The code changed. Run the command now.

**Skipping the sentinel because "the tests already cover it."**
Tests cover implementation. The sentinel checks acceptance criteria. These are different things.

**Marking PASS on a criterion with no verify command.**
If the plan has no verify command for a criterion, ask how to verify it. Do not assume.

**Stopping after the first failure.**
Run all checks. A full scorecard is more useful than a partial one. Report everything.
