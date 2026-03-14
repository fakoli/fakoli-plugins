---
name: gws-chat-send
description: "Google Chat: Send a message to a space."
trigger:
  - keyword: send chat
  - keyword: chat message
  - keyword: post in chat
---

# chat +send

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Send a message to a space

## Usage

```bash
gws chat +send --space <NAME> --text <TEXT>
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--space` | ✓ | — | Space name (e.g. spaces/AAAA...) |
| `--text` | ✓ | — | Message text (plain text) |

## Examples

```bash
gws chat +send --space spaces/AAAAxxxx --text 'Hello team!'
```

## Tips

- Use 'gws chat spaces list' to find space names.
- For cards or threaded replies, use the raw API instead.

> [!CAUTION]
> This is a **write** command — confirm with the user before executing.

## See Also

- **gws-shared** — Global flags and auth
- [gws-chat](../gws-chat/SKILL.md) — All manage chat spaces and messages commands
