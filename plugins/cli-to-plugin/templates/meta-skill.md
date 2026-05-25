<!-- Template: structural reference for the cli-to-plugin generator. Claude reads this to understand expected shape. NOT a Jinja template — no placeholder substitution. -->

---
name: gh-review-and-merge
description: Use when the user wants to review pending pull requests assigned to them and merge approved ones. Multi-step workflow using the `gh` CLI.
user-invocable: true
disable-model-invocation: false
argument-hint: "[repo]"
allowed-tools: Bash
---

# Review and merge PRs

## When to use
- "Review my pending PRs"
- "Are there any PRs waiting on me?"
- "Merge the approved PR"
- The user wants a guided, end-to-end PR review and merge session.

## Workflow
1. **List assigned PRs**
   Run `gh pr list --assignee @me --state open` to see what needs attention.

2. **Inspect each candidate**
   For each PR, run `gh pr view <N>` to read the description and `gh pr checks <N>` to confirm CI is green.

3. **Review and comment**
   Use `gh pr review <N> --approve` to approve, or `gh pr review <N> --request-changes --body "..."` to flag issues.

4. **Merge approved PRs**
   Run `gh pr merge <N> --squash --delete-branch` for a clean merge. Prefer `--rebase` when the branch history is meaningful.

5. **Confirm merge**
   Run `gh pr view <N>` after merging and verify the state shows `MERGED`.

## Variants
- **Specific repo:** append `--repo OWNER/REPO` to every `gh pr` command.
- **Auto-merge on green CI:** `gh pr merge <N> --squash --auto` sets the PR to merge as soon as checks pass.
- **Batch review:** iterate with `gh pr list --assignee @me --json number --jq '.[].number'` to get all PR numbers and loop.

## Related
- [[gh-pr]] — full PR command reference (list, create, review, merge flags)
- [[gh-issue]] — issue triage and linking
- [[gh-workflow]] — inspect CI runs before merging
