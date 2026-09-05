---
description: Generate an image using Nano Banana Pro and the configured Gemini model
argument-hint: '"prompt" [--model pro|flash|MODEL_ID] [--aspect 16:9] [--size 2K] [--out path.png]'
---

Generate the image requested in `$ARGUMENTS`. Use [the generate skill](../skills/generate/SKILL.md) and [README](../README.md) for configuration and supported options.

Run directly from the user's project directory; preserve the user's prompt and model choice. Resolve arguments with proper shell quoting rather than evaluating their text as shell syntax.

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" gen \
  --prompt "<prompt>" --out "./image.png"
```

Map requested flags to the CLI. Use defaults for unspecified options. Inspect and display the resulting image. Stop after one generation unless revisions were requested or an iteration budget was agreed; do not launch a mandatory agent pipeline.
