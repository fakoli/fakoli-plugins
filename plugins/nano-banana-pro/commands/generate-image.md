---
name: generate-image
description: Generate an image from a text prompt using Gemini 3 Pro
arguments:
  - name: prompt
    description: Text description of the image to generate
    required: true
  - name: --aspect
    description: "Aspect ratio (1:1, 16:9, 4:3, 9:16, 3:2)"
    required: false
  - name: --size
    description: "Image size tier (1K, 2K, 4K)"
    required: false
  - name: --out
    description: Output file path (defaults to .nanobanana/out/)
    required: false
---

# Generate Image Command

Generate an image from a text prompt using Google's Gemini 3 Pro Image Preview model.

## Prerequisites

- GEMINI_API_KEY configured (see settings section)
- Python 3.10+ installed
- `uv` package manager installed

## API Key Configuration

Set up the API key in one of these locations (checked in order):

1. **Settings file** (recommended): `.claude/nano-banana-pro.local.md`
   ```markdown
   ---
   gemini_api_key: "your-api-key-here"
   default_aspect: "16:9"
   default_size: "2K"
   ---
   ```

2. **Environment variable**: `GEMINI_API_KEY`

3. **Workspace .env file**: `GEMINI_API_KEY="your-key"`

4. **Home .env file**: `~/.env`

## Execution

Run the nanobanana.py script with the gen command:

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" gen \
  --prompt "<prompt>" \
  [--aspect "16:9"] \
  [--size "2K"] \
  [--out "./output.png"]
```

## Examples

### Basic generation

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" gen \
  --prompt "A serene mountain landscape at sunset with golden light"
```

### Hero banner with specific dimensions

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" gen \
  --prompt "Hero banner for a SaaS product. Bold headline 'Ship Faster' on left, abstract tech illustration on right. Clean, modern, blue gradient background." \
  --aspect "16:9" \
  --size "2K" \
  --out "./hero-banner.png"
```

### Social media avatar

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" gen \
  --prompt "Professional avatar icon, geometric abstract face, purple and teal gradient" \
  --aspect "1:1" \
  --size "1K"
```

## Output

The command prints the output file path on success. Default location: `./.nanobanana/out/nanobanana-<timestamp>.png`

## Best Practices

1. **Be specific**: Include layout, colors, typography, and exact text
2. **Use style templates**: Reference `references/style-templates.md` for patterns
3. **Lock down text**: Say "Render this text verbatim" for exact copy
4. **Start smaller**: Use 1K or 2K for drafts, 4K for final versions

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401/403 error | Check API key configuration |
| No image returned | Prompt may have been blocked; try rephrasing |
| Slow generation | Reduce size from 4K to 2K |
