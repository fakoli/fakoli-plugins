---
name: excalidraw
description: Create or extend editable Excalidraw diagrams from descriptions or repository evidence using a local skeleton-to-scene converter.
---

# Editable Excalidraw diagrams

Deliver an editable `.excalidraw` file. Read the relevant source or existing scene before representing it; distinguish observed architecture from proposed changes.

Resolve `../../scripts/convert.js` relative to this skill directory. Use its absolute path with Node.js 18 or newer; the converter has no npm dependencies. Do not depend on the shell's working directory or a particular host's plugin-root environment variable.

## Create

Write a skeleton JSON file in the task workspace, then run:

```sh
node /resolved/plugin/scripts/convert.js skeleton.json diagram.excalidraw
```

```json
{
  "type": "excalidraw-skeleton",
  "version": 1,
  "layout": "left-right",
  "elements": [
    {"type": "rectangle", "id": "api", "label": "API", "color": "blue"},
    {"type": "rectangle", "id": "db", "label": "Database", "color": "green"},
    {"type": "arrow", "id": "query", "from": "api", "to": "db", "label": "Queries"}
  ]
}
```

Supported shapes: rectangle, diamond, ellipse, text, arrow, line, frame. Use `grid`, `top-down`, or `left-right` layout and `default`, `blueprint`, `warm`, or `monochrome` theme. Explicit coordinates are preserved; supply all shape coordinates for precise layout. IDs remain stable in the output. Elbowed arrow routing is not implemented.

Read [the format reference](references/format-reference.md) for properties, line points, frames, and style options. Keep labels short enough to fit the boxes; text measurement is approximate, so visually inspect diagrams with long labels or complex routing.

## Extend or remove

Read the existing file and use its actual element IDs. The converter accepts additions and removals, preserving the scene's embedded files and app state:

```sh
node /resolved/plugin/scripts/convert.js --modify existing.excalidraw additions.json updated.excalidraw
```

Add new elements using new IDs and connect arrows to either new or existing shapes. Put existing IDs in a top-level `remove` array to delete them. Removing containers also removes bound labels; arrows remain with detached bindings. Removing a frame leaves its contents unframed. Unknown references and duplicate IDs fail before writing. To change existing properties, edit the scene deliberately and preserve reciprocal bindings, or replace the affected elements and their connectors; do not pass a duplicate ID as an addition.

## Verify and deliver

Check the converter's exit status and JSON result. Read the output, confirm node/edge counts and intended relationships, and inspect it in an available Excalidraw editor when possible. Use the editor's normal file import or a documented `excalidrawAPI` integration; do not traverse React internals. Report the absolute output path and any preview limitation. Creation alone does not prove that a complex layout is visually clear.

[Plugin documentation](../../README.md) covers installation and CLI checks.
