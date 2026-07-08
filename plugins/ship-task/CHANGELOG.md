# Changelog

All notable changes to the ship-task plugin are documented here.

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
