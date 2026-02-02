---
name: generate
description: Generate, edit, remix, and optimize images using Google Gemini 3 Pro Image Preview (Nano Banana Pro)
allowed-tools:
  - Bash
  - Read
  - Write
---

# Nano Banana Pro (Gemini 3 Pro Image) Skill

Generate, edit, remix, and optimize images using Google's Gemini 3 Pro Image Preview model.

## Quick Reference

| Command | Description |
|---------|-------------|
| `gen` | Generate an image from a text prompt |
| `edit` | Edit an existing image with instructions |
| `remix-url` | Create an image styled from a webpage |
| `optimize` | Reduce image size for GitHub, Slack, web |

## Usage

```bash
# Generate/edit/remix
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" <command> [options]

# Optimize
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/optimize.py" <image> [--preset github|slack|web|thumbnail]
```

## Auto-Optimization Guidance

**After generating any image, check the file size.** If over 500KB (or user's configured threshold), suggest optimization:

```
Generated image: ./banner.png (2.3MB)

⚠️ This image is large for GitHub/web use. To optimize:
/optimize-image ./banner.png --preset github
```

### Optimization Presets

| Preset | Max Size | Max Width | Use Case |
|--------|----------|-----------|----------|
| `github` | 500KB | 1280px | README images, PR screenshots |
| `slack` | 128KB | 800px | Slack/Discord messages |
| `web` | 200KB | 1200px | Blog posts, documentation |
| `thumbnail` | 50KB | 400px | Previews, icons |

## Documentation

- [README](../../README.md) - Full documentation, configuration, and troubleshooting
- [Style Templates](references/style-templates.md) - Pre-built prompt patterns for common use cases
