# Create Your Own Plugin Marketplace

This guide walks you through creating your own Claude Code plugin marketplace using this repository as a template.

## Overview

A plugin marketplace is a GitHub repository that:
- Contains plugins in a `plugins/` directory
- Has a `registry/index.json` listing available plugins
- Can be added to Claude Code with `/plugin marketplace add <url>`

## Step 1: Fork the Repository

1. Go to [github.com/fakoli/fakoli-plugins](https://github.com/fakoli/fakoli-plugins)
2. Click **Fork** in the top-right
3. Choose your account/organization
4. Clone your fork:

```bash
git clone https://github.com/YOUR-USERNAME/fakoli-plugins.git
cd fakoli-plugins
```

## Step 2: Customize marketplace.json

Edit `.claude-plugin/marketplace.json` with your marketplace info:

```json
{
  "name": "your-marketplace",
  "displayName": "Your Marketplace Name",
  "description": "A curated collection of plugins for your use case",
  "author": {
    "name": "Your Name",
    "url": "https://github.com/your-username"
  },
  "homepage": "https://github.com/your-username/your-marketplace"
}
```

## Step 3: Remove Example Plugins

Remove the existing plugins (or keep ones you want):

```bash
# Remove all existing plugins
rm -rf plugins/*

# Or keep specific ones
rm -rf plugins/marketplace-manager  # Example
```

## Step 4: Add Your Plugins

### Option A: Create New Plugins

```bash
# Copy the template
cp -r templates/basic plugins/my-plugin

# Edit the manifest
# plugins/my-plugin/.claude-plugin/plugin.json
```

### Option B: Copy Existing Plugins

Copy plugins from other sources into `plugins/`:

```bash
# Each plugin needs a .claude-plugin/plugin.json manifest
plugins/
├── my-plugin/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── skills/
│   └── README.md
```

## Step 5: Validate Your Plugins

```bash
# Validate all plugins
./scripts/validate.sh

# Validate specific plugin
./scripts/validate.sh plugins/my-plugin
```

## Step 6: Generate the Registry Index

```bash
./scripts/generate-index.sh
```

This creates `registry/index.json` with all your plugins listed.

## Step 7: Set Up GitHub Actions

The repository includes workflows that automatically:
- Validate plugins on PRs
- Regenerate `registry/index.json` on merge to main

Check `.github/workflows/` and ensure they're enabled in your fork:

1. Go to your repository Settings > Actions > General
2. Enable "Allow all actions and reusable workflows"

## Step 8: Update Documentation

Update these files for your marketplace:

- `README.md` - Your marketplace description
- `docs/CONTRIBUTING.md` - How to contribute to your marketplace
- `assets/fakoli-banner.png` - Your marketplace banner (optional)

## Step 9: Publish Your Marketplace

1. Push to GitHub:
   ```bash
   git add .
   git commit -m "Initialize marketplace"
   git push origin main
   ```

2. Users can now add your marketplace:
   ```bash
   /plugin marketplace add https://github.com/YOUR-USERNAME/your-marketplace
   ```

## Directory Structure

Your marketplace should have:

```
your-marketplace/
├── .claude-plugin/
│   ├── plugin.json         # Marketplace manifest
│   └── marketplace.json    # Marketplace metadata
├── plugins/                # Your plugins
│   └── plugin-name/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── skills/
│       └── README.md
├── registry/
│   └── index.json          # Auto-generated plugin index
├── scripts/
│   ├── validate.sh         # Plugin validation
│   └── generate-index.sh   # Index generation
├── templates/
│   └── basic/              # Plugin template
└── README.md
```

## Customization Options

### Categories

Edit `registry/categories.json` to define your categories:

```json
[
  {"id": "productivity", "name": "Productivity", "description": "..."},
  {"id": "devops", "name": "DevOps", "description": "..."}
]
```

### Validation Rules

Edit `scripts/validate.sh` to add custom validation rules.

### Plugin Template

Edit `templates/basic/` to customize the starting template for new plugins.

## Maintenance

### Adding New Plugins

1. Create plugin in `plugins/`
2. Run `./scripts/validate.sh plugins/new-plugin`
3. Commit and push
4. GitHub Actions regenerates the index

### Updating Plugins

1. Edit plugin files
2. Update version in `plugin.json`
3. Update CHANGELOG.md
4. Commit and push

### Removing Plugins

1. Delete the plugin directory
2. Commit and push
3. GitHub Actions regenerates the index

## Troubleshooting

### Validation Fails

- Check JSON syntax in `plugin.json`
- Ensure `name` field exists and uses kebab-case
- Verify at least one component (skills/, commands/, agents/, or hooks/)

### Index Not Updating

- Check GitHub Actions are enabled
- Verify `.github/workflows/update-index.yml` exists
- Manually run: `./scripts/generate-index.sh`

### Plugins Not Appearing

- Ensure `registry/index.json` includes the plugin
- Verify plugin structure matches requirements
- Check for validation errors

## Examples

See these marketplaces for reference:
- [Fakoli Plugins](https://github.com/fakoli/fakoli-plugins) - This repository

---

Questions? Open an issue in the original repository.
