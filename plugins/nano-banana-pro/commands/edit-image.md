---
description: Edit a PNG, JPEG, or WebP image with Gemini and natural language instructions
argument-hint: 'image-path "edit instructions" [--model pro|flash|MODEL_ID] [--out path.png]'
---

Edit the image requested in `$ARGUMENTS`. Inspect the input, preserve the user's requested details, and follow [the generate skill](../skills/generate/SKILL.md).

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" edit \
  --in "<image-path>" --prompt "<edit instructions>" --out "./edited.png"
```

Run from the user's project directory. Quote each argument safely, map requested flags, and choose a new output path unless the user requests replacement. The script detects the actual input MIME type. Inspect and display the output; do not automatically launch paid revision loops. See [README](../README.md#usage) for options and limits.
