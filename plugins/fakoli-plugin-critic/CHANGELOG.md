# Changelog

All notable changes to this plugin are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-26

Initial release. Extracted from `fakoli-crew` so plugin-development teams can install only the review layer.

### Added

- `agents/agent-critic.md` (color magenta, model opus) — reviews `<plugin>/agents/*.md`.
- `agents/skill-critic.md` (color teal, model opus) — reviews `<plugin>/skills/*/SKILL.md`.
- `agents/hook-critic.md` (color gray, model opus) — reviews `<plugin>/hooks/*.sh` + `hooks.json`.
- `agents/mcp-critic.md` (color white, model opus) — reviews `.mcp.json` + MCP server source.
- `agents/structure-critic.md` (color brown, model opus) — reviews `plugin.json` + marketplace.json + registry + README/CHANGELOG hygiene + version sync.

### Migration notes

- Existing recipes that dispatched these via `fakoli-crew:<critic>` must update the namespace to `fakoli-plugin-critic:<critic>`. Agent system prompts are unchanged in this release; only the namespace moved.
- Pair with `fakoli-crew` 2.3.0+ which removes the 5 critics from its own agent set.
