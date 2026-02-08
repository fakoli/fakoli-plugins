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

## Plugin Manifest Schema

**Official Reference:** https://code.claude.com/docs/en/plugins-reference

### Required Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier (kebab-case, no spaces) |

### Optional Metadata Fields
| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Semantic version (e.g., `1.0.0`) |
| `description` | string | Brief explanation of plugin purpose |
| `author` | object | `{name, email?, url?}` |
| `homepage` | string | Documentation URL |
| `repository` | string | Source code URL (must be string, not object) |
| `license` | string | SPDX license identifier |
| `keywords` | array | Discovery tags |

### Component Path Fields
| Field | Type | Description |
|-------|------|-------------|
| `commands` | string\|array | Additional command files/directories |
| `agents` | string\|array | Additional agent files |
| `skills` | string\|array | Additional skill directories |
| `hooks` | string\|object | Hook config path or inline config |
| `mcpServers` | string\|object | MCP config path or inline config |
| `outputStyles` | string\|array | Additional output style files/directories |
| `lspServers` | string\|object | LSP config for code intelligence |

### Example plugin.json
```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Brief plugin description",
  "author": {
    "name": "Author Name",
    "url": "https://github.com/author"
  },
  "repository": "https://github.com/author/plugin",
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"]
}
```

**Important:** Claude Code discovers skills, commands, agents, and hooks from directories - not from manifest fields. Only use manifest component paths for non-standard locations.

## Dependencies

Scripts require `jq` for JSON processing:
```bash
brew install jq  # macOS
apt-get install jq  # Linux
```

## Plugin Development Patterns

### Python Scripts with uv
- Use `uv run --with <pkg>` for one-off dependency testing
- Define dependencies in `pyproject.toml` for plugin scripts
- Test with: `uv run python -c "import module; print('OK')"`

### Documentation Hygiene
- README.md is the authoritative source for configuration/troubleshooting
- SKILL.md should be minimal: frontmatter + quick reference + links to README
- Command files link to README sections instead of duplicating content

### Versioning
- Update plugin version in `.claude-plugin/plugin.json` whenever plugin changes
- Follow semver: patch for fixes, minor for features, major for breaking changes

### New Plugin Checklist
When adding a new plugin, ALWAYS complete ALL of these steps before merging:
1. Create the plugin in `plugins/<name>/` with all required files
2. **Update `README.md`** — add the plugin to the "Available Plugins" table
3. Run `./scripts/generate-index.sh` to regenerate `registry/index.json`
4. Run `./scripts/validate.sh plugins/<name>` to validate the plugin
5. Verify the plugin appears in both the README table AND `registry/index.json`

## Official Claude Code Documentation

Reference these official docs for detailed specifications:

| Topic | URL |
|-------|-----|
| Plugin Reference | https://code.claude.com/docs/en/plugins-reference |
| Hooks | https://code.claude.com/docs/en/hooks |
| Plugins Overview | https://code.claude.com/docs/en/plugins |
| Sub-agents | https://code.claude.com/docs/en/sub-agents |
| Skills | https://code.claude.com/docs/en/skills |
