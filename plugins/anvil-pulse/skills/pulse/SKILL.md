---
name: pulse
description: Start, stop, or check the anvil-pulse dashboard — a live local web page showing active anvil claims (actor, phase, elapsed, lease countdown), the event feed, and stuck-state detection (healthy / quiet / possibly wedged / lease expired) for long autonomous runs. Use when the user asks to "watch this run", "open the anvil dashboard", "is the agent stuck?", "monitor the claims", "start/stop pulse", or wants a heartbeat view of an anvil project. Also installs an optional Claude Code statusline segment on request. Read-only over anvil state; sends nothing externally.
---

# anvil pulse

A local operator dashboard for anvil projects. It polls `anvil status --json`
and tails the append-only `events.jsonl`, then serves a single self-contained
web page. It never writes anvil state.

Resolve `PLUGIN_ROOT` from this installed skill (`../..`), not from the target project or an assumed shell variable. Keep the project path explicit.

## Toolkit (bundled)

```
$PLUGIN_ROOT/scripts/start-server.sh   # start (prints {"event":"server-started","url":...})
$PLUGIN_ROOT/scripts/stop-server.sh    # stop
$PLUGIN_ROOT/scripts/check-server.sh   # is it running?
$PLUGIN_ROOT/scripts/statusline-segment.sh  # optional Claude Code statusline segment
```

All scripts take `--project-dir <path>` (default: cwd). Requires `node` and the
`anvil` CLI on PATH.

## Start the dashboard

1. Confirm the target project is anvil-initialized: `anvil status --json --cwd <project>`
   exits 0. If not, tell the user and stop — the dashboard has nothing to show.
2. Run:
   ```bash
   bash "$PLUGIN_ROOT/scripts/start-server.sh" --project-dir <project>
   ```
3. Parse the JSON line and give the user the `url`. Suggest opening it in a
   browser; it live-updates every ~2.5s.
4. On Windows/Git Bash and environments setting `CODEX_CI`, the script auto-runs in the foreground
   (detached processes get reaped there). In that case start it with the shell
   tool's background/run-in-background mode so it survives the turn, or tell
   the user to run it in a separate terminal:
   `bash .../start-server.sh --project-dir <project> --foreground`

Options worth knowing: `--port <n>` for a stable URL, `--state-dir <dir>` if
anvil state lives in a non-default workspace dir (auto-discovery checks
`<project>/.anvil`, `<project>/bin/.anvil`, then the exact path-hashed workspace under
`~/.anvil/workspaces/`. A same-named checkout is never selected as a fallback;
use an explicit `--state-dir` for legacy or custom layouts).

Suggest adding `.anvil-pulse/` to the project's `.gitignore` (pid/log files
live there).

## Stop / check

```bash
bash "$PLUGIN_ROOT/scripts/stop-server.sh"  --project-dir <project>
bash "$PLUGIN_ROOT/scripts/check-server.sh" --project-dir <project>
```

## Reading the board

- Each active claim card shows task, actor, latest `progress.noted` phase,
  elapsed time, live lease countdown, and time since last observed event.
- Staleness classification (server defaults via `PULSE_QUIET_SECONDS` /
  `PULSE_WEDGED_SECONDS` = 300/900; retune live per request with
  `/api/pulse?quiet_seconds=600&wedged_seconds=1800` — no restart needed):
  - **healthy** — activity within the quiet threshold
  - **quiet** — no activity for 5-15 min; often a long tool call or model wait
  - **possibly wedged** — silent beyond 15 min with a live lease; worth a look
  - **lease expired** — the claim's lease ran out; the run may have died
- When the user asks "is it stuck?", read `/api/pulse` yourself and answer from
  `claims[].staleness` + `last_activity_seconds` instead of guessing:
  `curl --fail --silent --show-error --max-time 10 http://localhost:<port>/api/pulse`

## Optional: Claude Code statusline segment

Only on explicit request — this edits the user's own statusline script.
Requires `python3` or `python` on PATH (the segment parses anvil's JSON;
on Windows, `python3` is often a broken WindowsApps stub, so the script tries
both — but at least one must actually work).

1. Read `~/.claude/settings.json` -> `statusLine.command` to find the script
   (commonly `~/.claude/statusline-command.sh`). If no statusline is configured,
   explain how to set one up instead of creating files unasked.
2. IDEMPOTENCY CHECK: grep the script for `# anvil-pulse segment` first. If
   present, the segment is already installed — update the existing block in
   place if the path changed; NEVER append a second copy (it would render
   twice).
3. For a requested installation, append this snippet to the END of
   their script after inspecting its existing structure (it prints nothing outside anvil projects):
   ```bash
   # anvil-pulse segment
   pulse_seg="$(bash "<absolute-plugin-path>/scripts/statusline-segment.sh" "$workspace_dir" 2>/dev/null)"
   [[ -n "$pulse_seg" ]] && printf ' | %s' "$pulse_seg"
   ```
   Replace `<absolute-plugin-path>` with the resolved installed plugin root
   and `$workspace_dir` with however their script names the current workspace
   variable (read the script first; do not assume).
4. The segment caches `anvil status` for 10s (`ANVIL_PULSE_STATUSLINE_TTL`)
   under `~/.cache/anvil-pulse/`; on a transient anvil failure it serves the
   previous cached segment instead of blanking.

## Other harnesses

- **Codex**: start the server in a persistent terminal and open its browser page.
  This plugin supplies a dashboard skill; it does not configure recurring
  automation or notifications merely by starting the dashboard.
- **OpenClaw**: see `$PLUGIN_ROOT/docs/openclaw.md` for the zero-code
  Gateway cron recipe (`anvil notify-digest --announce`) and the planned
  control-ui embed.
