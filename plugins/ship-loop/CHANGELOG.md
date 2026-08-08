# Changelog

All notable changes to the ship-loop plugin.

## [1.1.1] - 2026-08-08

### Fixed

- `dispatch-packet` skill: an adversarial review found the worked example
  broke four rules the skill itself states. The worked example now
  enumerates the mirror PRs' actual edit set (file lists for #364 and
  #368, plus the consequence for `commands/serves.py`), sends
  rollback-check tests to the canonical `_Result` fake in
  `tests/test_serves_rollback_check.py` instead of claiming no such
  helper exists, restores the full playbook gate list including a
  mutation check and the known-local-failure caveat, and moves the open
  design question out of "Decided design" into a dedicated `## Open
  decisions (BLOCKING)` section rather than presenting it as closed and
  shippable. The template now carries a mandatory stop-and-report
  anti-stall line, a `## Context reads` section ahead of `## Why`, and a
  `MODEL TIER` header field — bumped to format `v2`.

### Added

- `tests/test-dispatch-packet-sections.sh`, wired into the PR check: the
  template skeleton's section set and the worked example's must be
  identical and in order, and the example must carry the anti-stall line
  and a recorded model tier. Section drift between the two is invisible to
  every other gate in this repo, and it is what shipped in 1.1.0.

## [1.1.0] - 2026-08-08

### Added

- `dispatch-packet` skill: generates a dispatch packet (subagent packet /
  implementer prompt) from an issue or task description — decided-design
  restatement with any open decision flagged back rather than resolved,
  grep-verified file:line anchors, mirror-PR reference, boundaries, tests
  with the injectable-runner pattern, ordered verify commands (`git add -A`
  before any `git ls-files`-based audit), the anti-stall clause, and
  `[operator]` markers. Refuses to guess when the source lacks decisions.
  Generation only — a human/orchestrator reviews the packet before any
  agent runs it.

## [1.0.0] - 2026-07-09

### Added

- Initial release: the seven-step ship loop as a user-invocable skill —
  sync/isolate (worktree off fresh origin/main), ground-truth scoping,
  precedent-mirroring implementation, reality-faithful testing, the
  eight-angle adversarial review as the merge gate (cross-process boundary
  tracer non-negotiable, findings verified against ground truth), the
  mechanical ship tail (composing with /ship-task), and loop closure
  (promotions ledger, out-of-diff issues, lesson promotion).
- `/ship-loop` Claude Code command; skills-first `.codex-plugin` manifest.
- Platform discipline distilled from live incidents: bash-heredoc backslash
  mangling, assert-anchored patch scripts, cp1252-safe output, CVE-2024-27980
  .cmd spawning, MSYS-vs-native paths.
