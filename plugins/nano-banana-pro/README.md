# Nano Banana Pro

Generate, edit, and remix images using Google's Gemini 3 Pro Image Preview model.

## Features

- **Generate** images from text prompts with precise control over composition
- **Edit** existing images with natural language instructions
- **Remix** webpages into brand-aligned visual assets
- **Optimize** images for GitHub, Slack, web with smart presets
- **Style templates** for common use cases (UI, marketing, artistic)

## Installation

### Requirements

- Python 3.10 or later
- [uv](https://github.com/astral-sh/uv) package manager
- Google AI API key with Gemini 3 Pro access

### Setup

1. Install the plugin in Claude Code
2. Configure your API key (see Configuration section)

## Configuration

Create a settings file at `.claude/nano-banana-pro.local.md`:

```markdown
---
gemini_api_key: "your-api-key-here"
default_aspect: "16:9"
default_size: "2K"
output_dir: "./.nanobanana/out"
---

# Nano Banana Pro Settings

Your local configuration for image generation.
```

### Alternative: Environment Variables

Set `GEMINI_API_KEY` in your environment or in a `.env` file:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

Or create a `.env` file:

```
GEMINI_API_KEY="your-api-key-here"
```

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `/generate-image` | Generate an image from a text prompt |
| `/edit-image` | Edit an existing image with instructions |
| `/remix-url` | Create an image styled from a webpage |
| `/optimize-image` | Reduce image size for GitHub, Slack, web |

### Generate Image

```
/generate-image "A hero banner with bold headline 'Ship Faster' on blue gradient background" --aspect 16:9 --size 2K
```

### Edit Image

```
/edit-image ./banner.png "Increase headline size by 15%, add subtle drop shadow"
```

### Remix URL

```
/remix-url https://stripe.com "Create a hero banner for payments feature with headline 'Accept Anywhere'" --aspect 16:9
```

### Optimize Image

```
/optimize-image ./banner.png --preset github
```

#### Optimization Presets

| Preset | Max Size | Max Width | Use Case |
|--------|----------|-----------|----------|
| `github` | 500KB | 1280px | README images, PR screenshots |
| `slack` | 128KB | 800px | Slack/Discord messages |
| `web` | 200KB | 1200px | Blog posts, documentation |
| `thumbnail` | 50KB | 400px | Previews, icons |

Custom options: `--max-size 300KB --width 1000`

## Style Templates

The plugin includes pre-built prompt templates for common use cases:

### UI/Web Styles
- Hero banners (16:9, 1920x1080)
- Social media cards (1:1, 1200x1200)
- App screenshots (9:16, 1080x1920)
- Landing page sections (4:3)
- Icons (1:1, 512x512)

### Marketing Styles
- Product photography
- Ad creatives
- Logo variations
- Brand assets

### Artistic Styles
- Flat design illustrations
- Abstract art
- Photo-realistic
- Minimalist
- Retro/vintage

See `skills/generate/references/style-templates.md` for detailed templates.

## Aspect Ratios

| Ratio | Best For |
|-------|----------|
| `1:1` | Social avatars, icons, thumbnails |
| `16:9` | Hero banners, presentations, YouTube |
| `4:3` | Product shots, traditional photos |
| `9:16` | Mobile stories, vertical banners |
| `3:2` | Photography, print media |

## Size Options

| Size | Resolution | Use Case |
|------|------------|----------|
| `1K` | ~1024px | Quick previews, drafts |
| `2K` | ~2048px | Web-ready, social media |
| `4K` | ~4096px | Print, high-resolution |

## Best Practices

1. **Prompt like a designer** - Include layout, margins, typography, and exact text
2. **Lock down text** - Say "Render this text verbatim" for exact copy
3. **Iterate surgically** - Use edit mode for specific refinements
4. **Use templates** - Reference style templates for consistent results

## Output

Generated images are saved to `./.nanobanana/out/` by default with timestamp-based filenames. Use `--out` to specify a custom path.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401/403 error | Check API key configuration |
| No image returned | Prompt may have been blocked; try rephrasing |
| Slow generation | Reduce size from 4K to 2K |
| Permission denied | Ensure `uv` and `python3` are in PATH |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Sekou Doumbouya ([@fakoli](https://github.com/fakoli))
