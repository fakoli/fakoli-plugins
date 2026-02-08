# Excalidraw Format Reference

This document describes the `.excalidraw` JSON file format for reference when generating or debugging diagrams.

## File Structure

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [...],
  "appState": {...},
  "files": {}
}
```

## Element Base Properties

Every element has these properties:

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `id` | string | generated | Unique ID (20-char alphanumeric) |
| `type` | string | required | Element type |
| `x` | number | 0 | X position |
| `y` | number | 0 | Y position |
| `width` | number | 0 | Width |
| `height` | number | 0 | Height |
| `angle` | number | 0 | Rotation in radians |
| `strokeColor` | string | `"#1e1e1e"` | Stroke/border color |
| `backgroundColor` | string | `"transparent"` | Fill color |
| `fillStyle` | string | `"solid"` | Fill pattern |
| `strokeWidth` | number | 2 | Border width |
| `strokeStyle` | string | `"solid"` | Border style |
| `roughness` | number | 1 | Hand-drawn roughness (0-2) |
| `opacity` | number | 100 | Opacity (0-100) |
| `groupIds` | string[] | [] | Group memberships |
| `frameId` | string\|null | null | Parent frame ID |
| `index` | string | generated | Fractional index for ordering |
| `roundness` | object\|null | varies | Corner rounding config |
| `seed` | number | random | Roughjs seed for consistent rendering |
| `version` | number | 1 | Version counter |
| `versionNonce` | number | random | Version uniqueness |
| `isDeleted` | boolean | false | Soft delete flag |
| `boundElements` | array\|null | null | Elements bound to this one |
| `updated` | number | timestamp | Last update timestamp |
| `link` | string\|null | null | URL link |
| `locked` | boolean | false | Lock flag |

## Text Element Additional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `text` | string | required | Display text |
| `originalText` | string | same as text | Original text before wrapping |
| `fontSize` | number | 20 | Font size in px |
| `fontFamily` | number | 5 | Font family ID (5=Excalifont) |
| `textAlign` | string | `"left"` | Horizontal: `left`, `center`, `right` |
| `verticalAlign` | string | `"top"` | Vertical: `top`, `middle`, `bottom` |
| `lineHeight` | number | 1.25 | Line height multiplier |
| `containerId` | string\|null | null | Parent container element ID |
| `autoResize` | boolean | true | Auto-resize text |

## Arrow/Line Additional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `points` | number[][] | [[0,0],[w,h]] | Point coordinates relative to element origin |
| `startBinding` | object\|null | null | Start point binding |
| `endBinding` | object\|null | null | End point binding |
| `startArrowhead` | string\|null | null | Start arrowhead type |
| `endArrowhead` | string\|null | `"arrow"` | End arrowhead type |
| `lastCommittedPoint` | null | null | Internal state |

## FixedPointBinding Format

```json
{
  "elementId": "target-element-id",
  "fixedPoint": [0.5, 0.5],
  "mode": "orbit"
}
```

- `elementId`: ID of the element the arrow binds to
- `fixedPoint`: [x_ratio, y_ratio] where 0.0-1.0 represents position on the target element (0.5, 0.5 = center)
- `mode`: Binding mode
  - `"orbit"`: Arrow stays outside the shape with a gap (default for most cases)
  - `"inside"`: Arrow can go inside the shape
  - `"skip"`: No binding

## boundElements Format

```json
{
  "boundElements": [
    { "type": "text", "id": "text-element-id" },
    { "type": "arrow", "id": "arrow-element-id" }
  ]
}
```

## Roundness

| Element Type | Roundness |
|-------------|-----------|
| rectangle | `{ "type": 3 }` (ADAPTIVE_RADIUS) |
| diamond | `{ "type": 2 }` (PROPORTIONAL_RADIUS) |
| ellipse | `null` |
| arrow/line | `{ "type": 2 }` (PROPORTIONAL_RADIUS) |

## Frame Element

Frames are containers that visually group elements. Additional properties:
- `name`: Frame label displayed above the frame

Child elements reference the frame via `frameId`.

## Color Palette (Excalidraw Native)

| Name | Hex | Usage |
|------|-----|-------|
| black | `#1e1e1e` | Default stroke |
| white | `#ffffff` | Background |
| transparent | `transparent` | Default fill |
| blue | `#228be6` | Primary accent |
| red | `#fa5252` | Error/danger |
| green | `#40c057` | Success/positive |
| orange | `#fd7e14` | Warning/external |
| violet | `#7950f2` | Special/unique |
| yellow | `#fab005` | Highlight/attention |
| cyan | `#15aabf` | Info/secondary |
| teal | `#12b886` | Alternative positive |
| pink | `#e64980` | Accent |
| grape | `#be4bdb` | Accent |

Each color has 5 shades [0-4]: lightest to darkest. Index 3 is used for strokes, index 0 for backgrounds.

## Font Family IDs

| ID | Name | Style |
|----|------|-------|
| 1 | Virgil | Hand-drawn (legacy) |
| 2 | Helvetica | Clean sans-serif |
| 3 | Cascadia | Monospace |
| 5 | Excalifont | Hand-drawn (current default) |
| 6 | Nunito | Rounded sans-serif |

## Arrowhead Types

- `null` — No arrowhead
- `"arrow"` — Standard arrow
- `"bar"` — Flat bar
- `"circle"` — Filled circle
- `"circle_outline"` — Hollow circle
- `"triangle"` — Filled triangle
- `"triangle_outline"` — Hollow triangle
- `"diamond"` — Filled diamond
- `"diamond_outline"` — Hollow diamond
- `"crowfoot_one"` — Crowfoot one (ER diagrams)
- `"crowfoot_many"` — Crowfoot many (ER diagrams)
- `"crowfoot_one_or_many"` — Crowfoot one-or-many (ER diagrams)

## AppState

Key appState fields for export:

```json
{
  "viewBackgroundColor": "#ffffff",
  "gridSize": 20,
  "gridStep": 5,
  "gridModeEnabled": false,
  "scrollX": 0,
  "scrollY": 0,
  "zoom": { "value": 1 }
}
```
