---
description: Generate or modify Excalidraw diagrams from descriptions or code analysis
argument-hint: Describe the diagram you want, e.g. "architecture of this project" or "flowchart of user registration"
---

# Excalidraw Diagram Generation

You are generating an Excalidraw diagram based on the user's request.

## Request

$ARGUMENTS

## Instructions

1. **Analyze the request**: Determine what kind of diagram is needed (architecture, flowchart, ER, dependency graph, etc.)

2. **Gather information if needed**:
   - If the user references the codebase ("diagram this project", "show the architecture"), use Glob and Grep to analyze the code structure, imports, and components.
   - If the user provides a description, use it directly.
   - If an existing `.excalidraw` file is referenced, read it first.

3. **Choose the right settings**:
   - **Layout**: `top-down` for flowcharts/trees, `left-right` for pipelines/flows, `grid` for architecture overviews
   - **Theme**: `default` for most cases, `blueprint` for dark-background formal docs, `monochrome` for print
   - **Colors**: Use consistent color coding (e.g., blue for services, green for databases, orange for external systems)

4. **Generate skeleton JSON**: Create the skeleton with all shapes, arrows, labels, and frames needed.

5. **Run the converter**:
   ```bash
   node "${CLAUDE_PLUGIN_ROOT}/scripts/convert.js" /tmp/excalidraw-skeleton.json <output-path>
   ```

6. **Report results**: Tell the user the file path and how to open it.

## Output Path

- Default: `./<diagram-name>.excalidraw` in the current working directory
- If the user specifies a path, use that
- For modifications, default to writing a new file (don't overwrite unless asked)

## Converter Script

Located at: `${CLAUDE_PLUGIN_ROOT}/scripts/convert.js`

### Create mode:
```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/convert.js" /tmp/excalidraw-skeleton.json output.excalidraw
```

### Modify mode:
```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/convert.js" --modify existing.excalidraw /tmp/excalidraw-additions.json output.excalidraw
```

## Skeleton Format

Write the skeleton JSON to `/tmp/excalidraw-skeleton.json` before running the converter. See the excalidraw skill for full format documentation.

### Quick shape reference:
- `rectangle` — Services, processes, components
- `diamond` — Decisions, conditionals
- `ellipse` — Start/end, external entities
- `arrow` — Connections (use `from`/`to` with shape IDs)
- `line` — Dividers, boundaries
- `text` — Standalone titles, annotations
- `frame` — Named groups with `children` array

### Quick property reference:
- `color`: `blue`, `red`, `green`, `orange`, `violet`, `yellow`, `cyan`, `teal`, `pink`, `grape`, `gray`, `black`
- `layout`: `grid`, `top-down`, `left-right`
- `theme`: `default`, `blueprint`, `warm`, `monochrome`
- `style` (arrows): `solid`, `dashed`, `dotted`
