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
bash <plugin>/scripts/start-server.sh
# -> {"event":"server-started","url":"http://localhost:PORT/", ...}

bash <plugin>/scripts/check-server.sh
bash <plugin>/scripts/stop-server.sh
```

In Claude Code, just use `/pulse` (or ask: "watch this run"). Add
`.anvil-pulse/` to your project `.gitignore` (pid/log files live there).

Requirements: `node` (any recent LTS), the `anvil` CLI on PATH, `bash`
(Git Bash works on Windows).

## Harness support

| Harness | Produce heartbeats | Display |
|---|---|---|
| Claude Code | anvil plugin hooks (already shipping) | this dashboard + optional statusline segment (`/pulse statusline`) |
| Codex | same anvil hooks (loaded from the plugin cache) | this dashboard in a browser — Codex has no in-TUI surface |
| OpenClaw | anvil's native OpenClaw plugin | this dashboard, plus zero-code Gateway cron digest — see [docs/openclaw.md](docs/openclaw.md) |

## Stuck detection

Thresholds are env-tunable on the server: `PULSE_QUIET_SECONDS` (default 300)
and `PULSE_WEDGED_SECONDS` (default 900). A claim with an expired lease is
always `lease expired`. Classifications are advisory — the board flags, the
operator decides.

## API

- `GET /api/pulse` — everything the page renders (status + enriched claims +
  events + warnings), for scripting: `curl -s localhost:PORT/api/pulse`
- `GET /healthz` — liveness

## License

MIT
