---
description: Optimize a local image to a file size and width limit without an API call
argument-hint: 'image-path [--preset github|slack|web|thumbnail] [--max-size 500KB] [--width 1280] [--out path.png]'
---

Optimize the file in `$ARGUMENTS` using the requested constraints. This command runs locally and needs no Gemini key.

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/optimize.py" \
  "<image-path>" --preset github
```

Run from the user's directory; safely quote each argument. Pass custom size/width/output flags when requested. Default output is `<stem>-optimized.png`. Preserve the original unless replacement is requested, then use `--overwrite` deliberately. Report the saved path, measured byte size, and any tradeoff visible in the output. The CLI exits nonzero if the limit cannot be met and leaves existing files intact. See [optimization](../README.md#optimization) for presets and format behavior.
