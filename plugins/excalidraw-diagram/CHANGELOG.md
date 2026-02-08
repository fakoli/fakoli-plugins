# Changelog

## [1.1.0] - 2026-02-08

### Fixed
- Arrow fixedPoints now computed based on relative shape positions instead of always [0.5, 0.5] — multiple arrows to the same shape connect at different edges
- Text width estimation uses character-class buckets (narrow/medium/wide) for ~80-85% accuracy (was ~40-60%)
- Modification-mode arrows can now bind to elements in the existing file, not just new skeleton elements
- Grid and tree/flow layouts respect variable element sizes — no more overlaps with mixed dimensions
- `needsAutoLayout()` returns false only when ALL shapes have coordinates (was: ANY)
- `boundElements` deduplication prevents duplicate entries in modification mode
- Frame children emit warnings for unresolved IDs instead of silently skipping
- Removed `customData: undefined` from base element (cleaner serialization)

### Added
- Skeleton input validation with collected error reporting (type, id, arrow from/to checks)
- Line element `points` array and elbowed arrow type documented in agent docs
- Browser preview via React fiber traversal documented (replaces non-functional approaches)

### Changed
- Agent docs use `${CLAUDE_PLUGIN_ROOT}/scripts/convert.js` (was undefined `CONVERTER_PATH`)
- Command file reframed as agent instructions (was user-addressed)

## [1.0.0] - 2026-02-08

### Added
- Initial release
- Zero-dependency Node.js converter script for skeleton-to-excalidraw conversion
- Diagram architect agent with isolated context for diagram generation
- Excalidraw skill with format reference and workflow instructions
- `/excalidraw` slash command for natural language diagram generation
- Support for element types: rectangle, diamond, ellipse, text, arrow, line, frame
- Three layout algorithms: grid, top-down tree, left-to-right flow
- Four color themes: default, blueprint, warm, monochrome
- Diagram modification mode (add/remove elements from existing files)
- Arrow binding with FixedPointBinding format
- Text-in-shape binding with containerId
- Frame elements with automatic bounds computation
- Browser preview support via claude-in-chrome MCP
- Code-aware diagram generation from codebase analysis
