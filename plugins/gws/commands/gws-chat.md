---
description: Send messages and manage Google Chat spaces
argument-hint: "<send|list-spaces> [space-name] [message]"
allowed-tools: [Bash]
---

# /gws-chat

Manage Google Chat using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine the operation.

### Common Operations

**List spaces:**
```bash
gws chat spaces list --format table
```

**Send a message:**
```bash
gws chat +send --space SPACE_ID --text "Message content"
```

**List messages in a space:**
```bash
gws chat spaces messages list --params '{"parent": "spaces/SPACE_ID"}' --format table
```

## Tips

- Space IDs look like `spaces/XXXXXXXXX`. Use `spaces list` to find them.
- Confirm with the user before sending messages.

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
- Chat API may require app-level auth for non-DM spaces.
