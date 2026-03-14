---
name: gws-workflow-email-to-task
description: "Google Workflow: Convert a Gmail message into a Google Tasks entry."
trigger:
  - keyword: email to task
  - keyword: convert email
  - keyword: email action items
version: 1.0.0
---

# workflow +email-to-task

> **Reference:** See the `gws-shared` skill for auth, global flags, and security rules.

Convert a Gmail message into a Google Tasks entry

## Usage

```bash
gws workflow +email-to-task --message-id <ID>
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--message-id` | ✓ | — | Gmail message ID to convert |
| `--tasklist` | — | @default | Task list ID (default: @default) |

## Examples

```bash
gws workflow +email-to-task --message-id MSG_ID
gws workflow +email-to-task --message-id MSG_ID --tasklist LIST_ID
```

## Tips

- Reads the email subject as the task title and snippet as notes.
- Creates a new task — confirm with the user before executing.

## See Also

- **gws-shared** — Global flags and auth
- [gws-workflow](../gws-workflow/SKILL.md) — All cross-service productivity workflows commands
