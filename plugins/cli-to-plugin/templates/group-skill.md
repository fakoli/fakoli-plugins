<!-- Template: structural reference for the cli-to-plugin generator. Claude reads this to understand expected shape. NOT a Jinja template — no placeholder substitution. -->

---
name: gh-pr
description: Use when working with GitHub pull requests — listing, viewing, creating, reviewing, merging, or commenting on PRs via the `gh` CLI.
user-invocable: true
disable-model-invocation: false
argument-hint: "[pr-number|list|create|merge]"
allowed-tools: Bash
---

# gh-pr

## When to use
- The user wants to list, search, view, create, review, comment on, or merge pull requests.
- Tasks involving PR drafts, CI checks, reviewers, or labels.
- Do NOT use for issues or workflow runs — see [[gh-issue]] and [[gh-workflow]].

## Commands
| Subcommand | Purpose | Example |
|---|---|---|
| `gh pr list` | List open PRs in the current repo | `gh pr list --state open --author @me` |
| `gh pr view` | Show details for a specific PR | `gh pr view 42` |
| `gh pr create` | Open a new PR from the current branch | `gh pr create --title "Fix login bug" --body "Closes #12"` |
| `gh pr review` | Approve, request changes, or comment | `gh pr review 42 --approve` |
| `gh pr merge` | Merge a PR (squash, rebase, or merge) | `gh pr merge 42 --squash --delete-branch` |
| `gh pr comment` | Post a comment on a PR | `gh pr comment 42 --body "LGTM"` |
| `gh pr checks` | Show CI check results for a PR | `gh pr checks 42` |
| `gh pr diff` | Show the diff for a PR | `gh pr diff 42` |
| `gh pr close` | Close a PR without merging | `gh pr close 42` |
| `gh pr edit` | Update title, body, labels, or reviewers | `gh pr edit 42 --add-label "needs-review"` |

## Common patterns
- **Review your assigned PRs:** `gh pr list --assignee @me --state open`
- **Approve and merge:** `gh pr review 42 --approve && gh pr merge 42 --squash`
- **Create a draft PR:** `gh pr create --draft --title "WIP: feature" --body "Not ready yet"`
- **Check CI before merging:** `gh pr checks 42 --watch`
- **Target a specific repo:** append `--repo OWNER/REPO` to any command

## Reference
Full flags: `gh pr <subcommand> --help`
