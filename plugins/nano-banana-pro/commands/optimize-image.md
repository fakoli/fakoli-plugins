---
name: optimize-image
description: Optimize image size for GitHub, Slack, web, or custom constraints
arguments:
  - name: image-path
    description: Path to the image to optimize
    required: true
  - name: --preset
    description: "Named preset: github (500KB), slack (128KB), web (200KB), thumbnail (50KB)"
    required: false
  - name: --max-size
    description: "Custom max file size (e.g., 500KB, 1MB)"
    required: false
  - name: --width
    description: Maximum width in pixels
    required: false
  - name: --out
    description: Output path (defaults to <original>-optimized.png)
    required: false
---

# Optimize Image Command

Reduce image file size for GitHub, Slack, web, or other constrained environments.

## Prerequisites

- Python 3.10+ installed
- `uv` package manager installed
- macOS uses built-in `sips` (no extra dependencies)
- Other platforms use Pillow (installed automatically)

## Presets

| Preset | Max Size | Max Width | Use Case |
|--------|----------|-----------|----------|
| `github` | 500KB | 1280px | README images, PR screenshots |
| `slack` | 128KB | 800px | Slack/Discord messages |
| `web` | 200KB | 1200px | Blog posts, documentation |
| `thumbnail` | 50KB | 400px | Previews, icons |

## Execution

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/optimize.py" \
  <image-path> \
  [--preset github|slack|web|thumbnail] \
  [--max-size 500KB] \
  [--width 800] \
  [--out "./optimized.png"]
```

## Examples

### Optimize for GitHub README

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/optimize.py" \
  ./banner.png --preset github
```

### Optimize for Slack

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/optimize.py" \
  ./screenshot.png --preset slack
```

### Custom size constraint

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/optimize.py" \
  ./image.png --max-size 300KB --width 1000
```

### Specify output path

```bash
uv run python "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/optimize.py" \
  ./large-image.png --preset web --out ./web-ready.png
```

## Output

The command prints the optimized file path and size reduction:

```
Optimized: ./banner-optimized.png
Size: 2340KB → 420KB (82% reduction)
```

## How It Works

1. Applies max width constraint first (preserves aspect ratio)
2. If still over max size, iteratively reduces dimensions by 20%
3. Uses `sips` on macOS (built-in) or Pillow on other platforms
