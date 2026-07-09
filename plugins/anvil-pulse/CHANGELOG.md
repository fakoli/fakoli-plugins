# Changelog

All notable changes to the anvil-pulse plugin.

## [0.1.0] - 2026-07-09

### Added

- Initial release: local web dashboard for anvil runs — task rollups, active
  claims (actor, phase, elapsed, live lease countdown), event feed tail, and
  per-claim staleness classification (healthy / quiet / possibly-wedged /
  lease-expired).
- Dependency-free Node server (`scripts/server.cjs`) with PID-file lifecycle
  scripts (`start-server.sh` / `stop-server.sh` / `check-server.sh`), including
  auto-foreground on Windows/Git Bash and Codex CI (detached-process reapers).
- `pulse` skill + `/pulse` Claude Code command.
- Optional Claude Code statusline segment (`scripts/statusline-segment.sh`)
  with a 10s status cache; installed only on explicit user request.
- Codex packaging (`.codex-plugin/plugin.json`, skills-first) and OpenClaw
  guidance (`docs/openclaw.md`: Gateway cron digest recipe, planned control-ui
  embed).
