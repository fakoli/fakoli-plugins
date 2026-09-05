# Changelog

## 1.1.0 — 2026-09-05

- Review the actual requested base and working-tree scope, distinguish reproduced failures from code-supported risks, use isolated probes, and preserve existing authorization to fix defects.
- Added native Codex discovery alongside the existing Claude entrypoints and focused offline regressions.

All notable changes to the recall-mode-verifier plugin. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-07-09

### Added

- `recall-mode-verifier` skill: a spec-independent breakage-probe procedure
  along four axes (fail-closed, malformed-input, resource-exhaustion,
  state-drift) for pre-PR / anvil verify-left review. `/recall-verify`
  command. Skills-first (Codex-portable), so anvil execute can invoke it
  cross-repo.
