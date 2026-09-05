---
description: List available voices for the active TTS provider
allowed-tools: Bash
---

Run this command to list available voices:

```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak voices
```

Show the output to the user. Tell them they can switch providers by setting `FAKOLI_SPEAK_PROVIDER` in `~/.env`, and switch voices by setting the provider-specific voice env var (e.g. `ELEVENLABS_VOICE_ID`, `OPENAI_TTS_VOICE`) in `~/.env`.
