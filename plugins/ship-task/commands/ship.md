---
description: Ship the current branch — push, open a PR, wait for CI, squash-merge, sync base, and optionally run a post-merge command. Runs after review; never gates quality.
argument-hint: '"PR title" [--then "cmd"] [--dry-run]'
---

Run the ship-task tail on the current branch. **Review and verification must
already have passed** — this command does not review code; it only performs the
mechanical push → PR → wait-for-CI → merge → sync sequence, and if CI fails it
stops and leaves the PR open.

Invoke the bundled script, passing through the user's arguments (`$ARGUMENTS`):

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/ship.sh" $ARGUMENTS
```

If the user gave no arguments, run `"${CLAUDE_PLUGIN_ROOT}/scripts/ship.sh" --help`
and ask for a PR title (and an optional `--then` post-merge command, e.g.
`--then "anvil apply <task> --approve --reviewer <me>"`).

Report back only the final `ship:` summary line (PR number, CI result, merge SHA,
sync status, post-merge status, URL). On exit `5` the PR IS already merged —
only the local base sync was skipped or failed (e.g. the base branch lives in
another worktree); ship attempts the remote-branch cleanup itself and warns if
that fails. Tell the user the PR merged and how to finish the sync, and do NOT
re-run ship. On any other non-zero exit, surface the failing checks or error
the script printed and leave the PR open for the user to decide (note: if the
script says the PR state "could not be verified", check the PR on GitHub —
it may have merged despite the error).
