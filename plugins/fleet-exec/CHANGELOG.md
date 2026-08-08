# Changelog

All notable changes to the fleet-exec plugin. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-08-08

### Added

- `fleet-exec` MCP server (stdlib only, hand-rolled stdio JSON-RPC — no
  `mcp` dependency): `run_on_host`, `fetch_text`, `push_file`, `host_facts`.
- Base64-wrapped remote python payloads and a `python3`/`python` launcher
  probe loop, ported from anvil-serving's live-tested `fleet.py` semantics,
  to survive ssh -> `cmd.exe` re-splitting on Windows remotes.
- Four-state contract (`ok`/`unreachable`/`not-installed`/`timeout`) —
  tools never raise on a remote-side failure; a nonzero remote exit code is
  still `state: "ok"`.
- Structural refusals (list-argv-only, secret-shaped argv, `.env*`/`id_rsa*`/
  `*.pem`/credentials paths) checked before any read or transmission,
  returned as an MCP error result distinct from the four host states.
- `local_hostname_matches` host-id comparison helper.
- `fleet-exec` skill documenting the tool contract and the raw-ssh
  fallback-only migration note.
