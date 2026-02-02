---
name: install-workflows
description: Install GitHub Actions workflows for plugin validation and registry updates
arguments:
  - name: target-dir
    description: Target directory to install workflows (defaults to current directory)
    required: false
---

# Install Workflows Command

Install GitHub Actions workflows for automating plugin validation and registry index updates in a plugin marketplace repository.

## Workflows Installed

### 1. `validate.yml`
- **Triggers**: Push to main, PRs to main
- **Purpose**: Validates all plugin manifests
- **Checks**: JSON syntax, required fields, semver format, README presence

### 2. `update-index.yml`
- **Triggers**: Push to main (plugin changes), manual trigger
- **Purpose**: Regenerates registry indices
- **Actions**: Validates plugins, generates index.json/categories.json/tags.json, auto-commits

### 3. `pr-check.yml`
- **Triggers**: PRs to main (plugin changes)
- **Purpose**: Preview validation and index changes
- **Actions**: Validates plugins, shows registry preview

## Execution

Run the install script:

```bash
./plugins/marketplace-manager/skills/marketplace-manager/scripts/install_workflows.sh [target-dir]
```

If no target directory is specified, workflows are installed in the current directory.

## Prerequisites

The target repository must have:
- `scripts/validate.sh` - Plugin validation script
- `scripts/generate-index.sh` - Registry generation script
- `plugins/` or `external_plugins/` directories

## After Installation

1. Commit the new workflow files:
   ```bash
   git add .github/workflows/
   git commit -m "Add GitHub Actions workflows for plugin validation"
   ```

2. Push to trigger the workflows:
   ```bash
   git push
   ```

3. Verify workflows run successfully in the GitHub Actions tab
