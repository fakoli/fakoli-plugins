# anvil-pulse

Live operator dashboard for long autonomous [anvil](https://github.com/fakoli/anvil)
runs. One local web page answers the question every multi-hour agent run
eventually raises: **is this still going, or is it wedged?**

![category: workflow](https://img.shields.io/badge/category-workflow-blue)

## What it shows

- **Task rollups** — ready / in progress / needs review / blocked / done
- **Active claims** — task, actor, latest `progress.noted` phase, elapsed time,
  live lease countdown, time since last observed event
- **Staleness per claim** — `healthy` / `quiet` / `possibly wedged` /
  `lease expired`, computed from heartbeat evidence in the event stream
- **Event feed** — the tail of anvil's append-only `events.jsonl`

## How it works

A dependency-free Node server (stdlib only) polls `anvil status --json` (cached,
~2s TTL) and tails `events.jsonl`, serving a self-contained HTML page that
refreshes every 2.5s. Read-only over anvil state: it never opens `state.db`
for writing — status is a read verb and the JSONL is opened read-only. Binds
`127.0.0.1` by default; sends nothing externally.

## Quick start

```bash
# from your anvil project
bash "<plugin>/scripts/start-server.sh" --project-dir "/path/to/project"
# -> {"event":"server-started","url":"http://localhost:PORT/", ...}

bash "<plugin>/scripts/check-server.sh" --project-dir "/path/to/project"
bash "<plugin>/scripts/stop-server.sh" --project-dir "/path/to/project"
```

In Claude Code, just use `/pulse` (or ask: "watch this run"). Add
`.anvil-pulse/` to your project `.gitignore` (pid/log files live there).

Requirements: `node` (any recent LTS), the `anvil` CLI on PATH, `bash`
(Git Bash works on Windows).

## Harness support

| Harness | Produce heartbeats | Display |
|---|---|---|
| Claude Code | anvil plugin hooks (already shipping) | this dashboard + optional statusline segment (`/pulse statusline`) |
| Codex | heartbeat events supplied by your Anvil workflow | this dashboard in a browser |
| OpenClaw | anvil's native OpenClaw plugin | this dashboard, plus zero-code Gateway cron digest — see [docs/openclaw.md](docs/openclaw.md) |

Both `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json` expose the dashboard skill. Resolve scripts from the installed plugin, then pass the intended project explicitly. Start in a persistent terminal when the runtime reaps detached processes. A running dashboard does not itself schedule assistant monitoring.

State discovery checks local `.anvil` directories and the exact path-hashed Anvil workspace. Same-named workspaces are not a fallback. For custom/legacy layouts pass `--state-dir` explicitly. Start/check/stop verify the recorded PID belongs to this package's server and this project; unrelated Node processes are left alone.

## Stuck detection

Thresholds are env-tunable on the server: `PULSE_QUIET_SECONDS` (default 300)
and `PULSE_WEDGED_SECONDS` (default 900). A claim with an expired lease is
always `lease expired`. Classifications are advisory — the board flags, the
operator decides.

## API

- `GET /api/pulse` — everything the page renders (status + enriched claims +
  events + warnings), for scripting: `curl --fail --max-time 10 localhost:PORT/api/pulse`
- `GET /healthz` — liveness

## Verification

```bash
python3 -m unittest discover -s plugins/anvil-pulse/tests -p 'test_*.py' -v
```

Requires Bash, Node, curl, and Python. Tests use temporary projects, a fake Anvil command, and local ephemeral HTTP ports. They cover isolated workspace discovery, malformed input, and preservation of unrelated processes; no real Anvil project is modified.

## License

MIT
