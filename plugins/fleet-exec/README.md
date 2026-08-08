# fleet-exec

Structured remote-execution MCP server for Claude Code. Replaces hand-quoted
`ssh host "..."` one-liners with four typed tools that never raise on a
remote-side failure and refuse secret-shaped or credential-file requests
before anything is read or sent.

## Why

A bare `ssh host "some command"` Bash call looks fine until the remote host
is Windows: `cmd.exe` re-splits the ssh-joined command line, so any argv
element with a space silently breaks, and a multi-line payload breaks
always. fleet-exec fixes this by shipping every operation as a small Python
script, base64-encoded into one shell-inert token, executed via
`ssh host <launcher> -c <payload>` — the remote shell never sees anything it
could misparse.

## Features

### MCP Tools

| Tool | Purpose |
|------|---------|
| `run_on_host(host, argv, timeout_s=30)` | Run a list-argv command on a host. |
| `fetch_text(host, path, max_bytes=256000)` | Read a remote text file, truncated. |
| `push_file(host, local_path, remote_path)` | Write a local file to a host. |
| `host_facts(host)` | OS family, python launcher, home dir. |

### The four states

Every tool call returns a row instead of raising: `state` is one of `ok`
(the command ran — including a nonzero remote exit code), `unreachable`
(ssh/transport failure), `not-installed` (no python launcher on the remote),
or `timeout` (the local ssh call exceeded `timeout_s`). See
`skills/fleet-exec/SKILL.md` for the full contract.

### Refusals

A `host` that is not a plain ssh alias (ssh reads a leading-dash positional
as an option, and `-oProxyCommand=<cmd>` would run `<cmd>` locally),
`run_on_host` with a string instead of a list argv, any argv element that
looks like it carries a secret (`token`/`password`/`secret`/`apikey`,
`key=`, or a 40+ char base64-ish run), and `fetch_text`/`push_file` on
`.env*`/`id_rsa*`/`*.pem`/`credentials` paths are all refused before any
read or transmission — returned as an MCP error result, never mistaken for
a host condition. `push_file` also refuses a local file over 16 000 bytes:
the payload ships as one base64 ssh argv element, and past the OS
argument-length cap ssh fails with an error that names neither the file nor
the limit.

## Installation

Add the `fakoli-plugins` marketplace and install `fleet-exec`, or reference
it directly in your `.mcp.json`. The server launches via `uv run --directory
${CLAUDE_PLUGIN_ROOT} python -m fleet_exec` — `uv` resolves a deterministic
interpreter, sidestepping the same local `python`/`python3` launcher
divergence this plugin fixes on the remote side. No dependency is
installed; the project has none (stdlib only, hand-rolled MCP stdio
protocol).

## Configuration

`.mcp.json` sets two env vars, both overridable per tool call:

| Variable | Default | Meaning |
|----------|---------|---------|
| `FLEET_EXEC_TIMEOUT` | `30` | Default `timeout_s` for `run_on_host` (clamped to 600). |
| `FLEET_EXEC_MAX_BYTES` | `256000` | Default `max_bytes` for `fetch_text` (clamped to 1 000 000). |

Hosts are resolved through the caller's `~/.ssh/config` — see
`config/fleet.example.toml` for the placeholder shape. fleet-exec never
reads real hostnames, IPs, or credentials from its own config; it only
takes the SSH alias you'd otherwise pass to `ssh`.

## Migration

Remote execution in agent sessions now goes through the fleet-exec MCP
tools (`run_on_host`, `fetch_text`, `push_file`, `host_facts`), not raw
`ssh host "..."` calls via Bash. That pattern — a shell-quoted command
string handed to Bash's `ssh` — is retired as the default remote-exec path;
it's fallback-only now, for diagnosing fleet-exec itself when a tool call
reports `unreachable` and you need to rule out a local ssh/config problem.

This is a session-tool change, not a product-surface change: anvil-serving's
own `fleet version` and `fleet drift` CLI verbs are a separate product
surface and are unaffected — they keep working exactly as before.

## Development

```bash
uv run --directory plugins/fleet-exec --extra dev pytest tests -q
```

Tests fake the `subprocess.run` boundary (`fleet_exec.transport._run`) — no
real ssh or network calls.

## License

MIT
