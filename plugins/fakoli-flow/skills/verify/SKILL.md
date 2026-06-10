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
[ -f tsconfig.json ] && echo "TypeScript"
[ -f Cargo.toml ] && echo "Rust"
{ [ -f pyproject.toml ] || [ -f setup.py ]; } && echo "Python"
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

**If multiple plans exist for the current date:** Do not guess. Ask the user:
```
Multiple plans found for today:
- docs/plans/2026-04-04-feature-a.md
- docs/plans/2026-04-04-feature-b.md
Which plan should I verify against?
```

**After `/flow:quick` (no plan file):** Quick mode does not create a plan file. If verify is invoked after a quick session, ask the user for the original task description and verify the modified files against it. Use the same evidence gate — every PASS still requires a command output to cite. Because there is no plan file, use `verify-quick-<YYYYMMDDHHmm UTC>` as the run-id (e.g. `verify-quick-202606011545`) so the sentinel always gets a concrete, absolute status path.

**Derive a scratch path for this verify session.** Use a `verify-` prefixed run ID so the
sentinel has an isolated, gitignored location to write its status file:

```
# When a plan file exists:
<verify-run-id>     = verify-<plan-basename-without-extension>-<YYYYMMDDHHmm UTC>

# When there is no plan file (quick mode):
<verify-run-id>     = verify-quick-<YYYYMMDDHHmm UTC>

<verify-scratch>    = <project-root>/.fakoli/runs/<verify-run-id>/
<sentinel-status>   = <verify-scratch>/agent-sentinel-status.md   (absolute path)
```

Example (plan file): plan file `docs/plans/2026-06-01-retry-mechanism.md`, verify invoked at 15:45 UTC →
`verify-run-id = verify-2026-06-01-retry-mechanism-202606011545`

Example (quick mode): no plan file, verify invoked at 15:45 UTC →
`verify-run-id = verify-quick-202606011545`

Log the resolved paths before dispatch:

```
[verify] Run ID: verify-2026-06-01-retry-mechanism-202606011545
[verify] Scratch root: /abs/project/.fakoli/runs/verify-2026-06-01-retry-mechanism-202606011545/
[verify] Sentinel status: /abs/project/.fakoli/runs/verify-2026-06-01-retry-mechanism-202606011545/agent-sentinel-status.md
```

Quick-mode log example:

```
[verify] Run ID: verify-quick-202606011545
[verify] Scratch root: /abs/project/.fakoli/runs/verify-quick-202606011545/
[verify] Sentinel status: /abs/project/.fakoli/runs/verify-quick-202606011545/agent-sentinel-status.md
```

**Dispatch.** Use exactly ONE of the two dispatches below — the plan-file dispatch when a plan exists, the quick-mode dispatch when it does not. Do not combine them, and never paste a `docs/plans/<filename>` that does not exist.

Plan-file mode (a plan exists):

```
Agent(
  subagent_type="fakoli-crew:sentinel",
  prompt="Run verification and report PASS or FAIL per item with cited evidence. Do not claim PASS without a command output from this session to cite.

Acceptance criteria:
<paste criteria from plan>
Plan file: docs/plans/<filename>
For each criterion, run the exact verify command from the plan.
Language: <detected language>

Write your scorecard to: <sentinel-status>
Status: COMPLETE (all pass) or NEEDS_REVIEW (any fail).
End the scorecard with a machine-readable verdict in a fenced json block:
{\"verdict\": \"READY\" | \"NOT_READY\", \"pass\": <n>, \"fail\": <n>, \"na\": <n>, \"failures\": [{\"check\": \"<name>\", \"fix_owner\": \"<agent>\"}]}
"
)
```

Quick mode (no plan file):

```
Agent(
  subagent_type="fakoli-crew:sentinel",
  prompt="Run verification and report PASS or FAIL per item with cited evidence. Do not claim PASS without a command output from this session to cite.

Plan file: (none — quick session)
Task description: <original task the user gave to /flow:quick>
Verify the modified files against this task description; derive a concrete verify command per claim (build / test / typecheck). Do not invent acceptance criteria the user did not state.
Language: <detected language>

Write your scorecard to: <sentinel-status>
Status: COMPLETE (all pass) or NEEDS_REVIEW (any fail).
End the scorecard with a machine-readable verdict in a fenced json block:
{\"verdict\": \"READY\" | \"NOT_READY\", \"pass\": <n>, \"fail\": <n>, \"na\": <n>, \"failures\": [{\"check\": \"<name>\", \"fix_owner\": \"<agent>\"}]}
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

## Step 5.5: Adversarial Refutation Pass

A single verifier confirming its own reading of the evidence is the weakest link in
the chain — independent refutation materially outperforms single-verifier review.
When fakoli-crew is installed and the scorecard contains at least one PASS, dispatch
a second sentinel whose job is to break the verdict, not confirm it:

```
Agent(
  subagent_type="fakoli-crew:sentinel",
  prompt="You are the REFUTER. A first verification pass produced the scorecard
below. For each PASS verdict, try to REFUTE it: find a command, an edge case, or a
stricter reading of the criterion under which the cited evidence does NOT prove the
criterion. Run your own commands — do not trust the cited output. You succeed by
breaking a verdict, not by agreeing with it.

For each criterion report:
- UPHELD — you attempted refutation and failed; cite the command you ran
- REFUTED — the PASS does not hold; cite the exact evidence that breaks it

Scorecard under review:
<paste the Step 5 scorecard verbatim>

Write your report to: <verify-scratch>/agent-sentinel-refuter-status.md
End with a fenced json block:
{\"upheld\": <n>, \"refuted\": <n>, \"refutations\": [{\"criterion\": \"<text>\", \"evidence\": \"<what broke it>\"}]}
"
)
```

**Convergence rule:** a criterion is PASS only when both sentinels agree. Every
REFUTED criterion flips to FAIL in the final scorecard, carrying the refuter's
evidence. Never argue with the refuter on the original sentinel's behalf — if the
refutation itself looks wrong, surface both findings to the user; do not silently
pick a winner.

Skip this pass only when there were zero PASS verdicts to refute (everything already
failed) or fakoli-crew is not installed (generic fallback: run the refutation prompt
yourself against your own scorecard before reporting).

---

## Step 6: Report to User

Present the scorecard. Then:

- If **all PASS and all upheld by the refuter**: "Verification complete. All criteria met (adversarially confirmed). Run `/flow:finish` to ship."
- If **any FAIL or any REFUTED**: State what failed (including refuted criteria with the refuter's evidence) and stop. Do not proceed to finish. Do not suggest retrying without fixing the underlying issue first.

---

## Red Flags — Stop and Report

Do not proceed past this skill if any of these are true:

- A command exited non-zero
- Typecheck output contains any error lines
- Any test failed
- An acceptance criterion produced no verifiable output
- The plan file cannot be found AND this is not a quick-mode session (in quick mode, verify against the user's task description instead)

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
