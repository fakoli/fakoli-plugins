---
name: generate
description: Generate, edit, or remix images using Google Gemini 3 Pro Image Preview (Nano Banana Pro)
allowed-tools:
  - Bash
  - Read
  - Write
---

# Nano Banana Pro (Gemini 3 Pro Image) Skill

Generate, edit, and remix images using Google's Gemini 3 Pro Image Preview model.

## Quick Reference

| Command | Description |
|---------|-------------|
| `gen` | Generate an image from a text prompt |
| `edit` | Edit an existing image with instructions |
| `remix-url` | Create an image styled from a webpage |

## Usage

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" <command> [options]
```

## Documentation

- [README](../../README.md) - Full documentation, configuration, and troubleshooting
- [Style Templates](references/style-templates.md) - Pre-built prompt patterns for common use cases
