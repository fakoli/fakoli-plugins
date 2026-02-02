---
name: remove-plugin
description: Remove a plugin from the fakoli-plugins marketplace
arguments:
  - name: plugin-name
    description: Name of the plugin to remove
    required: true
  - name: force
    description: Skip confirmation prompt
    required: false
---

# Remove Plugin Command

Remove a plugin from the fakoli-plugins marketplace.

## Process

1. Verify the plugin exists in `plugins/` or `external_plugins/`
2. Confirm removal with the user (unless --force is specified)
3. Remove the plugin directory
4. Remove the plugin entry from marketplace.json if present
5. Regenerate the registry index

## Execution

Run the remove_plugin.sh script:

```bash
# With confirmation prompt
./plugins/marketplace-manager/skills/marketplace-manager/scripts/remove_plugin.sh <plugin-name>

# Skip confirmation
./plugins/marketplace-manager/skills/marketplace-manager/scripts/remove_plugin.sh <plugin-name> --force
```

## After Removal

Regenerate the registry index:

```bash
./scripts/generate-index.sh
```

## Warning

This action is permanent. The plugin directory and all its contents will be deleted. Make sure to backup any important data before removing a plugin.
