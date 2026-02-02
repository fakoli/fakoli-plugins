---
name: generate
description: Generate, edit, or remix images using Google Gemini 3 Pro Image Preview (Nano Banana Pro)
allowed-tools:
  - Bash
  - Read
  - Write
---

# Nano Banana Pro (Gemini 3 Pro Image) Skill

This skill wraps a local Python CLI to generate or edit images using Google's Gemini API model `gemini-3-pro-image-preview`.

## Features

- **Generate** images from text prompts
- **Edit** existing images with instructions
- **Remix** webpages into design-aligned assets (extracts colors, fonts, imagery)
- **Style templates** for common use cases (UI, marketing, artistic)

## API Key Configuration

The CLI loads the key in this order:

1. Settings file: `.claude/nano-banana-pro.local.md` (recommended)
2. Environment variable: `GEMINI_API_KEY`
3. Workspace `.env` file
4. Home `~/.env` file

### Settings file format

Create `.claude/nano-banana-pro.local.md`:

```markdown
---
gemini_api_key: "your-api-key-here"
default_aspect: "16:9"
default_size: "2K"
output_dir: "./.nanobanana/out"
---
```

### .env format

```
GEMINI_API_KEY="your_key_here"
```

## Requirements

- Python 3.10+ (3.11+ recommended)
- `uv` package manager installed

## Commands

### Generate an image

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" gen \
  --prompt "<prompt>" \
  [--out "<path.png>"] \
  [--aspect "16:9"] \
  [--size "1K|2K|4K"] \
  [--search]
```

### Edit an existing image

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" edit \
  --prompt "<edit instructions>" \
  --in "<input.png>" \
  [--out "<path.png>"] \
  [--aspect "1:1"] \
  [--size "1K|2K|4K"] \
  [--search]
```

### Remix a webpage into a design asset

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" remix-url \
  --url "<https://...>" \
  --prompt "<what to make>" \
  [--out "<path.png>"] \
  [--aspect "16:9"] \
  [--size "1K|2K|4K"] \
  [--max-images 2] \
  [--max-bytes 4000000] \
  [--search]
```

Remix mode extracts:
- Title and description
- Theme colors (meta theme-color + CSS variables)
- Typography hints (Google Fonts + font-family)
- Reference images (og:image, twitter:image, favicon)

## Aspect Ratios

| Ratio | Use Case |
|-------|----------|
| `1:1` | Social media avatars, icons, thumbnails |
| `16:9` | Hero banners, YouTube thumbnails, presentations |
| `4:3` | Product shots, traditional photos |
| `9:16` | Mobile stories, vertical banners |
| `3:2` | Photography, print media |

## Size Options

| Size | Resolution | Use Case |
|------|------------|----------|
| `1K` | ~1024px | Quick previews, drafts |
| `2K` | ~2048px | Web-ready, social media |
| `4K` | ~4096px | Print, high-resolution displays |

## Best Practices

### 1. Prompt like a designer

Include: dimensions, layout rules, margins, type hierarchy, and exact text.

Example prompt skeleton:
- Format: "hero banner"
- Aspect: 16:9
- Safe margins: 6% on all sides
- Type: bold sans-serif headline + smaller subhead
- Exact text (verbatim block)
- Visual: clean, high contrast, minimal clutter

### 2. Lock down text when it matters

Say: "Render this text verbatim, including capitalization and punctuation."
Put the copy in a literal block.

### 3. Iterate surgically with edit mode

If the first version is close, use `edit` with specific deltas:
- "Increase headline size by ~15%"
- "Add more whitespace above the subhead"
- "Replace background with a subtle gradient using #112233 -> #445566"
- "Keep everything else the same"

### 4. Use style templates

Refer to `references/style-templates.md` for pre-built prompt patterns for:
- UI/Web: Hero banners, social cards, app screenshots, icons
- Marketing: Product shots, ad creatives, brand assets
- Artistic: Illustrations, abstract, photo-realistic, minimalist, retro

### 5. Keep outputs organized

- Default output: `./.nanobanana/out/`
- Use `--out` for specific locations
- Avoid storing generated images in the plugin directory

## Troubleshooting

| Error | Solution |
|-------|----------|
| 401/403 | API key missing or invalid |
| No image returned | Prompt may have been blocked or response missing image data |
| Slow calls | Reduce `--size` from 4K to 2K or 1K |
| Permission denied | Check that `uv` and `python3` are in PATH |

## Output Location

Images are saved to `./.nanobanana/out/` by default with timestamp-based filenames. The CLI prints the output path on success.
