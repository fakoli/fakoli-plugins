# Changelog

All notable changes to the ship-task plugin are documented here.

## [1.1.0] - 2026-07-13

### Fixed

- Remote merge state and local sync are now separate stages with separate
  outcomes (#137). When the base branch is checked out in another worktree,
  `gh pr merge` merges the PR on GitHub and then exits nonzero on its local
  sync — ship treated that as an unqualified merge failure and left the
  remote feature branch undeleted. Now, after any nonzero merge command, ship
  re-queries the PR state: if it is `MERGED`, ship finishes the remote branch
  cleanup itself and continues; only a genuinely un-merged PR exits 3.
- The base-branch checkout is no longer required to succeed in multi-worktree
  layouts: when another worktree owns the base branch, ship skips the local
  checkout with a pointer to sync there instead of dying.

### Added

- Exit code 5: merged remotely but local base sync was skipped or failed
  (partial success) — the base branch owned by another worktree, a checkout
  error, or a non-fast-forward `git pull`. `--then` is skipped in that case
  (it would run against an unsynced base), and the summary line now carries
  a `sync <ok|worktree|pull-failed|failed>` field. SKILL.md, README, and the
  `/ship` command doc were updated to the new contract.
- Integration test (`tests/test-ship-worktree.sh`, wired into pr-check CI):
  base branch in a dirty worktree A, feature branch in worktree B, stubbed
  `gh` reproducing the merged-remotely-but-exited-nonzero failure mode, plus
  non-fast-forward-pull and genuine-merge-failure cases.

### Fixed (post-review)

- A non-fast-forward `git pull` after checkout previously kept `sync ok`,
  ran `--then` against the stale base, and exited 0 — now exit 5 with
  `--then` skipped, consistent with the other local-sync failures.
- Worktree detection now matches the base branch as a fixed string
  (`grep -qxF`), so branch names containing regex metacharacters (e.g.
  `release-1.2`) cannot match a different worktree's branch line.

## [1.0.1] - 2026-07-08

### Fixed

- CI-registration race: a freshly-opened PR reports no checks for a few seconds
  while GitHub registers its workflows. ship treated that initial emptiness as
  "no CI" and merged immediately — before CI ran (caught dogfooding on a repo
  whose test job took ~3 min to start). A grace window (`CHECK_GRACE_SECS`,
  default 60s) now distinguishes "not registered yet" from "repo has no CI", so
  ship waits for checks to appear before concluding there are none.

## [1.0.0] - 2026-07-08

### Added

- `scripts/ship.sh` — push the current branch, open a PR, wait for CI to reach a
  terminal state, squash-merge and delete the branch, sync the base branch, and
  optionally run a `--then` post-merge command. Compact one-line-per-stage output;
  stops and leaves the PR open on CI failure.
- `/ship` command and a `ship-task` skill wrapping the script.
- Flags: `--body`/`--body-file`, `--base`, `--then`, `--draft`, `--no-wait`,
  `--squash`/`--merge`/`--rebase`, `--admin`, `--unset-token`, `--poll-secs`,
  `--timeout-secs`, `--dry-run`.
