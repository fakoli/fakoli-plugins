# Changelog

All notable changes to the anvil-pulse plugin.

## [1.0.0] - 2026-07-09

Initial release, hardened by an 8-angle adversarial review before merge.

### Added

- Local web dashboard for anvil runs — task rollups, active claims (actor,
  phase, elapsed, live lease countdown), event feed tail, and per-claim
  staleness classification (healthy / quiet / possibly-wedged / lease-expired).
- Dependency-free Node server (`scripts/server.cjs`) with PID-file lifecycle
  scripts (`start-server.sh` / `stop-server.sh` / `check-server.sh`), including
  auto-foreground on Windows/Git Bash and Codex CI (detached-process reapers).
- `pulse` skill + `/pulse` Claude Code command.
- Optional Claude Code statusline segment (`scripts/statusline-segment.sh`)
  with a 10s status cache in `~/.cache/anvil-pulse/`; installed only on
  explicit user request, idempotently.
- Codex packaging (`.codex-plugin/plugin.json`, skills-first) and OpenClaw
  guidance (`docs/openclaw.md`: Gateway cron digest recipe, planned control-ui
  embed).
- Per-request staleness tuning: `/api/pulse?quiet_seconds=&wedged_seconds=`.

### Fixed (pre-merge review findings)

- Event payloads are read from `payload_json` — the key real anvil writes —
  not `payload` (the event feed's phase/notes column was empty against
  production anvil; the test fixture had encoded the same wrong key).
- HOME-workspace discovery now looks at the real depth
  (`~/.anvil/workspaces/<key>/.anvil/events.jsonl`) and matches the workspace
  by anvil's own slug+sha256 project key instead of guessing newest-mtime
  across all projects (cross-project event misattribution); name-only
  fallback matches are surfaced as an explicit warning.
- Windows anvil resolution: the binary is resolved once at startup via
  `where` (prefer `.exe`, else run the `.cmd` shim through `cmd.exe /d /s /c`
  with verbatim quoting). Replaces an ASCII allowlist that permanently locked
  out non-ASCII usernames and `Program Files (x86)` paths.
- Status cache is stamped on completion (not dispatch) and reuses the
  in-flight promise, so a slow `anvil status` can no longer stack overlapping
  subprocesses behind itself.
- `check-server.sh` no longer reports a stale URL after a foreground restart
  (foreground mode clears the old background log).
- Lifecycle scripts guard against PID recycling: a recorded PID is only
  killed if the process still looks like the dashboard.
- Statusline segment: falls back `python3` → `python` (WindowsApps stub),
  serves the previous cache on transient anvil failures instead of blanking
  for a full TTL, shows sub-minute leases as `45s!` instead of `0m`, and
  keeps its cache in a private dir instead of a predictable `/tmp` path.
- Events-path discovery and tail parsing are cached (30s / file size+mtime),
  and the dashboard only rebuilds DOM on new data — the 1s tick updates
  countdown text nodes in place (text selection survives; no per-second
  innerHTML churn).
