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

### Plugin Deep Scanner
```bash
./scripts/test-path-resolution.sh              # Deep scan all plugins
./scripts/test-path-resolution.sh plugins/<name>  # Scan specific plugin
```

### Validation Tests
```bash
./tests/test-hooks-validation.sh              # Run hook validation test suite
```

### Schema Drift Detection
```bash
./scripts/check-schema-drift.sh               # Check for upstream schema changes
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
- `archive/` - Archived project-specific plugins (not indexed)
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
1. `validate.sh` checks: JSON syntax, required fields, semver format, name format, component directories, path resolution, hook safety
2. `test-path-resolution.sh` performs deep scanning: all component path fields, script existence, `set -e` detection, `cat|grep` anti-patterns, matcher analysis
3. GitHub Actions runs both scripts on push to `plugins/` or `schemas/`
4. `update-index.yml` auto-regenerates registry on merge to main

### Validation Reference

| Check | Script | Severity |
|-------|--------|----------|
| JSON syntax, required fields, semver | `validate.sh` | ERROR |
| Unrecognized manifest field (`$schema`, etc) | `validate.sh` | ERROR |
| Hook entry missing `hooks` array wrapper | `validate.sh` | ERROR |
| Empty `hooks` array in hook entry | `validate.sh` | ERROR |
| Auto-discovered field declared | `validate.sh` | WARN |
| `../` path confusion (should be `./`) | `validate.sh` | WARN |
| hooks/mcpServers path not found | `validate.sh` | ERROR |
| License field without LICENSE file | `validate.sh` | WARN |
| Broad matcher on high-frequency event | `validate.sh` | WARN |
| prompt-type on UserPromptSubmit | `validate.sh` | ERROR |
| prompt-type on PreToolUse (no matcher) | `validate.sh` | ERROR |
| `set -e` in hook scripts | `validate.sh` | WARN |
| Hook script not found | `validate.sh` | ERROR |
| Missing hook timeout | `validate.sh` | WARN |
| `cat \| grep` in hook scripts | `test-path-resolution.sh` | WARN |
| All component path fields (deep) | `test-path-resolution.sh` | ERROR |

**Manual review still needed:** hook logic correctness, matcher specificity beyond presence/absence, script security

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

### Path Resolution Rules

All paths in `plugin.json` resolve **relative to the plugin root** and must start with `./`.

**Rule 1:** Don't declare standard auto-discovered directories (`skills/`, `commands/`, `agents/`, `hooks/`) — Claude Code finds them automatically.

**Rule 2:** Use `./` prefix for all paths (relative to plugin root, not `.claude-plugin/`).

| Scenario | Correct | Incorrect |
|----------|---------|-----------|
| Reference hooks.json at plugin root | `"hooks": "./hooks/hooks.json"` | `"hooks": "../hooks/hooks.json"` |
| Reference .mcp.json at plugin root | `"mcpServers": "./.mcp.json"` | `"mcpServers": "../.mcp.json"` |
| Reference skills dir (unnecessary) | _(don't declare — auto-discovered)_ | `"skills": "./skills"` |

**Directory layout:**
```
my-plugin/
├── .claude-plugin/
│   └── plugin.json      ← manifest lives here, but paths resolve from plugin root
├── hooks/
│   └── hooks.json       ← referenced as "./hooks/hooks.json"
├── skills/              ← auto-discovered, don't declare
├── commands/            ← auto-discovered, don't declare
└── .mcp.json            ← referenced as "./.mcp.json"
```

### Hook Safety Rules

Lessons from production incidents — these anti-patterns cause hooks to block all conversations or crash silently:

1. **Always use the `hooks` array wrapper** — Claude Code requires every hook entry to have a `hooks: [...]` array, even without a matcher. Direct `{type, command}` entries cause `expected array, received undefined` errors.
2. **Never use `set -e` in hook scripts** — breaks `|| fallback` patterns. A `grep` returning non-zero kills the entire script, blocking all responses.
3. **Never use prompt-type hooks on `UserPromptSubmit`** — fires on every message, injecting AI evaluation that hijacks the conversation.
4. **Always use specific matchers** on `PreToolUse`/`PostToolUse` — broad/empty matchers cause hooks to fire on every tool call.
5. **Always set timeouts** on command-type hooks — prevents indefinite hangs.
6. **Grep files directly** — never `cat file | grep` or `var=$(cat file); echo "$var" | grep` — ARG_MAX failures on large transcripts.
7. **Match invocations, not mentions** — use transcript JSON patterns (`"subagent_type": "plugin:..."`, `"skill": "plugin:..."`) not loose keyword matching.
8. **Command gates over prompt gates** — command hooks can scope/skip gracefully; prompt hooks fire unconditionally.

**Safe Hook Template:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "SpecificToolName",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/my-check.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Schema-Driven Validation

The schema `schemas/plugin.schema.json` is the **single source of truth** for allowed plugin.json fields. `validate.sh` derives its `ALLOWED_FIELDS` list directly from the schema at runtime — no hardcoded field lists.

**Available schemas:**
| Schema | Validates |
|--------|-----------|
| `schemas/plugin.schema.json` | Plugin manifests (`.claude-plugin/plugin.json`) |
| `schemas/marketplace.schema.json` | Marketplace config (`.claude-plugin/marketplace.json`) |
| `schemas/index.schema.json` | Registry index (`registry/index.json`) |
| `schemas/hooks.schema.json` | Hook configs (`hooks/hooks.json`) |
| `schemas/mcp.schema.json` | MCP configs (`.mcp.json`) |
| `schemas/skill.schema.json` | Skill frontmatter (`SKILL.md` YAML) |

**Note:** Do not add `$schema` to plugin.json or hooks.json — Claude Code rejects unrecognized keys. Internal files (index.json, marketplace.json) may use `$schema` for IDE validation since Claude Code does not parse them.

### Schema Drift Detection

```bash
./scripts/check-schema-drift.sh    # Compare schema vs baseline vs upstream docs
```

- Compares `schemas/plugin.schema.json` against `schemas/.field-baseline.json` (last-known official fields)
- Optionally scrapes Anthropic docs page for newly added fields
- CI runs weekly via `.github/workflows/schema-drift.yml` (auto-creates GitHub issue on drift)

**When Anthropic adds new fields:** Update `schemas/plugin.schema.json` and `schemas/.field-baseline.json` — validation updates automatically.

## Dependencies

Scripts require `jq` for JSON processing:
```bash
brew install jq  # macOS
apt-get install jq  # Linux
```

## Plugin Development Patterns

### Testing Standards
See `docs/TESTING_STANDARDS.md` for full testing guidance, including hook testing patterns, CI integration, and coverage expectations.

### Python Scripts with uv
- Use `uv run --with <pkg>` for one-off dependency testing
- Define dependencies in `pyproject.toml` for plugin scripts
- Test with: `uv run python -c "import module; print('OK')"`

### Documentation Hygiene
- README.md is the authoritative source for configuration/troubleshooting
- SKILL.md should be minimal: frontmatter + quick reference + links to README
- Command files link to README sections instead of duplicating content

### Versioning (CRITICAL)
- **ALWAYS bump the version** in `.claude-plugin/plugin.json` whenever ANY file in a plugin changes — even metadata-only or docs-only changes
- Before committing, check which plugins have modified files (`git diff --name-only plugins/`) and bump the patch version for each affected plugin
- Follow semver: patch for fixes, minor for features, major for breaking changes
- After bumping versions, run `./scripts/generate-index.sh` to update the registry with new versions
- Plugin consumers use the version to detect updates — unchanged versions mean cached copies are never refreshed

### Existing Plugin Change Checklist
When modifying ANY file in an existing plugin, ALWAYS complete these steps before committing:
1. **Bump the version** in `.claude-plugin/plugin.json` (patch for fixes, minor for features)
2. Run `./scripts/generate-index.sh` to update registry with new version
3. Run `./scripts/validate.sh plugins/<name>` to validate
4. Run `./scripts/test-path-resolution.sh plugins/<name>` to deep scan

### Keeping Sources in Sync

Three sources must always agree on the active plugin set:

1. `README.md` — "Available Plugins" table
2. `registry/index.json` — auto-generated by `generate-index.sh`
3. `.claude-plugin/marketplace.json` — marketplace metadata

**Archived plugins must NOT appear in any of the three sync sources.** Plugins moved to `archive/` should be removed from the README table, are excluded from index generation (scripts only scan `plugins/`), and must not have entries in `marketplace.json`.

### New Plugin Checklist
When adding a new plugin, ALWAYS complete ALL of these steps before merging:
1. Create the plugin in `plugins/<name>/` with all required files
2. **Update `README.md`** — add the plugin to the "Available Plugins" table
3. **Set initial version** to `1.0.0` in `.claude-plugin/plugin.json`
4. Run `./scripts/generate-index.sh` to regenerate `registry/index.json`
5. Run `./scripts/validate.sh plugins/<name>` to validate the plugin
6. Run `./scripts/test-path-resolution.sh plugins/<name>` to deep scan paths and hooks
7. Verify no auto-discovered directories (`skills/`, `commands/`, `agents/`) are declared in manifest
8. Verify `hooks`/`mcpServers` paths use `./` prefix (relative to plugin root) and targets exist
9. If plugin has hooks: verify matchers are specific, no `set -e`, timeouts are set
10. **Assign a category** in `.claude-plugin/marketplace.json` — must be one of: `productivity`, `integrations`, `utilities`
11. Verify the plugin appears in both the README table AND `registry/index.json`

## Official Claude Code Documentation

Reference these official docs for detailed specifications:

| Topic | URL |
|-------|-----|
| Plugin Reference | https://code.claude.com/docs/en/plugins-reference |
| Hooks | https://code.claude.com/docs/en/hooks |
| Plugins Overview | https://code.claude.com/docs/en/plugins |
| Sub-agents | https://code.claude.com/docs/en/sub-agents |
| Skills | https://code.claude.com/docs/en/skills |
