---
description: Stop TTS playback
allowed-tools: Bash
---

Run this command to stop any currently playing TTS audio:

```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak stop
```

Report the command result; do not claim successful stopping if it failed. The command targets this plugin's verified worker only.
