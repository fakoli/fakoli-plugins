# Changelog

## 1.1.0 — 2026-09-05

- Require isolated PyYAML parsing, reject duplicate keys and wrong field types, support --help and direct SKILL.md inputs, deduplicate roots, and separate length guidance from schema errors.
- Added native Codex discovery alongside the existing Claude entrypoints and focused offline regressions.

All notable changes to the skill-spec-lint plugin. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-08-08

### Added

- `scripts/skill_spec_lint.py`: stdlib-only linter for the deterministic Agent
  Skills spec rules — `name` charset/length/dir-match, `description` length
  (block scalars measured), `compatibility` length, the ≤500-line SKILL.md body
  ceiling, first-line frontmatter presence, and undiscoverable nested placement.
  Parses frontmatter authoritatively with PyYAML when importable, with a
  scalar-only fallback (and an honest stderr note) when it is not.
- `/skill-spec-lint` command and the `skill-spec-lint` user-invocable skill
  wrapping the script.
- `tests/test_skill_spec_lint.py`: 22 offline assertions (no pytest, no
  network), including the folded-scalar description path and the ceiling edge.
- Deliberately not wired into any CI gate — a portable, on-demand tool so it
  stays usable outside this repo.

Adversarial review before first release caught and fixed:

- A SKILL.md-less (or SKILL.md-as-a-directory) skill folder was silently
  skipped, so a broken skill reported "0 errors". Discovery now enumerates
  every immediate child of `skills/` as a candidate and reports the missing or
  non-file SKILL.md as an ERROR.
- A UTF-8 BOM (a common Windows-editor artifact) made a spec-compliant file
  read as frontmatter-less; files are now read with `utf-8-sig`.
- The no-PyYAML fallback parser diverged from PyYAML on inline `# comments` and
  multi-line plain scalars, so the same file could pass on one machine and fail
  on another. The fallback now strips trailing comments and folds continuation
  lines to match, with a forced-fallback parity test.
- Discovery walks with `os.walk(followlinks=False)` instead of `Path.rglob`, so
  a symlink loop cannot hang the scan on any Python version.
