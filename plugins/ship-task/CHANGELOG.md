# Changelog

All notable changes to the ship-task plugin are documented here.

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
