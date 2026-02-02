#!/usr/bin/env bash
#
# remove_plugin.sh - Remove a plugin from the marketplace
#
# Usage: remove_plugin.sh <plugin-name> [--force] [--regenerate]
#
# Reference: https://code.claude.com/docs/en/plugins-reference
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

FORCE=false
REGENERATE=false

show_usage() {
    echo "Usage: remove_plugin.sh <plugin-name> [--force] [--regenerate]"
    echo ""
    echo "Removes a plugin from the marketplace."
    echo ""
    echo "Options:"
    echo "  --force       Skip confirmation prompt"
    echo "  --regenerate  Run generate-index.sh after removal"
    echo ""
    echo "Example:"
    echo "  remove_plugin.sh old-plugin"
    echo "  remove_plugin.sh old-plugin --force"
    echo "  remove_plugin.sh old-plugin --force --regenerate"
    exit 1
}

if [[ $# -lt 1 ]]; then
    show_usage
fi

PLUGIN_NAME="$1"
shift

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --regenerate)
            REGENERATE=true
            shift
            ;;
        *)
            echo -e "${RED}Error:${NC} Unknown option: $1"
            show_usage
            ;;
    esac
done

PLUGIN_DIR="$MARKETPLACE_ROOT/plugins/$PLUGIN_NAME"
EXTERNAL_PLUGIN_DIR="$MARKETPLACE_ROOT/external_plugins/$PLUGIN_NAME"
MARKETPLACE_JSON="$MARKETPLACE_ROOT/.claude-plugin/marketplace.json"

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
if [[ -f "$MARKETPLACE_JSON" ]]; then
    # Check if plugin exists in marketplace.json
    EXISTING=$(jq -r --arg name "$PLUGIN_NAME" '.plugins[] | select(.name == $name) | .name' "$MARKETPLACE_JSON" 2>/dev/null || true)
    if [[ -n "$EXISTING" ]]; then
        TMP_FILE=$(mktemp)
        if jq --arg name "$PLUGIN_NAME" '.plugins = [.plugins[] | select(.name != $name)]' "$MARKETPLACE_JSON" > "$TMP_FILE" 2>/dev/null; then
            mv "$TMP_FILE" "$MARKETPLACE_JSON"
            echo "Removed from marketplace.json"
        else
            rm -f "$TMP_FILE"
            echo -e "${YELLOW}Warning:${NC} Could not remove from marketplace.json"
        fi
    fi
fi

echo -e "${GREEN}Success!${NC} Plugin '$PLUGIN_NAME' has been removed"

# Regenerate index if requested
if [[ "$REGENERATE" == true ]]; then
    echo ""
    echo "Regenerating registry index..."
    if [[ -f "$MARKETPLACE_ROOT/scripts/generate-index.sh" ]]; then
        "$MARKETPLACE_ROOT/scripts/generate-index.sh"
    else
        echo -e "${YELLOW}Warning:${NC} generate-index.sh not found"
    fi
else
    echo ""
    echo "Next step:"
    echo "  Run: ./scripts/generate-index.sh"
fi
