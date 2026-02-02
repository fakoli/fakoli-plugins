#!/usr/bin/env bash
#
# remove_plugin.sh - Remove a plugin from the marketplace
#
# Usage: remove_plugin.sh <plugin-name> [--force]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

FORCE=false

if [[ $# -lt 1 ]]; then
    echo "Usage: remove_plugin.sh <plugin-name> [--force]"
    echo ""
    echo "Removes a plugin from the marketplace."
    echo ""
    echo "Options:"
    echo "  --force    Skip confirmation prompt"
    echo ""
    echo "Example:"
    echo "  remove_plugin.sh old-plugin"
    echo "  remove_plugin.sh old-plugin --force"
    exit 1
fi

PLUGIN_NAME="$1"

if [[ "${2:-}" == "--force" ]]; then
    FORCE=true
fi

PLUGIN_DIR="$MARKETPLACE_ROOT/plugins/$PLUGIN_NAME"
EXTERNAL_PLUGIN_DIR="$MARKETPLACE_ROOT/external_plugins/$PLUGIN_NAME"

# Check if plugin exists
if [[ -d "$PLUGIN_DIR" ]]; then
    TARGET_DIR="$PLUGIN_DIR"
    LOCATION="plugins"
elif [[ -d "$EXTERNAL_PLUGIN_DIR" ]]; then
    TARGET_DIR="$EXTERNAL_PLUGIN_DIR"
    LOCATION="external_plugins"
else
    echo -e "${RED}Error:${NC} Plugin '$PLUGIN_NAME' not found"
    echo "Searched in:"
    echo "  - $PLUGIN_DIR"
    echo "  - $EXTERNAL_PLUGIN_DIR"
    exit 1
fi

# Confirm removal
if [[ "$FORCE" != true ]]; then
    echo -e "${YELLOW}Warning:${NC} This will permanently delete '$PLUGIN_NAME' from $LOCATION/"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Remove plugin directory
echo "Removing plugin directory..."
rm -rf "$TARGET_DIR"

# Remove from marketplace.json if present
MARKETPLACE_JSON="$MARKETPLACE_ROOT/.claude-plugin/marketplace.json"
if [[ -f "$MARKETPLACE_JSON" ]]; then
    TMP_FILE=$(mktemp)
    if jq --arg name "$PLUGIN_NAME" '.plugins = [.plugins[] | select(.name != $name)]' "$MARKETPLACE_JSON" > "$TMP_FILE" 2>/dev/null; then
        mv "$TMP_FILE" "$MARKETPLACE_JSON"
        echo "Removed from marketplace.json"
    else
        rm -f "$TMP_FILE"
    fi
fi

echo -e "${GREEN}Success!${NC} Plugin '$PLUGIN_NAME' has been removed"
echo ""
echo "Next step:"
echo "  Run: ./scripts/generate-index.sh"
