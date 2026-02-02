---
name: edit-image
description: Edit an existing image with natural language instructions
arguments:
  - name: input-file
    description: Path to the input image to edit
    required: true
  - name: edit-instructions
    description: Natural language description of the edits to make
    required: true
  - name: --aspect
    description: "Aspect ratio for output (1:1, 16:9, 4:3, 9:16, 3:2)"
    required: false
  - name: --size
    description: "Image size tier (1K, 2K, 4K)"
    required: false
  - name: --out
    description: Output file path (defaults to .nanobanana/out/)
    required: false
---

# Edit Image Command

Edit an existing image using natural language instructions with Google's Gemini 3 Pro Image Preview model.

## Prerequisites

- GEMINI_API_KEY configured (see [Configuration](../README.md#configuration))
- Python 3.10+ installed
- `uv` package manager installed
- Input image file (PNG recommended)

## Execution

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" edit \
  --in "<input-file>" \
  --prompt "<edit-instructions>" \
  [--aspect "1:1"] \
  [--size "2K"] \
  [--out "./edited.png"]
```

## Examples

### Adjust typography

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" edit \
  --in "./hero-banner.png" \
  --prompt "Increase the headline size by 15%. Add more whitespace above the subhead. Keep everything else the same."
```

### Change colors

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" edit \
  --in "./logo.png" \
  --prompt "Replace the blue with a gradient from #6366F1 to #8B5CF6. Keep the shape and layout identical."
```

### Add elements

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" edit \
  --in "./product-shot.png" \
  --prompt "Add a subtle drop shadow beneath the product. Add a small 'NEW' badge in the top-right corner."
```

### Remove elements

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" edit \
  --in "./photo.png" \
  --prompt "Remove the text watermark in the bottom-right corner. Fill the area naturally with the surrounding background."
```

## Output

The command prints the output file path on success. Default location: `./.nanobanana/out/nanobanana-<timestamp>.png`

## Common Edit Patterns

| Goal | Prompt Pattern |
|------|----------------|
| Resize element | "Increase/decrease [element] by [percentage]" |
| Reposition | "Move [element] to [location]" |
| Recolor | "Change [element] color from [old] to [new]" |
| Add | "Add [element] in/at [location]" |
| Remove | "Remove [element]. Fill naturally with surrounding [context]" |
| Transform | "Convert [element] to [style]. Keep [preserved aspects]" |
