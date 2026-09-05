---
description: Inspect the active TTS provider and a requested provider configuration
allowed-tools: Bash
---

Run to show current provider and available options:

```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak provider
```

To check a specific provider:

```bash
uv run --frozen --directory "${CLAUDE_PLUGIN_ROOT}" fakoli-speak provider <name>
```

Available providers: openai, elevenlabs, deepgram, google, macos.
Show the output. To persist, tell user to add FAKOLI_SPEAK_PROVIDER=<name> to ~/.env.
