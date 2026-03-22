# Marketplace Manager

Manage the fakoli-plugins marketplace from inside Claude Code. Scaffold new plugins, validate manifests, remove stale entries, regenerate the registry index, and install GitHub Actions workflows — all without leaving your terminal session.

## Installation

This plugin is bundled with the fakoli-plugins marketplace. It is available automatically once you add the marketplace:

```
/plugin marketplace add fakoli/fakoli-plugins
/plugin install marketplace-manager
```

## Features

- **Plugin scaffolding** — create a fully-structured plugin directory from the `templates/basic` starter in one command
- **Plugin removal** — safely remove a plugin and all its files, with optional `--force` to skip confirmation
- **Manifest validation** — run the JSON Schema validator against any plugin or the entire marketplace
- **Registry regeneration** — rebuild `registry/index.json` from the current set of installed plugins
- **Workflow installation** — copy the standard GitHub Actions CI suite into any repository
- **Marketplace status** — get a live summary of installed plugins, validation state, and registry freshness

## Commands

| Command | Description |
|---------|-------------|
| `/add-plugin <name>` | Scaffold a new plugin from `templates/basic` |
| `/remove-plugin <name>` | Remove a plugin from the marketplace |
| `/install-workflows [target-dir]` | Install GitHub Actions validation workflows |

## Usage

### Scaffold a New Plugin

```
/add-plugin my-new-plugin
```

Creates `plugins/my-new-plugin/` with the full directory structure, a prefilled `plugin.json` manifest, a `README.md`, and a starter skill.

You can also invoke the underlying script directly:

```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/add_plugin.sh my-new-plugin
```

### Remove a Plugin

```
/remove-plugin old-plugin
```

Prompts for confirmation before deleting. To skip the prompt:

```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/remove_plugin.sh old-plugin --force
```

### Install GitHub Actions Workflows

```
/install-workflows
```

Copies three workflow files into `.github/workflows/` of the current directory:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `validate.yml` | push, pull_request | Validates all plugin manifests against `schemas/plugin.schema.json` |
| `update-index.yml` | push to main | Regenerates `registry/index.json` and auto-commits |
| `pr-check.yml` | pull_request | Posts a registry diff as a PR comment |

Install into a specific directory:

```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/install_workflows.sh /path/to/repo
```

### Check Marketplace Status

```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/marketplace_status.sh
```

Reports: total plugin count, which plugins pass/fail validation, and whether the registry index is up to date.

### Validate Plugins

Validate all plugins:

```bash
./scripts/validate.sh
```

Validate a single plugin:

```bash
./scripts/validate.sh plugins/my-new-plugin
```

### Regenerate the Registry Index

```bash
./scripts/generate-index.sh
```

Rebuilds `registry/index.json` from all currently installed plugins. Run this after adding or removing plugins if the CI workflow hasn't triggered yet.

## Requirements

| Dependency | Why |
|------------|-----|
| bash | All scripts are bash |
| jq | JSON processing for manifest validation and index generation |

## License

MIT

## Author

Sekou Doumbouya ([@fakoli](https://github.com/fakoli))
