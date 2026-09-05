---
description: Toggle automatic text-to-speech for all responses
allowed-tools: Bash
---

The user wants to toggle autospeak mode. Check if they said "on", "off", or neither (status check).

To enable:
```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak autospeak on
```

To disable:
```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak autospeak off
```

To check status:
```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak autospeak
```

Show the output. When enabling, mention that responses over 100 characters will be automatically read aloud and they can use `/autospeak off` or `/stop` to control it.
