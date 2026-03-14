---
name: gws-gmail-triage
description: "Gmail: Show unread inbox summary (sender, subject, date)."
trigger:
  - keyword: triage inbox
  - keyword: gmail triage
  - keyword: unread emails
  - keyword: inbox summary
---

# gmail +triage

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Show unread inbox summary (sender, subject, date)

## Usage

```bash
gws gmail +triage
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--max` | — | 20 | Maximum messages to show (default: 20) |
| `--query` | — | — | Gmail search query (default: is:unread) |
| `--labels` | — | — | Include label names in output |

## Examples

```bash
gws gmail +triage
gws gmail +triage --max 5 --query 'from:boss'
gws gmail +triage --format json | jq '.[].subject'
gws gmail +triage --labels
```

## Tips

- Read-only — never modifies your mailbox.
- Defaults to table output format.

## See Also

- **gws-shared** — Global flags and auth
- [gws-gmail](../gws-gmail/SKILL.md) — All send, read, and manage email commands
