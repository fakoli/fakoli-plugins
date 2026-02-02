#!/usr/bin/env bash
#
# add_plugin.sh - Add a new plugin to the marketplace from template
#
# Usage: add_plugin.sh <plugin-name>
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate up from skills/marketplace-manager/scripts to plugin root, then to marketplace root
MARKETPLACE_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

if [[ $# -lt 1 ]]; then
    echo "Usage: add_plugin.sh <plugin-name>"
    echo ""
    echo "Creates a new plugin from the basic template."
    echo ""
    echo "Example:"
    echo "  add_plugin.sh my-new-plugin"
    exit 1
fi

PLUGIN_NAME="$1"
PLUGIN_DIR="$MARKETPLACE_ROOT/plugins/$PLUGIN_NAME"
TEMPLATE_DIR="$MARKETPLACE_ROOT/templates/basic"

# Validate plugin name
if [[ ! "$PLUGIN_NAME" =~ ^[a-z0-9-]+$ ]]; then
    echo -e "${RED}Error:${NC} Plugin name must be lowercase, alphanumeric, and hyphens only"
    exit 1
fi

# Check if plugin already exists
if [[ -d "$PLUGIN_DIR" ]]; then
    echo -e "${RED}Error:${NC} Plugin '$PLUGIN_NAME' already exists at $PLUGIN_DIR"
    exit 1
fi

# Check if template exists
if [[ ! -d "$TEMPLATE_DIR" ]]; then
    echo -e "${RED}Error:${NC} Template not found at $TEMPLATE_DIR"
    exit 1
fi

# Copy template
echo "Creating plugin from template..."
cp -r "$TEMPLATE_DIR" "$PLUGIN_DIR"

# Update plugin.json with new name
if [[ -f "$PLUGIN_DIR/.claude-plugin/plugin.json" ]]; then
    # Use temporary file for compatibility
    TMP_FILE=$(mktemp)
    jq --arg name "$PLUGIN_NAME" '.name = $name' "$PLUGIN_DIR/.claude-plugin/plugin.json" > "$TMP_FILE"
    mv "$TMP_FILE" "$PLUGIN_DIR/.claude-plugin/plugin.json"
fi

# Add to marketplace.json
MARKETPLACE_JSON="$MARKETPLACE_ROOT/.claude-plugin/marketplace.json"
if [[ -f "$MARKETPLACE_JSON" ]]; then
    TMP_FILE=$(mktemp)
    if jq --arg name "$PLUGIN_NAME" \
          --arg path "plugins/$PLUGIN_NAME" \
          '.plugins += [{"name": $name, "version": "1.0.0", "description": "New plugin - update description", "path": $path}]' \
          "$MARKETPLACE_JSON" > "$TMP_FILE" 2>/dev/null; then
        mv "$TMP_FILE" "$MARKETPLACE_JSON"
        echo "Added to marketplace.json"
    else
        rm -f "$TMP_FILE"
    fi
fi

echo -e "${GREEN}Success!${NC} Plugin '$PLUGIN_NAME' created at $PLUGIN_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit .claude-plugin/plugin.json with your plugin details"
echo "  2. Add skills, commands, agents, or hooks"
echo "  3. Update README.md and CHANGELOG.md"
echo "  4. Run: ./scripts/validate.sh plugins/$PLUGIN_NAME"
echo "  5. Run: ./scripts/generate-index.sh"
