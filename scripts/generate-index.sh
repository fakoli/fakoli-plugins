#!/usr/bin/env bash
#
# generate-index.sh - Generates registry index from all plugin manifests
#
# Usage: ./scripts/generate-index.sh
#
# Outputs:
#   - registry/index.json      - Full plugin index
#   - registry/categories.json - Plugins grouped by category
#   - registry/tags.json       - Tag cloud with counts
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
REGISTRY_DIR="$ROOT_DIR/registry"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "INFO: $1" >&2
}

log_success() {
    echo -e "${GREEN}OK:${NC} $1"
}

log_skip() {
    echo -e "SKIP: $1 (no changes)"
}

# Strip timestamp fields for comparison (generatedAt, indexedAt)
strip_timestamps() {
    jq 'walk(if type == "object" then del(.generatedAt, .indexedAt) else . end)'
}

# Write file only if content (excluding timestamps) has changed
write_if_changed() {
    local file="$1"
    local new_content="$2"
    local label="$3"

    if [[ -f "$file" ]]; then
        local old_stripped new_stripped
        old_stripped=$(cat "$file" | strip_timestamps)
        new_stripped=$(echo "$new_content" | strip_timestamps)

        if [[ "$old_stripped" == "$new_stripped" ]]; then
            log_skip "$label"
            return 0
        fi
    fi

    echo "$new_content" > "$file"
    log_success "$label"
}

# Check dependencies
check_dependencies() {
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed."
        echo "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
        exit 1
    fi
}

# Collect all plugin manifests
collect_plugins() {
    local plugins_json='[]'
    local plugin_dirs=()

    # Find plugins in plugins/
    if [[ -d "$ROOT_DIR/plugins" ]]; then
        while IFS= read -r -d '' dir; do
            if [[ -f "$dir/.claude-plugin/plugin.json" ]]; then
                plugin_dirs+=("$dir")
            fi
        done < <(find "$ROOT_DIR/plugins" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    fi

    # Find plugins in external_plugins/
    if [[ -d "$ROOT_DIR/external_plugins" ]]; then
        while IFS= read -r -d '' dir; do
            if [[ -f "$dir/.claude-plugin/plugin.json" ]]; then
                plugin_dirs+=("$dir")
            fi
        done < <(find "$ROOT_DIR/external_plugins" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    fi

    if [[ ${#plugin_dirs[@]} -gt 0 ]]; then
    for plugin_dir in "${plugin_dirs[@]}"; do
        local manifest_file="$plugin_dir/.claude-plugin/plugin.json"
        local plugin_name
        plugin_name=$(basename "$plugin_dir")
        local relative_path="${plugin_dir#$ROOT_DIR/}"

        log_info "Processing: $plugin_name"

        # Read manifest and add metadata
        local plugin_entry
        plugin_entry=$(jq --arg path "$relative_path" \
            --arg indexed_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
            '. + {
                "path": $path,
                "indexedAt": $indexed_at
            }' "$manifest_file")

        plugins_json=$(echo "$plugins_json" | jq --argjson plugin "$plugin_entry" '. + [$plugin]')
    done
    fi

    echo "$plugins_json"
}

# Generate main index
generate_index() {
    local plugins="$1"
    local plugin_count
    plugin_count=$(echo "$plugins" | jq 'length')

    local index
    index=$(jq -n \
        --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
        --arg version "1.0.0" \
        --argjson count "$plugin_count" \
        --argjson plugins "$plugins" \
        '{
            "$schema": "../schemas/index.schema.json",
            "version": $version,
            "generatedAt": $generated_at,
            "pluginCount": $count,
            "plugins": $plugins
        }')

    write_if_changed "$REGISTRY_DIR/index.json" "$index" "Generated registry/index.json ($plugin_count plugins)"
}

# Generate categories index
generate_categories() {
    local plugins="$1"

    local categories
    categories=$(echo "$plugins" | jq '
        group_by(.extended.category // "uncategorized")
        | map({
            category: (.[0].extended.category // "uncategorized"),
            count: length,
            plugins: map({
                name: .name,
                version: .version,
                description: .description,
                path: .path
            })
        })
        | sort_by(.category)
    ')

    local output
    output=$(jq -n \
        --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
        --argjson categories "$categories" \
        '{
            "generatedAt": $generated_at,
            "categories": $categories
        }')

    write_if_changed "$REGISTRY_DIR/categories.json" "$output" "Generated registry/categories.json"
}

# Generate tags index
generate_tags() {
    local plugins="$1"

    local tags
    tags=$(echo "$plugins" | jq '
        [.[].extended.tags // [] | .[]]
        | group_by(.)
        | map({
            tag: .[0],
            count: length
        })
        | sort_by(-.count)
    ')

    local output
    output=$(jq -n \
        --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
        --argjson tags "$tags" \
        '{
            "generatedAt": $generated_at,
            "totalTags": ($tags | length),
            "tags": $tags
        }')

    write_if_changed "$REGISTRY_DIR/tags.json" "$output" "Generated registry/tags.json"
}

# Update marketplace.json with indexed plugins
update_marketplace() {
    local plugins="$1"
    local marketplace_file="$ROOT_DIR/.claude-plugin/marketplace.json"

    if [[ -f "$marketplace_file" ]]; then
        local marketplace_plugins
        marketplace_plugins=$(echo "$plugins" | jq '[.[] | {
            name: .name,
            version: .version,
            description: .description,
            path: .path
        }]')

        local new_content
        new_content=$(jq --argjson plugins "$marketplace_plugins" '.plugins = $plugins' "$marketplace_file")

        # Compare plugins arrays only (marketplace.json has no timestamps)
        local old_plugins new_plugins
        old_plugins=$(jq -c '.plugins | sort_by(.name)' "$marketplace_file")
        new_plugins=$(echo "$new_content" | jq -c '.plugins | sort_by(.name)')

        if [[ "$old_plugins" == "$new_plugins" ]]; then
            log_skip "Updated .claude-plugin/marketplace.json"
            return 0
        fi

        echo "$new_content" > "$marketplace_file"
        log_success "Updated .claude-plugin/marketplace.json"
    fi
}

# Main
main() {
    check_dependencies

    echo "========================================"
    echo "  Generating Plugin Registry Index"
    echo "========================================"

    # Ensure registry directory exists
    mkdir -p "$REGISTRY_DIR"

    # Collect all plugins
    local plugins
    plugins=$(collect_plugins)

    # Generate indices
    generate_index "$plugins"
    generate_categories "$plugins"
    generate_tags "$plugins"
    update_marketplace "$plugins"

    echo ""
    echo "========================================"
    echo "  Registry generation complete!"
    echo "========================================"
}

main "$@"
