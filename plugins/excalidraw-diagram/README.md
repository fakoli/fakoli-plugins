# Excalidraw Diagram Plugin for Claude Code

Generate and modify Excalidraw diagrams from natural language descriptions and code analysis, directly from your Claude Code terminal session.

## Features

- **Natural language to diagram**: Describe what you want, get a `.excalidraw` file
- **Code-aware**: Analyzes your codebase to generate architecture diagrams
- **Modification support**: Add/remove elements from existing diagrams, including arrows to pre-existing elements
- **Smart arrow binding**: Edge-aware arrow connections that exit/enter shapes at the correct edge based on relative position
- **Accurate text sizing**: Character-class-based width estimation for reliable label placement
- **Multiple layouts**: Grid, top-down tree, left-right flow — all respect variable element sizes
- **Color themes**: Default, blueprint, warm, monochrome
- **Input validation**: Skeleton JSON is validated before conversion with clear error reporting
- **Browser preview**: Load diagrams directly in excalidraw.com via claude-in-chrome
- **Zero dependencies**: Only requires Node.js >= 18

## Quick Start

```
/excalidraw Create a flowchart of user registration with email verification
```

```
/excalidraw Diagram the architecture of this project
```

```
/excalidraw Add a Redis cache between the API and database in ./architecture.excalidraw
```

## How It Works

1. You describe the diagram you want (or reference code to analyze)
2. The diagram-architect agent generates a compact skeleton JSON
3. A Node.js converter script expands it into a valid `.excalidraw` file
4. The file is saved and you can open it in excalidraw.com or any compatible editor

## Supported Diagram Types

| Type | Layout | Use Case |
|------|--------|----------|
| Architecture | `grid` or `left-right` | System overviews, microservices |
| Flowchart | `top-down` | Processes, decision trees |
| Data Flow | `left-right` | Request pipelines, data processing |
| ER Diagram | `grid` | Database relationships |
| Dependency Graph | `top-down` | Package/module dependencies |

## Supported Elements

- **Shapes**: rectangle, diamond, ellipse
- **Connectors**: arrow (with labels, styles, arrowheads), line (with multi-segment `points` arrays)
- **Text**: standalone text elements
- **Frames**: named groups that visually contain other elements

## Arrow Binding

Arrows automatically compute edge-aware `FixedPointBinding` positions:
- If shape B is **below** shape A, the arrow exits A from the **bottom** and enters B from the **top**
- If shape B is to the **right** of A, the arrow exits from the **right** and enters from the **left**
- Multiple arrows to the same shape connect at different edge points (no overlapping at center)

## Color Themes

| Theme | Description |
|-------|-------------|
| `default` | Colorful fills with matching strokes on white background |
| `blueprint` | Light strokes on dark blue background, no fills |
| `warm` | Warm-toned backgrounds on white |
| `monochrome` | All gray tones |

## Requirements

- Claude Code
- Node.js >= 18

## File Structure

```
.claude-plugin/
  plugin.json          # Plugin manifest
agents/
  diagram-architect.md # Isolated agent for diagram generation
commands/
  excalidraw.md        # /excalidraw slash command
skills/
  excalidraw/
    SKILL.md           # Skill definition with workflow instructions
    references/
      format-reference.md  # Excalidraw JSON format reference
scripts/
  convert.js           # Zero-dep Node.js skeleton-to-excalidraw converter
```

## License

MIT
