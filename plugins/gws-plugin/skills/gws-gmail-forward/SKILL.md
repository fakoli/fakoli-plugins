---
name: gws-gmail-forward
description: "Gmail: Forward a message to new recipients."
trigger:
  - keyword: forward email
  - keyword: gmail forward
  - keyword: fwd email
---

# gmail +forward

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Forward a message to new recipients

## Usage

```bash
gws gmail +forward --message-id <ID> --to <EMAILS>
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--message-id` | ✓ | — | Gmail message ID to forward |
| `--to` | ✓ | — | Recipient email address(es), comma-separated |
| `--from` | — | — | Sender address (for send-as/alias; omit to use account default) |
| `--cc` | — | — | CC email address(es), comma-separated |
| `--bcc` | — | — | BCC email address(es), comma-separated |
| `--body` | — | — | Optional note to include above the forwarded message (plain text, or HTML with --html) |
| `--html` | — | — | Send as HTML (formats forwarded block with Gmail styling; treat --body as HTML) |
| `--dry-run` | — | — | Show the request that would be sent without executing it |

## Examples

```bash
gws gmail +forward --message-id 18f1a2b3c4d --to dave@example.com
gws gmail +forward --message-id 18f1a2b3c4d --to dave@example.com --body 'FYI see below'
gws gmail +forward --message-id 18f1a2b3c4d --to dave@example.com --cc eve@example.com
gws gmail +forward --message-id 18f1a2b3c4d --to dave@example.com --bcc secret@example.com
gws gmail +forward --message-id 18f1a2b3c4d --to dave@example.com --body '<p>FYI</p>' --html
```

## Tips

- Includes the original message with sender, date, subject, and recipients.

## See Also

- **gws-shared** — Global flags and auth
- [gws-gmail](../gws-gmail/SKILL.md) — All send, read, and manage email commands
