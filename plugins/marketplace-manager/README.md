# Marketplace Manager

Manage the fakoli-plugins marketplace: add/remove plugins, validate manifests, and regenerate registry indices.

## Installation

This plugin is included with the fakoli-plugins marketplace.

## Features

- Add new plugins from template
- Remove plugins from the marketplace
- Validate plugin manifests
- Regenerate registry indices
- Check marketplace status
- Install GitHub Actions workflows

## Usage

### Skill

```
/marketplace-manager
```

### Commands

#### `/add-plugin <plugin-name>`

Create a new plugin from the basic template.

```bash
# Via script
./plugins/marketplace-manager/skills/marketplace-manager/scripts/add_plugin.sh my-new-plugin
```

#### `/remove-plugin <plugin-name>`

Remove a plugin from the marketplace.

```bash
# Via script
./plugins/marketplace-manager/skills/marketplace-manager/scripts/remove_plugin.sh old-plugin

# Skip confirmation
./plugins/marketplace-manager/skills/marketplace-manager/scripts/remove_plugin.sh old-plugin --force
```

#### `/install-workflows [target-dir]`

Install GitHub Actions workflows for plugin validation and registry updates.

```bash
# Install in current directory
./plugins/marketplace-manager/skills/marketplace-manager/scripts/install_workflows.sh

# Install in specific directory
./plugins/marketplace-manager/skills/marketplace-manager/scripts/install_workflows.sh /path/to/repo
```

Installs three workflows:
- `validate.yml` - Validates plugins on push/PR
- `update-index.yml` - Auto-updates registry index
- `pr-check.yml` - Previews changes on PRs

### Other Scripts

**Check status:**
```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/marketplace_status.sh
```

**Validate plugins:**
```bash
./scripts/validate.sh
./scripts/validate.sh plugins/<plugin-name>
```

**Regenerate indices:**
```bash
./scripts/generate-index.sh
```

## Requirements

- bash
- jq (JSON processor)

## License

MIT
