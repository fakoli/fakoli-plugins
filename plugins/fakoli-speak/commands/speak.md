---
description: Read the last response aloud using ElevenLabs TTS
---

Look at your most recent assistant response in this conversation — the one immediately before the user typed /speak.

Extract ONLY the visible text output. Do NOT include:
- Tool call results or raw JSON
- System reminders or session metadata
- Markdown formatting characters (#, *, `, |, ---)
- Code blocks or code snippets
- Table formatting

Convert the content to natural spoken English. For tables, summarize the key data points conversationally. For bullet points, read them as sentences.

Then pipe that cleaned text to the TTS script using Bash:

```
echo "cleaned text here" | ${CLAUDE_PLUGIN_ROOT}/scripts/tts.sh
```

Do NOT output anything else to the user. Just run the Bash command silently.
