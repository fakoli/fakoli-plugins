# ship-task

**The mechanical tail of a one-PR-per-task loop, as a single command.**

When you ship work one PR per task, the same deterministic dance runs every time:
push the branch, open a PR, wait for CI, squash-merge and delete the branch, sync
the base branch, and (often) run one post-merge step like `anvil apply`. Done by
hand — or by an agent issuing six separate `git`/`gh` calls — that boilerplate
dumps a screenful of output into the context window on every task.

`ship-task` collapses it into one command that prints **one line per stage** and a
final summary, so the loop stays out of your context. It runs **after** your review
and verification pass: it makes no quality judgement, and if CI fails it stops and
leaves the PR open for you to decide.

## Install

Via the Fakoli marketplace:

```
/plugin marketplace add fakoli/fakoli-plugins
/plugin install ship-task
```

Requires [`git`](https://git-scm.com) and the [GitHub CLI `gh`](https://cli.github.com),
authenticated (`gh auth login`).

## Usage

```bash
# via the bundled script directly
SHIP="${CLAUDE_PLUGIN_ROOT}/scripts/ship.sh"

"$SHIP" "feat(auth): add token refresh"                       # push → PR → CI → merge → sync
"$SHIP" "fix: race in reaper" --body-file /tmp/body.md        # PR body from a file
"$SHIP" "feat: gate" --then "anvil apply T007 --approve --reviewer me"   # + post-merge step
"$SHIP" "wip: spike" --draft                                  # open a draft PR, stop
"$SHIP" "feat: x" --dry-run                                   # print the plan, touch nothing
```

Or the slash command: `/ship "PR title" --then "…"`. Or let an agent invoke the
`ship-task` skill when you say "ship this."

### What it does, in order

1. **Preflight** — verify `git`/`gh` are present, you're in a repo on a non-base
   branch, and warn if the working tree has uncommitted changes (they won't be in
   the PR — ship pushes only what's committed).
2. **Push** the current branch (`git push -u origin HEAD` — survives long branch
   names that break `push origin <branch>`).
3. **Open a PR** against the base branch (reusing an existing PR for the branch if
   one is already open).
4. **Wait for CI** — poll `gh pr checks` until every check is terminal. On failure
   or timeout, stop and leave the PR open (exit 2).
5. **Merge** (`--squash --delete-branch` by default) and capture the merge SHA.
6. **Sync** — checkout the base branch and fast-forward pull.
7. **`--then`** — run an optional post-merge command (the composition seam for
   task engines like [anvil](https://github.com/fakoli/anvil)).

Final line, e.g.:

```
ship: PR #161 · CI passed · merged abc123def · sync ok · then ok · https://github.com/org/repo/pull/161
```

## Options

| Flag | Default | Purpose |
|------|---------|---------|
| `"PR title"` | *(required)* | positional — the PR title |
| `--body TEXT` | — | PR body, inline |
| `--body-file FILE` | — | PR body from a file (`-` = stdin) |
| `--base BRANCH` | repo default branch | base to target and sync |
| `--then "CMD"` | — | shell command run after a successful merge |
| `--draft` | off | open a draft PR and stop (no CI wait, no merge) |
| `--no-wait` | off | skip CI polling; merge as soon as mergeable |
| `--squash` / `--merge` / `--rebase` | `--squash` | merge method |
| `--admin` | off | pass `--admin` to `gh pr merge` |
| `--unset-token` | off | run every `gh` call as `env -u GITHUB_TOKEN gh …` |
| `--poll-secs N` | `20` | CI poll interval |
| `--timeout-secs N` | `1800` | max CI wait before giving up |
| `--dry-run` | off | print the plan and exit; change nothing |

### `--unset-token`

Some environments export a `GITHUB_TOKEN` (an ambient PAT) that lacks the scope
`gh` needs, while `gh`'s own keyring login works once that variable is unset.
`--unset-token` runs every `gh` call as `env -u GITHUB_TOKEN gh …` so the keyring
auth is used instead. Leave it off unless you hit permission errors.

### `--then` and task engines

`ship-task` is deliberately tool-agnostic. Anvil (and any similar task engine) is
integrated purely by composition, not coupling — the engine's "mark this task
accepted" step is just a post-merge command:

```bash
ship "feat(state): claims (task:T007)" \
  --body-file /tmp/pr.md \
  --then "anvil apply evidence-contracts:T007 --approve --reviewer me"
```

If `--then` fails, ship reports it and exits `4` — the PR is already merged, so you
only need to re-run the post-merge step.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | shipped (and `--then`, if any, succeeded) |
| `1` | usage or preflight error (nothing changed) |
| `2` | CI failed or timed out — PR left open |
| `3` | merge failed — PR left open |
| `4` | merge succeeded but the `--then` command failed |
| `5` | **merged remotely**, but the local base sync was skipped or failed — the base branch is checked out in another worktree, the checkout errored, or the pull did not fast-forward. The PR is merged; ship attempts remote-branch cleanup (a warning is printed if that fails). Do not re-run ship — sync the base locally. `--then` is skipped. |

The summary line carries the sync outcome as `sync <ok|worktree|pull-failed|failed>`.

## Scope

- **After review only.** ship performs mechanics, not review. Gate quality (tests,
  an adversarial critic, whatever your process is) *before* calling it.
- **Commits are yours.** ship pushes what's committed; it never runs `git add` or
  `git commit`.
- **GitHub PRs.** ship targets `gh`-backed GitHub repositories.

## License

MIT — see [LICENSE](LICENSE).
