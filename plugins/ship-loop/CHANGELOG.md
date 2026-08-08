# Changelog

All notable changes to the ship-loop plugin.

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
