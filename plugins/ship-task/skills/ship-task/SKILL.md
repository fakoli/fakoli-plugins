---
name: ship-task
description: This skill should be used AFTER code review and verification pass, when the user wants to "ship this", "ship the task", "open and merge the PR", "push, PR, wait for CI, and merge", or otherwise run the mechanical tail of a one-PR-per-task loop. It pushes the current branch, opens a PR, waits for CI to reach a terminal state, merges (squash + delete branch), syncs the base branch, and optionally runs a post-merge command (e.g. `anvil apply`). It makes NO review decisions — the human or agent gates that first.
user-invocable: true
---

# ship-task

The deterministic tail of shipping one task as one PR, collapsed into a single
command so it stays out of the context window. Runs **after** your review /
verification pass — it never reviews code or decides whether to merge; if CI
fails it stops and leaves the PR open.

## The command

`${CLAUDE_PLUGIN_ROOT}/scripts/ship.sh` — bash + `git` + `gh`, no other deps.

```bash
SHIP="${CLAUDE_PLUGIN_ROOT}/scripts/ship.sh"
"$SHIP" "PR title" --body-file /tmp/pr-body.md          # push → PR → CI → merge → sync
"$SHIP" "PR title" --then "anvil apply T007 --approve --reviewer me"   # + post-merge step
"$SHIP" "PR title" --dry-run                            # print the plan, touch nothing
"$SHIP" --help
```

It prints one `ship:` line per stage and a final summary
(`ship: PR #161 · CI passed · merged abc123def · sync ok · then ok · <url>`),
not the raw git/gh output.

## When to use it

- The task's branch is committed, review has passed, and it's ready to merge.
- You're running a one-PR-per-task loop and the push→PR→poll-CI→merge→apply tail
  is repeated per task — that repetition is exactly what this replaces.

## When NOT to use it

- Before review — ship does not gate quality. Dispatch your reviewer first.
- To create code or commits — ship pushes only what's already committed
  (it warns loudly if the tree is dirty).

## Key flags

| Flag | Purpose |
|------|---------|
| `--body TEXT` / `--body-file FILE` | PR body (`-` reads stdin) |
| `--base BRANCH` | base branch (default: the repo's default branch) |
| `--then "CMD"` | run after a successful merge — the composition seam for tools like anvil |
| `--no-wait` | merge without polling CI |
| `--draft` | open a draft PR and stop |
| `--admin` | `gh pr merge --admin` (bypass required checks if permitted) |
| `--unset-token` | run `gh` as `env -u GITHUB_TOKEN gh …` (ambient-PAT workaround) |
| `--dry-run` | print the plan and exit |

Exit codes: `0` shipped · `1` usage/preflight · `2` CI failed (PR left open) ·
`3` merge failed (PR left open) · `4` `--then` command failed · `5` **merged
remotely** but the local base sync was skipped or failed (base branch owned by
another worktree, checkout error, or non-fast-forward pull) — the PR is merged
and ship attempts the remote-branch cleanup (warns if that fails); do NOT
re-run ship, just sync the base locally (`--then` is skipped on exit 5).
Full reference: see `README.md`.
