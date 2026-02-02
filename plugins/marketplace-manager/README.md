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

## Usage

### Skill Invocation

```
/marketplace-manager
```

### Available Commands

**Add a plugin:**
```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/add_plugin.sh <plugin-name>
```

**Remove a plugin:**
```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/remove_plugin.sh <plugin-name>
```

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
