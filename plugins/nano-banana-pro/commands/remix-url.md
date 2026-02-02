---
name: remix-url
description: Generate an image styled from a webpage's design (colors, fonts, imagery)
arguments:
  - name: url
    description: URL of the webpage to use as style reference
    required: true
  - name: prompt
    description: Description of what image to create using the page's style
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
  - name: --max-images
    description: Maximum reference images to download (default 2)
    required: false
---

# Remix URL Command

Generate an image that matches the visual style of a webpage, using extracted colors, typography, and reference images.

## Prerequisites

- GEMINI_API_KEY configured (see settings section)
- Python 3.10+ installed
- `uv` package manager installed
- Target URL must be publicly accessible

## How It Works

The remix command:

1. **Fetches the webpage** HTML content
2. **Extracts style hints**:
   - Title and description
   - Theme color (meta theme-color)
   - Color palette (CSS hex codes)
   - Typography (Google Fonts links, font-family declarations)
3. **Downloads reference images**:
   - Open Graph images (og:image)
   - Twitter card images
   - Favicons
4. **Generates** a new image inspired by the page's style

## API Key Configuration

Set up the API key in one of these locations (checked in order):

1. **Settings file** (recommended): `.claude/nano-banana-pro.local.md`
   ```markdown
   ---
   gemini_api_key: "your-api-key-here"
   ---
   ```

2. **Environment variable**: `GEMINI_API_KEY`

3. **Workspace .env file**: `GEMINI_API_KEY="your-key"`

4. **Home .env file**: `~/.env`

## Execution

Run the nanobanana.py script with the remix-url command:

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" remix-url \
  --url "<webpage-url>" \
  --prompt "<what-to-create>" \
  [--aspect "16:9"] \
  [--size "2K"] \
  [--max-images 2] \
  [--out "./remixed.png"]
```

## Examples

### Create a hero banner matching a site's style

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" remix-url \
  --url "https://stripe.com" \
  --prompt "Hero banner for a payment processing feature. Headline: 'Accept Payments Anywhere'. Clean, gradient background, modern typography." \
  --aspect "16:9" \
  --size "2K"
```

### Generate social card in brand style

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" remix-url \
  --url "https://notion.so" \
  --prompt "Social media card announcing a new feature. Text: 'Now with AI'. Centered layout, minimal design." \
  --aspect "1:1" \
  --size "2K"
```

### Create presentation slide

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" remix-url \
  --url "https://linear.app" \
  --prompt "Presentation title slide. Headline: 'Q4 Product Roadmap'. Professional, dark theme, subtle gradients." \
  --aspect "16:9" \
  --size "2K"
```

### Design app store screenshot

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" remix-url \
  --url "https://figma.com" \
  --prompt "App store screenshot showing a design canvas with colorful shapes and collaboration cursors." \
  --aspect "9:16" \
  --size "2K"
```

## Output

The command prints the output file path on success. Default location: `./.nanobanana/out/nanobanana-<timestamp>.png`

## What Gets Extracted

| Element | Source |
|---------|--------|
| Title | `<title>` tag |
| Description | `<meta name="description">` or `og:description` |
| Theme color | `<meta name="theme-color">` |
| Color palette | CSS hex codes in stylesheets |
| Fonts | Google Fonts links, font-family declarations |
| Reference images | og:image, twitter:image, favicons |

## Best Practices

1. **Describe the output, not the source**: Focus on what you want to create
2. **Include specific text**: Always specify exact headlines and copy
3. **Specify format**: Hero banner, social card, icon, etc.
4. **Add layout direction**: "Centered", "left-aligned", "rule of thirds"
5. **Respect copyright**: Create original content inspired by style, not copies

## Important Notes

- **Do NOT copy copyrighted imagery** - The model generates original content inspired by the page's style
- **Public pages only** - Pages requiring authentication won't work
- **Style guidance** - Use the page's palette and typography as inspiration

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401/403 error | Check API key configuration |
| No style extracted | Page may have minimal meta tags; be more specific in prompt |
| Wrong colors | Override with specific hex codes in your prompt |
| Reference images failed | Try `--max-images 1` or specify colors manually |
