# fleet-exec

Structured SSH execution for Codex and Claude Code. Four MCP tools run a list of arguments, read bounded text, write a small file, or inspect host facts. The remote Python wrapper preserves argument boundaries across POSIX and Windows shells.

## Requirements and launch

Install through the repository marketplace for your runtime. The local machine needs `uv`, Python 3.10+, and `ssh`; remote hosts need Python 3. Configure SSH authentication and host aliases in the user's SSH configuration.

The native manifest loads `.codex-plugin/mcp.json`, whose `cwd: "."` resolves to the installed plugin root and launches `uv run --frozen --project . python -m fleet_exec`. Claude uses `.mcp.json` and its `${CLAUDE_PLUGIN_ROOT}` expansion. The launchers use the bundled lockfile. Package setup may download a Python interpreter/build tooling; the server has no runtime Python dependencies.

Native relative working-directory behavior is implemented by the [Codex MCP parser](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/plugin_config.rs). Native argument strings do not rely on the hook-only root variable convention.

## Tools and results

| Tool | Purpose |
|---|---|
| `run_on_host(host, argv, timeout_s=30)` | Execute a nonempty list of string arguments. |
| `fetch_text(host, path, max_bytes=256000)` | Read remote UTF-8 text with replacement for invalid bytes. |
| `push_file(host, local_path, remote_path)` | Replace the destination with a local file of at most 16,000 bytes. |
| `host_facts(host)` | Read OS, Python launcher, and home information. |

A completed remote command returns `state: "ok"` and its actual `rc`; a nonzero exit code is still an operation failure. Transport states are `unreachable`, `not-installed`, and `timeout`. The local deadline includes five seconds of grace for the remote timeout response. Multiple launcher attempts can extend total wall time. A timeout does not prove that all remote descendants stopped or that a write had no effect.

Malformed calls return errors before SSH starts. The server also rejects string commands, malformed argument elements, option-shaped hosts, secret-shaped arguments, sensitive file basenames, and oversized uploads. These are heuristics, not comprehensive secret detection. Hosts can be aliases, simple hostnames, IPv4 addresses, or `user@host`; alias-only enforcement is not claimed. See the [skill](skills/fleet-exec/SKILL.md) for the full operating contract.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FLEET_EXEC_TIMEOUT` | `30` | Default command timeout; MCP tool values are clamped to 600 seconds. |
| `FLEET_EXEC_MAX_BYTES` | `256000` | Default text read limit; MCP tool values are clamped to 1,000,000 bytes. |

Edit the appropriate runtime MCP configuration or pass explicit tool parameters. The example in `config/fleet.example.toml` documents host naming; the server does not load a fleet inventory.

## Verification

From the repository root:

```bash
uv run --project plugins/fleet-exec --extra dev pytest plugins/fleet-exec/tests -q
```

Tests fake SSH and cover quoting, refusals, transport failures, timeouts, missing remote commands, malformed wrapper output, and recoverable JSON-RPC input errors. They do not contact a host. The stdio protocol follows [MCP JSON-RPC conventions](https://modelcontextprotocol.io/specification/2025-06-18/basic).

MIT licensed.
