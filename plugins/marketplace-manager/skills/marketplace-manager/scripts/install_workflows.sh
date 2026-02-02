#!/usr/bin/env bash
#
# install_workflows.sh - Install GitHub Actions workflows for plugin marketplace
#
# Usage: install_workflows.sh [target-dir]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate to marketplace root
MARKETPLACE_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
WORKFLOWS_SOURCE="$MARKETPLACE_ROOT/.github/workflows"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Target directory (default to current directory)
TARGET_DIR="${1:-.}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
TARGET_WORKFLOWS="$TARGET_DIR/.github/workflows"

echo "========================================"
echo "  Install GitHub Actions Workflows"
echo "========================================"
echo ""
echo "Source: $WORKFLOWS_SOURCE"
echo "Target: $TARGET_WORKFLOWS"
echo ""

# Check source workflows exist
if [[ ! -d "$WORKFLOWS_SOURCE" ]]; then
    echo -e "${RED}Error:${NC} Source workflows not found at $WORKFLOWS_SOURCE"
    exit 1
fi

# Check if target has required scripts
if [[ ! -f "$TARGET_DIR/scripts/validate.sh" ]]; then
    echo -e "${YELLOW}Warning:${NC} scripts/validate.sh not found in target directory"
    echo "The workflows require this script to function properly."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

if [[ ! -f "$TARGET_DIR/scripts/generate-index.sh" ]]; then
    echo -e "${YELLOW}Warning:${NC} scripts/generate-index.sh not found in target directory"
    echo "The update-index workflow requires this script."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Create target workflows directory
mkdir -p "$TARGET_WORKFLOWS"

# Copy workflow files
COPIED=0
for workflow in "$WORKFLOWS_SOURCE"/*.yml; do
    if [[ -f "$workflow" ]]; then
        filename=$(basename "$workflow")

        # Check if file already exists
        if [[ -f "$TARGET_WORKFLOWS/$filename" ]]; then
            echo -e "${YELLOW}Exists:${NC} $filename"
            read -p "  Overwrite? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "  Skipped."
                continue
            fi
        fi

        cp "$workflow" "$TARGET_WORKFLOWS/$filename"
        echo -e "${GREEN}Installed:${NC} $filename"
        ((COPIED++)) || true
    fi
done

echo ""
if [[ $COPIED -gt 0 ]]; then
    echo -e "${GREEN}Success!${NC} Installed $COPIED workflow(s) to $TARGET_WORKFLOWS"
    echo ""
    echo "Next steps:"
    echo "  1. git add .github/workflows/"
    echo "  2. git commit -m \"Add GitHub Actions workflows for plugin validation\""
    echo "  3. git push"
else
    echo "No workflows were installed."
fi

echo ""
echo "========================================"
