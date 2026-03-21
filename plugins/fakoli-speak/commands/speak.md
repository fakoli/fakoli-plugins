---
description: Read the last response aloud using ElevenLabs TTS
allowed_tools: Bash
---

Look at your most recent assistant response in this conversation — the one immediately before the user typed /speak.

Extract ONLY the visible text you wrote to the user. Exclude:
- Tool call inputs/outputs, raw JSON, system reminders, session metadata
- Markdown syntax: #, *, `, |, ---, ```, >, [ ]( )
- Code blocks and their contents
- Table grid characters (keep the data as prose)

Rewrite the extracted content as natural spoken English:
- Tables become conversational summaries ("The S&P 500 closed at 648, down 1.7 percent...")
- Bullet points become flowing sentences
- Numbers stay as-is but spell out symbols (% becomes "percent", $ stays)
- Section headers become topic transitions ("Regarding the macro dashboard...")
- Skip anything that wouldn't make sense spoken aloud

Then send the text to TTS using a heredoc (safe for quotes, dollars, backticks):

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak speak <<'SPEAK_EOF'
your cleaned spoken text here
SPEAK_EOF
```

After running the command, respond with only: "Speaking." — nothing else.
