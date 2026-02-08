---
name: excalidraw
description: Generate and modify Excalidraw diagrams from natural language and code analysis using skeleton JSON and a Node.js converter
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Excalidraw Diagram Generation Skill

Generate `.excalidraw` diagram files from natural language descriptions or code analysis. Uses a skeleton JSON intermediate format and a zero-dependency Node.js converter script.

## Quick Reference

| Action | How |
|--------|-----|
| Create a diagram | Generate skeleton JSON, pipe to converter |
| Modify a diagram | Read existing file, generate additions skeleton with `--modify` |
| Change layout | Set `"layout"` in skeleton: `grid`, `top-down`, `left-right` |
| Change theme | Set `"theme"` in skeleton: `default`, `blueprint`, `warm`, `monochrome` |

## Converter Script Location

```bash
CONVERTER_PATH="${CLAUDE_PLUGIN_ROOT}/scripts/convert.js"
```

## Workflow

### 1. Create a New Diagram

Write skeleton JSON to a temp file, then run the converter:

```bash
# Write skeleton to temp file
cat > /tmp/excalidraw-skeleton.json << 'SKELETON_EOF'
{
  "type": "excalidraw-skeleton",
  "version": 1,
  "theme": "default",
  "layout": "top-down",
  "elements": [
    { "type": "ellipse", "id": "start", "label": "Start", "color": "green", "width": 120, "height": 60 },
    { "type": "rectangle", "id": "process", "label": "Process Data", "color": "blue" },
    { "type": "diamond", "id": "decision", "label": "Valid?", "color": "orange", "width": 140, "height": 100 },
    { "type": "rectangle", "id": "success", "label": "Save Result", "color": "green" },
    { "type": "rectangle", "id": "error", "label": "Handle Error", "color": "red" },
    { "type": "arrow", "from": "start", "to": "process" },
    { "type": "arrow", "from": "process", "to": "decision" },
    { "type": "arrow", "from": "decision", "to": "success", "label": "Yes" },
    { "type": "arrow", "from": "decision", "to": "error", "label": "No" }
  ]
}
SKELETON_EOF

# Convert
node "${CLAUDE_PLUGIN_ROOT}/scripts/convert.js" /tmp/excalidraw-skeleton.json ./diagram.excalidraw
```

### 2. Modify an Existing Diagram

```bash
# Write additions skeleton
cat > /tmp/excalidraw-additions.json << 'SKELETON_EOF'
{
  "type": "excalidraw-skeleton",
  "version": 1,
  "elements": [
    { "type": "rectangle", "id": "cache", "label": "Redis Cache", "color": "red", "x": 500, "y": 200, "width": 180, "height": 70 },
    { "type": "arrow", "from": "cache", "to": "db", "label": "Fallback", "style": "dashed" }
  ],
  "remove": ["legacy-adapter"]
}
SKELETON_EOF

# Modify
node "${CLAUDE_PLUGIN_ROOT}/scripts/convert.js" --modify ./architecture.excalidraw /tmp/excalidraw-additions.json ./architecture-updated.excalidraw
```

### 3. From Stdin

```bash
echo '{"type":"excalidraw-skeleton","version":1,"layout":"grid","elements":[{"type":"rectangle","id":"a","label":"Service A","color":"blue"},{"type":"rectangle","id":"b","label":"Service B","color":"green"},{"type":"arrow","from":"a","to":"b"}]}' | node "${CLAUDE_PLUGIN_ROOT}/scripts/convert.js" --stdin ./quick-diagram.excalidraw
```

## Skeleton Format Quick Reference

### Shape Types
- `rectangle` — Default shape, good for services/processes
- `diamond` — Decision points, conditionals
- `ellipse` — Start/end states, external entities

### Arrow Properties
- `from`/`to` — Connect shapes by ID (converter handles binding)
- `label` — Text on the arrow
- `style` — `solid`, `dashed`, `dotted`
- `startArrowhead`/`endArrowhead` — `null`, `arrow`, `bar`, `circle`, `triangle`, `diamond`

### Colors
Semantic names: `blue`, `red`, `green`, `orange`, `violet`, `yellow`, `cyan`, `teal`, `pink`, `grape`, `gray`, `black`, `white`, `bronze`

Or use hex: `"#ff6600"`

### Layouts
- `grid` — Default, rows and columns
- `top-down` / `tree` / `flowchart` — Hierarchy flows downward
- `left-right` / `pipeline` / `flow` — Flows left to right

### Themes
- `default` — Colorful with white background
- `blueprint` — Dark background, light strokes, no fills
- `warm` — Warm-toned backgrounds
- `monochrome` — All gray

## Code-Aware Diagram Generation

When generating diagrams from a codebase:

1. **Import Graph**: Use `Grep` to find import statements, map dependencies between modules.
2. **Package Structure**: Use `Glob` to find package.json files, understand module boundaries.
3. **Component Hierarchy**: Read key files to understand component nesting and data flow.
4. **API Routes**: Grep for route definitions to map API surface.

Example analysis patterns:
```
# Find all imports in a directory
Grep: import.*from  (in src/**/*.ts)

# Find package boundaries
Glob: **/package.json

# Find API routes
Grep: (router\.(get|post|put|delete)|app\.(get|post|put|delete))

# Find React components
Grep: export.*function.*\(|export.*const.*=.*=>
```

## Output

After running the converter, it outputs JSON to stdout:
```json
{"success": true, "outputPath": "/absolute/path/to/diagram.excalidraw", "elementCount": 12, "message": "Wrote 12 elements to ..."}
```

Always report the file path to the user and suggest opening with excalidraw.com.
