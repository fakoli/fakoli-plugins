---
name: fleet-exec
description: "Structured remote execution over SSH for a fleet of hosts — run a command on another machine, read or write a remote file, or collect host facts, without hand-quoted ssh one-liners. Use this when the user asks to run a command on a remote host, ssh into a machine, execute something on another machine, fetch or push a remote file, or check a host's OS/python/home-dir facts. Trigger keywords — remote execution, ssh, fleet, host, run a command on another machine, fetch a remote file, push a file to a host."
---

# fleet-exec

Structured remote execution over SSH. Four MCP tools replace hand-quoted
`ssh host "some; quoted; command"` one-liners, which break silently the
moment a remote Windows host's `cmd.exe` re-splits a spaced argv or a
multi-line payload.

## Tools

- **`run_on_host(host, argv, timeout_s=30)`** — run a command on `host`.
  `argv` MUST be a list (`["ls", "-la"]`), never a shell string — a string
  reintroduces the quoting bug class this tool exists to kill, and is
  refused.
- **`fetch_text(host, path, max_bytes=256000)`** — read a remote text file,
  truncated to `max_bytes`.
- **`push_file(host, local_path, remote_path)`** — write a local file to
  `host`.
- **`host_facts(host)`** — OS family (`uname` else `ver`), python launcher,
  home dir. Facts come back as a JSON string in the row's `stdout`.

`host` is an SSH alias resolved through the caller's `~/.ssh/config` — never
a raw hostname, IP, or credential passed to the tool.

## The four states

Every tool call that reaches the network returns a row and never raises for
a remote-side problem:

```json
{"state": "ok", "rc": 0, "stdout": "...", "stderr": "...", "detail": "...", "host": "host-a"}
```

- **`ok`** — the command ran to completion. `rc` is whatever the remote
  command exited with — a remote command exiting nonzero (e.g. `rc: 3`) is
  still `state: "ok"`; only transport/launcher problems change the state.
- **`unreachable`** — ssh itself failed: connection refused, DNS failure, no
  route, timed-out connect, permission denied, or `ssh` isn't installed
  locally.
- **`not-installed`** — ssh reached the host but no Python launcher
  (`python3` then `python`) resolved there.
- **`timeout`** — the local `ssh` call exceeded `timeout_s`.

`detail`/`stderr` are stripped of the client's own `** ...` ssh advisory
banners — those never leak into either field.

## Refusals are not a fleet state

Structural problems are checked BEFORE any read or transmission and never
touch the network. A refusal comes back as an MCP error result, not a row:

```json
{"error": {"kind": "refused", "reason": "..."}}
```

Refused, unconditionally:

- `run_on_host` called with a string instead of a list argv.
- Any argv element that looks like it carries a secret: case-insensitive
  `token`, `password`, `secret`, `apikey`/`api_key`; a `key=` pattern; or a
  bare base64-ish run of 40+ characters. These are refused, not filtered or
  redacted — the call does not go out.
- `fetch_text`/`push_file` on any path whose basename matches `.env*`,
  `id_rsa*`, `*.pem`, or `credentials` — checked on the path string itself,
  before the file is opened.

## Raw ssh is fallback-only

Remote execution in an agent session goes through these tools. Raw `ssh`
calls via Bash are fallback-only now — use them only to diagnose fleet-exec
itself (e.g. confirming a host is reachable at all when `fleet-exec` reports
`unreachable` and you need to rule out a local ssh config issue). Don't
reach for a bare `ssh host "..."` Bash call as the default remote-exec path
anymore; that's exactly the quoting-bug pattern these tools replace.

anvil-serving's own `fleet version` / `fleet drift` CLI verbs are unrelated
and unaffected — those are product surface for that project, not a session
tool, and stay as they are.
