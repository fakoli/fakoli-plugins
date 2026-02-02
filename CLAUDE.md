# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fakoli Plugins Marketplace - a curated distribution platform for Claude Code plugins. This repository manages plugin validation, indexing, and publishing workflows.

## Key Commands

### Plugin Validation
```bash
./scripts/validate.sh                     # Validate all plugins
./scripts/validate.sh plugins/<name>      # Validate specific plugin
```

### Registry Generation
```bash
./scripts/generate-index.sh               # Regenerate registry/index.json
```

### Marketplace Manager (via plugin)
```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/add_plugin.sh <name>
./plugins/marketplace-manager/skills/marketplace-manager/scripts/remove_plugin.sh <name>
./plugins/marketplace-manager/skills/marketplace-manager/scripts/marketplace_status.sh
```

## Architecture

### Directory Structure
- `plugins/` - First-party plugins (each with `.claude-plugin/plugin.json`)
- `external_plugins/` - Modified third-party plugins (requires `UPSTREAM.md`)
- `registry/` - Auto-generated indices (index.json, categories.json, tags.json)
- `schemas/` - JSON Schema for plugin manifest validation
- `scripts/` - Bash validation and index generation tools
- `templates/basic/` - Starter template for new plugins

### Plugin Components
Each plugin in `plugins/<name>/` must have:
- `.claude-plugin/plugin.json` - Manifest with name, version, description
- At least one of: `skills/`, `commands/`, `agents/`, or `hooks/`
- `README.md` - Documentation

### Validation Pipeline
1. `validate.sh` checks: JSON syntax, required fields, semver format, name format (lowercase/hyphens), component directories
2. GitHub Actions runs validation on push to `plugins/` or `schemas/`
3. `update-index.yml` auto-regenerates registry on merge to main

## Manifest Requirements

Plugin names: lowercase alphanumeric + hyphens only, 2-64 chars
Versions: Semantic versioning (e.g., `1.0.0`, `1.0.0-beta.1`)
Description: 10-500 characters
Categories: `productivity`, `code-quality`, `devops`, `integrations`, `utilities`

## Dependencies

Scripts require `jq` for JSON processing:
```bash
brew install jq  # macOS
apt-get install jq  # Linux
```
