# anvil-pulse on OpenClaw

OpenClaw has the richest display surfaces of the three supported harnesses, but
anvil-pulse's own web dashboard works there unchanged (it is harness-neutral:
it reads anvil state, not harness state). This doc covers the OpenClaw-native
options.

## Zero-code today: Gateway cron + notify-digest

OpenClaw's Gateway can announce anvil's one-line digest (needs-review count,
blocked count, leases expiring soon) to a channel on a schedule — no plugin
code required:

```bash
openclaw cron add --name anvil-digest \
  --schedule "*/15 * * * *" \
  --announce <your-channel> \
  --command 'anvil notify-digest'
```

`anvil notify-digest` is silent when there is nothing to report and always
exits 0, so the cron never spams or fails. See anvil's
`docs/how-to/using-anvil-on-any-harness.md` (Gateway cron recipes) — `anvil
install openclaw` prints these recipes too.

## The web dashboard next to OpenClaw

Run the pulse server on the machine where the anvil project lives:

```bash
bash scripts/start-server.sh --project-dir <project> --port 7457
```

The board complements OpenClaw's own control UI: OpenClaw's `workboard` shows
agent-owned issues/sessions; anvil-pulse shows anvil claims, leases, phases,
and the event feed for one project.

## Planned: control-ui embed (follow-up, not shipped)

OpenClaw supports plugin-registered Gateway RPC methods (the
`admin-http-rpc` extension pattern: `gatewayMethodDispatch` +
an allowlisted method) and control-ui pages. The natural embed is a small
OpenClaw plugin registering `gateway.anvil.status` that shells
`anvil status --json`, plus a control-ui page rendering it — giving the same
board inside `openclaw-control-ui`. This is deferred until the Gateway is
stood up on the target machine; the standalone dashboard covers the need until
then.
