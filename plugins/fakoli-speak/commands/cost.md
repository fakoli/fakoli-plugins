---
description: Show TTS usage and cost tracking
allowed-tools: Bash
---

Run this command to show TTS usage and costs:

```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak cost
```

Show the output as a local estimate, not a provider invoice. If they ask to reset, run with `--reset`. If they want to set their plan rate, run with `--rate <dollars_per_1k_chars>`.
