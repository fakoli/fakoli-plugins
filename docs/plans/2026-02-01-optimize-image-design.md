# Optimize Image Feature Design

**Date:** 2026-02-01
**Plugin:** nano-banana-pro
**Version:** 1.2.0

## Overview

Add image optimization feature to nano-banana-pro plugin using `sips` (macOS) or Pillow (other platforms) to reduce image sizes for GitHub, Slack, web, and other constrained environments.

## Command Interface

```
/optimize-image <image-path> [--preset github|slack|web|thumbnail] [--max-size 500KB] [--width 800] [--out ./optimized.png]
```

**Arguments:**
- `image-path` (required) - Path to image to optimize
- `--preset` - Named preset (github, slack, web, thumbnail)
- `--max-size` - Custom max file size (e.g., `500KB`, `1MB`)
- `--width` - Custom max width in pixels
- `--out` - Output path (defaults to `<original>-optimized.png`)

## Presets

| Preset | Max Size | Max Width | Use Case |
|--------|----------|-----------|----------|
| `github` | 500KB | 1280px | README images, PR screenshots |
| `slack` | 128KB | 800px | Slack/Discord messages |
| `web` | 200KB | 1200px | Blog posts, documentation |
| `thumbnail` | 50KB | 400px | Previews, icons |

## Architecture

### Cross-Platform Support

- **macOS:** Use `sips` (built-in, zero dependencies)
- **Other platforms:** Use Pillow (conditional dependency)

### Dependencies

```toml
dependencies = [
    "python-dotenv>=1.0.0",
    "pillow>=10.0.0; sys_platform != 'darwin'"
]
```

## Auto-Suggestion

After image generation, if file size exceeds threshold (default 500KB):

```
Generated image: ./banner.png (2.3MB)

⚠️ This image is large for GitHub/web use. To optimize:
/optimize-image ./banner.png --preset github
```

### Settings

```yaml
---
optimize_threshold_kb: 500  # suggest optimization above this size
auto_optimize: false        # true to auto-optimize without asking
---
```

## Files

**New:**
- `commands/optimize-image.md` - Command definition
- `skills/generate/scripts/optimize.py` - Optimization script (~150 lines)

**Modified:**
- `pyproject.toml` - Add conditional Pillow dependency
- `SKILL.md` - Add auto-suggest guidance
- `README.md` - Document new command
- `CHANGELOG.md` - Document v1.2.0
- `plugin.json` - Bump version to 1.2.0
