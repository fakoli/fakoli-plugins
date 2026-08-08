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
- `push_file` size bound (16 000 bytes): a larger payload would exceed the
  OS argv cap and fail with an error naming neither the file nor the limit.

### Security

- `host` is validated against `[alnum._-]` with an optional `user@` prefix.
  ssh reads a leading-dash positional as an option, so a `host` of
  `-oProxyCommand=<cmd>` ran `<cmd>` **locally** before any connection —
  arbitrary local command execution through the one field that had no guard.
  List-argv does not cover this: the injection is into ssh's own option
  parser, not a shell. The guard sits in the single chokepoint every tool
  passes through, plus ahead of `push_file`'s local read.

### Fixed

- `run_on_host`'s remote wrapper catches `OSError`. A missing remote binary
  raised an uncaught `FileNotFoundError`, killing the wrapper before it wrote
  its JSON — so a healthy, reachable host running a typo'd command was
  reported `unreachable`. It now returns `state: "ok"` with `rc: 127`, which
  is what the four-state contract always promised.
- `timeout_s` and `max_bytes` are clamped (600 s / 1 000 000 bytes) instead of
  being accepted unbounded.
- Id-less JSON-RPC requests are never answered. Notifications were matched by
  method name, so `notifications/cancelled` — which real MCP clients send —
  drew a `-32601` reply with a null id, violating JSON-RPC 2.0 §4.1. The
  guard now keys on the absence of `id`, covering every notification.
