# Changelog

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
