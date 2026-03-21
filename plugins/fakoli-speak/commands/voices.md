---
description: List available ElevenLabs voices
allowed_tools: Bash
---

Run this command to list available ElevenLabs voices:

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak voices
```

Show the output to the user. Tell them they can switch voices by setting `ELEVENLABS_VOICE_ID` in `~/.env`.
