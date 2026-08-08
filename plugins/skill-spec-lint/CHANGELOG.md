# Changelog

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
