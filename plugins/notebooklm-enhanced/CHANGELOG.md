# Changelog

## [0.2.0] - 2026-09-05

- Add/refresh native Codex manifest and UI metadata while retaining Claude support.
- Upgrade and lock notebooklm-py 0.8.2; add a lock-backed installed-path wrapper and offline CLI contract tests.
- Use explicit notebook/run/artifact IDs; remove shared-context automation and stale duplicated command matrices.
- Document destructive ask --new semantics and bounded research polling, correct auth checks, and label the upstream RPC client unofficial.


## [0.1.4] - 2026-06-26

### Fixed
- Documented the `notebooklm-core` skill in the README.
- Clarified that autonomous research delegation is skill-driven.
- Synced package metadata and changelog with the current marketplace release.

## [0.1.3] - 2026-03-14

### Changed
- Existing marketplace release before the 2026-06 audit pass.

## [0.1.0] - 2026-03-14

### Added
- Initial release
- Core skill for NotebookLM automation
- Research synthesis skill for multi-notebook workflows
- 7 slash commands: setup, query, add-source, create-notebook, generate, library, research
- Research agent for autonomous multi-notebook research
- Python backend using notebooklm-py RPC API
