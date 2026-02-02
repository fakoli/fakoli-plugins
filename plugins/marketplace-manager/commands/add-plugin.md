---
name: add-plugin
description: Add a new plugin to the fakoli-plugins marketplace from template
arguments:
  - name: plugin-name
    description: Name of the plugin to create (lowercase, alphanumeric, hyphens only)
    required: true
---

# Add Plugin Command

Create a new plugin in the fakoli-plugins marketplace.

## Process

1. Validate the plugin name format (lowercase, alphanumeric, hyphens only)
2. Check that a plugin with this name doesn't already exist
3. Copy the template from `templates/basic/` to `plugins/<plugin-name>/`
4. Update the plugin manifest with the new name
5. Prompt user to customize the plugin metadata

## Execution

Run the add_plugin.sh script:

```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/add_plugin.sh <plugin-name>
```

## After Creation

Guide the user to:

1. Edit `.claude-plugin/plugin.json`:
   - Update `description` with a clear explanation (10-500 chars)
   - Set `author.name` and `author.email`
   - Choose appropriate `extended.category`: productivity, code-quality, devops, integrations, or utilities
   - Add relevant `extended.tags`

2. Add plugin components (at least one required):
   - Skills: Create `skills/<skill-name>/SKILL.md`
   - Commands: Create `commands/<command-name>.md`
   - Agents: Create `agents/<agent-name>.json`
   - Hooks: Create `hooks/<hook-name>.json`

3. Update documentation:
   - Edit `README.md` with usage instructions
   - Update `CHANGELOG.md` with initial release notes

4. Validate the plugin:
   ```bash
   ./scripts/validate.sh plugins/<plugin-name>
   ```

5. Regenerate the registry:
   ```bash
   ./scripts/generate-index.sh
   ```
