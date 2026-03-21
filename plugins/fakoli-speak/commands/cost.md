---
description: Show ElevenLabs TTS usage and cost tracking
allowed_tools: Bash
---

Run this command to show TTS usage and costs:

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak cost
```

Show the output to the user. If they ask to reset, run with `--reset`. If they want to set their plan rate, run with `--rate <dollars_per_1k_chars>`.
