---
description: List and read Google Keep notes
argument-hint: "<list|read> [note-id]"
allowed-tools: [Bash]
---

# /gws-keep

Manage Google Keep notes using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine the operation.

### Common Operations

**List notes:**
```bash
gws keep notes list --format table
```

**Read a specific note:**
```bash
gws keep notes get --params '{"name": "notes/NOTE_ID"}'
```

## Tips

- Note IDs are prefixed with `notes/`.
- The Keep API may require a Google Workspace enterprise account.

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
- 403 error: Keep API may not be available for consumer Gmail accounts.
