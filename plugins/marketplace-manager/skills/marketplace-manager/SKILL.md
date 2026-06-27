---
name: marketplace-manager
description: "Manage the fakoli-plugins marketplace. Use when: (1) adding a new plugin to the marketplace, (2) removing a plugin, (3) validating plugins, (4) regenerating registry indices, (5) checking marketplace status, or (6) any plugin registry management task. Triggers on phrases like \"add plugin\", \"validate plugins\", \"update registry\", \"marketplace status\"."
---

# Marketplace Manager

Manage the fakoli-plugins marketplace: add/remove plugins, validate manifests, and regenerate registry indices.

## Quick Reference

| Task | Command |
|------|---------|
| Validate all plugins | `./scripts/validate.sh` |
| Validate single plugin | `./scripts/validate.sh plugins/<name>` |
| Regenerate indices | `./scripts/generate-index.sh` |
| Check marketplace status | Read `.claude-plugin/marketplace.json` |

## Workflows

### Adding a New Plugin

1. **Create plugin from template**
   ```bash
   cp -r templates/basic plugins/<plugin-name>
   ```

2. **Update manifest** at `plugins/<plugin-name>/.claude-plugin/plugin.json`:
   - Set `name` (lowercase, alphanumeric, hyphens only)
   - Set `version` (semver format: x.y.z)
   - Write `description` (10-500 chars)
   - Add `author` info
   - Set `keywords` with relevant discovery tags
   - Keep marketplace-only metadata out of `plugin.json`

3. **Add plugin components** (at least one required):
   - Skills: `skills/<skill-name>/SKILL.md`
   - Commands: `commands/<cmd>.md`
   - Agents: `agents/<agent>.md`
   - Hooks: `hooks/<hook>.json`

4. **Update documentation**:
   - Edit `README.md` with usage instructions
   - Update `CHANGELOG.md`

5. **Validate**
   ```bash
   ./scripts/validate.sh plugins/<plugin-name>
   ```

6. **Register in marketplace**
   Add entry to `.claude-plugin/marketplace.json` plugins array:
   ```json
   {
     "name": "<plugin-name>",
     "version": "1.0.0",
     "description": "Concise marketplace description",
     "category": "development",
     "source": "./plugins/<plugin-name>"
   }
   ```
   The category must be one declared in `.claude-plugin/marketplace.json`.

7. **Regenerate indices**
   ```bash
   ./scripts/generate-index.sh
   ```

### Removing a Plugin

1. Remove from `.claude-plugin/marketplace.json` plugins array
2. Delete plugin directory: `rm -rf plugins/<plugin-name>`
3. Regenerate indices: `./scripts/generate-index.sh`

### Validating Plugins

**Validate all plugins:**
```bash
./scripts/validate.sh
```

**Validate specific plugin:**
```bash
./scripts/validate.sh plugins/<plugin-name>
```

Validation checks:
- JSON syntax validity
- Required fields: name, version, description
- Name format (lowercase, alphanumeric, hyphens)
- Version format (semver)
- README.md presence
- CHANGELOG.md presence
- At least one component (skill/command/agent/hook)

### Regenerating Registry Indices

```bash
./scripts/generate-index.sh
```

Generates:
- `registry/index.json` - Full plugin index with metadata
- `registry/categories.json` - Plugins grouped by category
- `registry/tags.json` - Tag cloud with counts

### Checking Marketplace Status

Read current state:
```bash
cat .claude-plugin/marketplace.json
cat registry/index.json
```

Quick stats:
```bash
jq '.pluginCount' registry/index.json
jq '.categories | length' registry/categories.json
jq '.totalTags' registry/tags.json
```

## Plugin Manifest Schema

Required fields:
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "10-500 character description"
}
```

Marketplace plugin entry:
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Concise marketplace description",
  "category": "development",
  "source": "./plugins/plugin-name"
}
```

Marketplace-only fields such as category and source belong in
`.claude-plugin/marketplace.json`, not in `plugin.json`.

## Directory Structure

```
fakoli-plugins/
├── .claude-plugin/marketplace.json  # Registry config
├── plugins/<plugin-name>/           # First-party plugins
│   ├── .claude-plugin/plugin.json
│   ├── skills/
│   ├── README.md
│   └── CHANGELOG.md
├── external_plugins/                # Modified external plugins
├── registry/                        # Auto-generated indices
├── scripts/                         # Validation tools
└── templates/basic/                 # Plugin template
```

## Validation Error Reference

| Error | Fix |
|-------|-----|
| Missing manifest | Create `.claude-plugin/plugin.json` |
| Invalid JSON | Fix JSON syntax errors |
| Missing name | Add `"name": "plugin-name"` |
| Invalid name format | Use lowercase, alphanumeric, hyphens only |
| Missing version | Add `"version": "1.0.0"` |
| Invalid version | Use semver format (x.y.z) |
| Missing description | Add description (10-500 chars) |
| No components | Add at least one skill, command, agent, or hook |
