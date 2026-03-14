---
description: 'Gmail: Send an email. Trigger with: send an email, compose email, draft and send Gmail message.'
name: gws-gmail-send
version: 1.0.0
---

# gmail +send

> **Reference:** See the `gws-shared` skill for auth, global flags, and security rules.

Send an email

## Usage

```bash
gws gmail +send --to <EMAILS> --subject <SUBJECT> --body <TEXT>
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--to` | ✓ | — | Recipient email address(es), comma-separated |
| `--subject` | ✓ | — | Email subject |
| `--body` | ✓ | — | Email body (plain text, or HTML with --html) |
| `--cc` | — | — | CC email address(es), comma-separated |
| `--bcc` | — | — | BCC email address(es), comma-separated |
| `--html` | — | — | Treat --body as HTML content (default is plain text) |
| `--dry-run` | — | — | Show the request that would be sent without executing it |

## Examples

```bash
gws gmail +send --to alice@example.com --subject 'Hello' --body 'Hi Alice!'
gws gmail +send --to alice@example.com --subject 'Hello' --body 'Hi!' --cc bob@example.com
gws gmail +send --to alice@example.com --subject 'Hello' --body 'Hi!' --bcc secret@example.com
gws gmail +send --to alice@example.com --subject 'Hello' --body '<b>Bold</b> text' --html
```

## Tips

- Handles RFC 2822 formatting and base64 encoding automatically.
- For attachments, use the raw API instead: gws gmail users messages send --json '...'

> [!CAUTION]
> This is a **write** command — confirm with the user before executing.

## See Also

- [gws-shared](../gws-shared/SKILL.md) — Global flags and auth
- [gws-gmail](../gws-gmail/SKILL.md) — All send, read, and manage email commands
