---
description: Ship phase — merge, PR, keep, or discard with pre-merge verification
---

# Finish (`/flow:finish`)

## Overview

Ship work only after fresh verification. Present options. Execute the chosen one. Never act without an explicit choice.

**Core principle:** Verify first, present exactly 4 options, wait for a decision, then execute.

**This skill is invoked:**
- After `/flow:verify` reports all criteria PASS
- Manually when the user runs `/flow:finish`

**Never auto-merge or auto-push.** The skill presents options and waits. The user decides.

---

## Step 1: Re-Run Tests (Fresh Evidence)

Do not rely on the verify step's results. Re-run now, in this message.

Detect the project language first:

```bash
[ -f tsconfig.json ] && echo "TypeScript"
[ -f Cargo.toml ] && echo "Rust"
{ [ -f pyproject.toml ] || [ -f setup.py ]; } && echo "Python"
```

Then run the appropriate test command:

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

**If tests fail — STOP.**

Report the failures with their full output:

```
Tests failing (N failures). Cannot proceed to ship.

[show exact failure output]

Fix the failures and re-run `/flow:finish`.
```

Do not proceed to Step 2. Return control to the user.

**If tests pass:** Continue.

---

## Step 2: Determine Base Branch

```bash
git branch --show-current
git branch --list main master
```

If `main` exists, use `main` as the base branch. If only `master` exists, use `master`. If neither `main` nor `master` is found, ask the user: "What is the base branch?"

---

## Step 3: Present Exactly 4 Options

Present these options verbatim, substituting `<base-branch>` with the detected branch name:

```
Tests pass. What would you like to do with this branch?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is
4. Discard this work

Which option? (1/2/3/4)
```

Do not add explanations, recommendations, or commentary. Do not suggest an option. Wait for the user's answer.

---

## Step 4: Execute the Chosen Option

### Option 1: Merge Locally

```bash
# Get the current feature branch name
FEATURE_BRANCH=$(git branch --show-current)

# Switch to base branch
git checkout <base-branch>

# Pull latest
git pull

# Merge feature branch
git merge "$FEATURE_BRANCH"
```

After merging, re-run tests on the merged result:

```bash
# Run the same test command from Step 1
```

If the post-merge tests fail: do not delete the feature branch. Report the failures and stop.

If the post-merge tests pass:

```bash
git branch -d "$FEATURE_BRANCH"
```

Report: "Merged `<feature-branch>` into `<base-branch>`. Branch deleted."

---

### Option 2: Push and Create a Pull Request

```bash
# Push the feature branch
git push -u origin $(git branch --show-current)
```

Then create the PR using `gh pr create`. Pull the summary from the plan file:

```bash
# Find the plan
ls docs/plans/ | sort | tail -1
```

Read the plan's **Goal** line and task list. Use them in the PR body:

```bash
gh pr create --title "<feature name from plan Goal>" --body "$(cat <<'EOF'
## Summary

<2-3 bullet points from the plan's task list — what was built, not how>

## Test results

- Type check: PASS (npx tsc --noEmit)
- Tests: PASS (N/N passing)
- Acceptance criteria: N/N PASS

## Plan

docs/plans/<plan-filename>
EOF
)"
```

Report the PR URL when `gh pr create` returns it.

---

### Option 3: Keep the Branch As-Is

Report: "Keeping branch `<feature-branch>`. No changes made."

Do not delete anything. Do not merge anything. Done.

---

### Option 4: Discard This Work

First, show exactly what will be deleted:

```bash
git log <base-branch>..HEAD --oneline
```

Display:

```
This will permanently delete:

Branch: <feature-branch>
Commits to be lost:
  <commit hash> <commit message>
  <commit hash> <commit message>
  ...

Type "discard" to confirm. This cannot be undone.
```

Wait for the user to type exactly `discard`. Accept nothing else — not "yes", not "ok", not "confirm".

If the user does not type `discard`: abort. Report: "Discard cancelled. Branch preserved."

If the user types `discard`:

```bash
FEATURE_BRANCH=$(git branch --show-current)
git checkout <base-branch>
git branch -D "$FEATURE_BRANCH"
```

Report: "Branch `<feature-branch>` and all its commits have been deleted."

---

## Step 5: Worktree Cleanup

Check if a worktree was used for this branch:

```bash
git worktree list | grep "$(git branch --show-current)" 2>/dev/null
```

- **Option 1 (merge) and Option 4 (discard):** Remove the worktree if present:
  ```bash
  git worktree remove <worktree-path>
  ```
- **Option 2 (PR) and Option 3 (keep):** Leave the worktree intact.

---

## Quick Reference

| Option | What happens | Worktree |
|--------|-------------|----------|
| 1. Merge locally | Merges to base, deletes feature branch | Removed |
| 2. Push + PR | Pushes branch, creates GitHub PR | Preserved |
| 3. Keep as-is | Nothing changes | Preserved |
| 4. Discard | Deletes all commits, deletes branch | Removed |

---

## Red Flags — Never Do These

- **Never merge without running fresh tests in this skill.** The verify step's results are stale by definition.
- **Never push without an explicit Option 2 choice.**
- **Never delete a branch without the exact typed word "discard" for Option 4.**
- **Never force-push** unless the user explicitly requests it.
- **Never offer a 5th option** or improvise on the 4 options presented.
- **Never proceed with failing tests.** Full stop.

---

## Common Mistakes

**Skipping the Step 1 re-run because `/flow:verify` just passed.**
Verify ran earlier. Code may have changed. Run the tests again now.

**Adding a recommendation when presenting options.**
"I'd suggest option 2" — don't. Present the options. Wait.

**Accepting "yes" instead of "discard" for Option 4.**
The exact word is the guard. If someone types "yes", ask again.

**Forgetting to check for worktrees.**
A dangling worktree is a future confusion. Always check and clean up for Options 1 and 4.
