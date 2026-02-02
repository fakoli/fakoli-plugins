#!/usr/bin/env bash
#
# add_plugin.sh - Add a new plugin to the marketplace from template
#
# Usage: add_plugin.sh <plugin-name> [--no-validate]
#
# Reference: https://code.claude.com/docs/en/plugins-reference
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate up from skills/marketplace-manager/scripts to plugin root, then to marketplace root
MARKETPLACE_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

NO_VALIDATE=false

show_usage() {
    echo "Usage: add_plugin.sh <plugin-name> [--no-validate]"
    echo ""
    echo "Creates a new plugin from the basic template."
    echo ""
    echo "Options:"
    echo "  --no-validate    Skip running validation after creating plugin"
    echo ""
    echo "Example:"
    echo "  add_plugin.sh my-new-plugin"
    exit 1
}

if [[ $# -lt 1 ]]; then
    show_usage
fi

PLUGIN_NAME="$1"

# Parse options
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-validate)
            NO_VALIDATE=true
            shift
            ;;
        *)
            echo -e "${RED}Error:${NC} Unknown option: $1"
            show_usage
            ;;
    esac
done

PLUGIN_DIR="$MARKETPLACE_ROOT/plugins/$PLUGIN_NAME"
TEMPLATE_DIR="$MARKETPLACE_ROOT/templates/basic"
MARKETPLACE_JSON="$MARKETPLACE_ROOT/.claude-plugin/marketplace.json"

# Validate plugin name (kebab-case, no spaces)
if [[ ! "$PLUGIN_NAME" =~ ^[a-z0-9-]+$ ]]; then
    echo -e "${RED}Error:${NC} Plugin name must be kebab-case (lowercase, alphanumeric, hyphens only)"
    exit 1
fi

# Check if plugin already exists in directory
if [[ -d "$PLUGIN_DIR" ]]; then
    echo -e "${RED}Error:${NC} Plugin '$PLUGIN_NAME' already exists at $PLUGIN_DIR"
    exit 1
fi

# Check if plugin already exists in marketplace.json
if [[ -f "$MARKETPLACE_JSON" ]]; then
    EXISTING=$(jq -r --arg name "$PLUGIN_NAME" '.plugins[] | select(.name == $name) | .name' "$MARKETPLACE_JSON" 2>/dev/null || true)
    if [[ -n "$EXISTING" ]]; then
        echo -e "${RED}Error:${NC} Plugin '$PLUGIN_NAME' already exists in marketplace.json"
        exit 1
    fi
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
    TMP_FILE=$(mktemp)
    jq --arg name "$PLUGIN_NAME" '.name = $name' "$PLUGIN_DIR/.claude-plugin/plugin.json" > "$TMP_FILE"
    mv "$TMP_FILE" "$PLUGIN_DIR/.claude-plugin/plugin.json"
    echo "Updated plugin.json with name: $PLUGIN_NAME"
fi

# Add to marketplace.json with proper schema
# Reference: https://code.claude.com/docs/en/plugins-reference
if [[ -f "$MARKETPLACE_JSON" ]]; then
    TMP_FILE=$(mktemp)
    if jq --arg name "$PLUGIN_NAME" \
          --arg source "./plugins/$PLUGIN_NAME" \
          '.plugins += [{"name": $name, "source": $source}]' \
          "$MARKETPLACE_JSON" > "$TMP_FILE" 2>/dev/null; then
        mv "$TMP_FILE" "$MARKETPLACE_JSON"
        echo "Added to marketplace.json with source: ./plugins/$PLUGIN_NAME"
    else
        rm -f "$TMP_FILE"
        echo -e "${YELLOW}Warning:${NC} Could not add to marketplace.json"
    fi
fi

echo ""
echo -e "${GREEN}Success!${NC} Plugin '$PLUGIN_NAME' created at $PLUGIN_DIR"

# Run validation unless --no-validate was specified
if [[ "$NO_VALIDATE" != true ]]; then
    echo ""
    echo "Running validation..."
    if [[ -f "$MARKETPLACE_ROOT/scripts/validate.sh" ]]; then
        "$MARKETPLACE_ROOT/scripts/validate.sh" "$PLUGIN_DIR" || true
    fi
fi

echo ""
echo "Next steps:"
echo "  1. Edit .claude-plugin/plugin.json with your plugin details"
echo "     (add version, description, author, repository, license, keywords)"
echo "  2. Add skills/, commands/, agents/, or hooks/ directories"
echo "  3. Update README.md and CHANGELOG.md"
echo "  4. Run: ./scripts/validate.sh plugins/$PLUGIN_NAME"
echo "  5. Run: ./scripts/generate-index.sh"
