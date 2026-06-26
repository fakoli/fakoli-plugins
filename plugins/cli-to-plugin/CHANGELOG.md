# Changelog

All notable changes to `cli-to-plugin` are documented here.

## [1.0.4] - 2026-05-25

### Fixed
- Made `scripts/validate-output.sh` self-contained by embedding the plugin and
  skill schemas it needs for generated-plugin validation.
- Added local schema copies for plugin and skill validation so generated output
  can be checked without relying on repository-relative schema paths.

## [1.0.3] - 2026-05-25

### Fixed
- Addressed review feedback on generated-plugin validation and command guidance.
- Tightened failure behavior in `validate-output.sh` so validation issues are
  surfaced clearly during plugin generation.

## [1.0.2] - 2026-05-25

### Added
- Initial `cli-to-plugin` release: convert a CLI with `--help` support into a
  self-contained Claude Code plugin.
- Recursive help discovery via `scripts/discover.py`, with fixtures covering
  `gh`, `docker`, `kubectl`, and pathological help-output cases.
- YAML overrides for skipped command groups, description overrides, appended
  guidance, and preselected meta-skills.
- Templates for generated group skills, workflow meta-skills, and plugin
  manifests.
- Output validation script and pytest coverage for discovery and override
  merging.
