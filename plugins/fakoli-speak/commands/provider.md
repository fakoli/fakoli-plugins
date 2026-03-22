---
description: Show or switch the active TTS provider
allowed-tools: Bash
---

Run to show current provider and available options:

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak provider
```

To check a specific provider:

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak provider <name>
```

Available providers: openai, elevenlabs, deepgram, google, macos.
Show the output. To persist, tell user to add FAKOLI_SPEAK_PROVIDER=<name> to ~/.env.
