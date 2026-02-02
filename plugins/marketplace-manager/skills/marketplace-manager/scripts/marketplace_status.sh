#!/usr/bin/env bash
#
# marketplace_status.sh - Show marketplace status and statistics
#
# Usage: marketplace_status.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "========================================"
echo "  Fakoli Plugins Marketplace Status"
echo "========================================"
echo ""

# Check marketplace.json
MARKETPLACE_JSON="$MARKETPLACE_ROOT/.claude-plugin/marketplace.json"
if [[ -f "$MARKETPLACE_JSON" ]]; then
    NAME=$(jq -r '.name' "$MARKETPLACE_JSON")
    VERSION=$(jq -r '.version' "$MARKETPLACE_JSON")
    echo -e "${CYAN}Marketplace:${NC} $NAME v$VERSION"
else
    echo "Marketplace config not found"
fi

echo ""

# Count plugins
PLUGIN_COUNT=0
EXTERNAL_COUNT=0

if [[ -d "$MARKETPLACE_ROOT/plugins" ]]; then
    PLUGIN_COUNT=$(find "$MARKETPLACE_ROOT/plugins" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
fi

if [[ -d "$MARKETPLACE_ROOT/external_plugins" ]]; then
    EXTERNAL_COUNT=$(find "$MARKETPLACE_ROOT/external_plugins" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
fi

echo -e "${CYAN}Plugins:${NC}"
echo "  First-party: $PLUGIN_COUNT"
echo "  External:    $EXTERNAL_COUNT"
echo "  Total:       $((PLUGIN_COUNT + EXTERNAL_COUNT))"
echo ""

# Registry stats
INDEX_JSON="$MARKETPLACE_ROOT/registry/index.json"
if [[ -f "$INDEX_JSON" ]]; then
    INDEXED=$(jq -r '.pluginCount' "$INDEX_JSON")
    GENERATED=$(jq -r '.generatedAt' "$INDEX_JSON")
    echo -e "${CYAN}Registry:${NC}"
    echo "  Indexed plugins: $INDEXED"
    echo "  Last generated:  $GENERATED"
else
    echo -e "${CYAN}Registry:${NC} Not generated yet"
    echo "  Run: ./scripts/generate-index.sh"
fi

echo ""

# List plugins
echo -e "${CYAN}Plugin List:${NC}"
if [[ -d "$MARKETPLACE_ROOT/plugins" ]]; then
    shopt -s nullglob
    for dir in "$MARKETPLACE_ROOT/plugins"/*/; do
        if [[ -d "$dir" ]]; then
            name=$(basename "$dir")
            manifest="$dir/.claude-plugin/plugin.json"
            if [[ -f "$manifest" ]]; then
                version=$(jq -r '.version // "?"' "$manifest")
                desc=$(jq -r '.description // ""' "$manifest" | head -c 50)
                echo -e "  ${GREEN}$name${NC} v$version - $desc..."
            else
                echo "  $name (no manifest)"
            fi
        fi
    done
    shopt -u nullglob
fi

if [[ -d "$MARKETPLACE_ROOT/external_plugins" ]]; then
    shopt -s nullglob
    for dir in "$MARKETPLACE_ROOT/external_plugins"/*/; do
        if [[ -d "$dir" ]]; then
            name=$(basename "$dir")
            echo "  $name (external)"
        fi
    done
    shopt -u nullglob
fi

if [[ $PLUGIN_COUNT -eq 0 && $EXTERNAL_COUNT -eq 0 ]]; then
    echo "  No plugins found"
fi

echo ""
echo "========================================"
