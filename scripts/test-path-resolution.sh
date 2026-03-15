#!/usr/bin/env bash
#
# test-path-resolution.sh - Deep path analysis and hook safety scanner for plugins
#
# Usage: ./scripts/test-path-resolution.sh [plugin-path]
#   If no path provided, scans all plugins in plugins/ and external_plugins/
#

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
ERRORS=0
WARNINGS=0
PASSED=0

log_error() {
    echo -e "  ${RED}ERROR:${NC} $1" >&2
    ((ERRORS++)) || true
}

log_warn() {
    echo -e "  ${YELLOW}WARN:${NC} $1" >&2
    ((WARNINGS++)) || true
}

log_ok() {
    echo -e "  ${GREEN}OK:${NC} $1"
    ((PASSED++)) || true
}

log_info() {
    echo -e "  ${BLUE}INFO:${NC} $1"
}

# Check dependencies
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required but not installed.${NC}"
    echo "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

# Scan component paths in a plugin manifest
scan_component_paths() {
    local plugin_dir="$1"
    local plugin_name="$2"
    local manifest_file="$plugin_dir/.claude-plugin/plugin.json"
    local claude_plugin_dir="$plugin_dir/.claude-plugin"

    echo -e "\n${BLUE}--- Path Resolution ---${NC}"

    # Component path fields to check
    local fields=("commands" "agents" "skills" "hooks" "mcpServers" "outputStyles" "lspServers")

    for field in "${fields[@]}"; do
        local field_type
        field_type=$(jq -r ".$field | type" "$manifest_file" 2>/dev/null)

        [[ "$field_type" == "null" ]] && continue

        # Auto-discovered directories warning
        if [[ "$field" == "commands" || "$field" == "agents" || "$field" == "skills" ]]; then
            log_warn "'$field' is auto-discovered — declaring in manifest is unnecessary"
        fi

        local paths=()
        if [[ "$field_type" == "string" ]]; then
            paths+=("$(jq -r ".$field" "$manifest_file")")
        elif [[ "$field_type" == "array" ]]; then
            while IFS= read -r p; do
                paths+=("$p")
            done < <(jq -r ".$field[]" "$manifest_file" 2>/dev/null)
        elif [[ "$field_type" == "object" ]]; then
            log_info "'$field' is inline object (no path to resolve)"
            continue
        fi

        for path in "${paths[@]}"; do
            [[ -z "$path" || "$path" == "null" ]] && continue

            # Resolve relative to .claude-plugin/
            local resolved="$claude_plugin_dir/$path"

            if [[ -e "$resolved" ]]; then
                log_ok "'$field' path '$path' resolves to existing target"
            else
                # Check if it exists at plugin root instead
                local at_root="$plugin_dir/$path"
                # Also check without ./ prefix
                local stripped="${path#./}"
                local at_root_stripped="$plugin_dir/$stripped"

                if [[ -e "$at_root" || -e "$at_root_stripped" ]]; then
                    log_error "'$field' path '$path' not found relative to .claude-plugin/ — but exists at plugin root. Use '../$stripped' instead"
                else
                    log_error "'$field' path '$path' not found (resolved: $resolved)"
                fi
            fi
        done
    done

    # Check .mcp.json if present
    if [[ -f "$plugin_dir/.mcp.json" ]]; then
        if jq empty "$plugin_dir/.mcp.json" 2>/dev/null; then
            log_ok ".mcp.json has valid JSON syntax"
        else
            log_error ".mcp.json has invalid JSON syntax"
        fi
    fi
}

# Deep hook safety scan
scan_hook_safety() {
    local plugin_dir="$1"
    local plugin_name="$2"

    # Find hooks.json
    local hooks_file=""
    if [[ -f "$plugin_dir/hooks/hooks.json" ]]; then
        hooks_file="$plugin_dir/hooks/hooks.json"
    else
        local manifest_file="$plugin_dir/.claude-plugin/plugin.json"
        local hooks_type
        hooks_type=$(jq -r '.hooks | type' "$manifest_file" 2>/dev/null)
        if [[ "$hooks_type" == "string" ]]; then
            local hooks_path
            hooks_path=$(jq -r '.hooks' "$manifest_file")
            local resolved="$plugin_dir/.claude-plugin/$hooks_path"
            [[ -f "$resolved" ]] && hooks_file="$resolved"
        fi
    fi

    [[ -z "$hooks_file" ]] && return 0

    echo -e "\n${BLUE}--- Hook Safety Scan ---${NC}"

    if ! jq empty "$hooks_file" 2>/dev/null; then
        log_error "hooks.json has invalid JSON syntax: $hooks_file"
        return 1
    fi
    log_ok "hooks.json has valid JSON syntax"

    local events
    events=$(jq -r '.hooks | keys[]' "$hooks_file" 2>/dev/null) || return 0

    for event in $events; do
        local hook_count
        hook_count=$(jq ".hooks[\"$event\"] | length" "$hooks_file")

        for ((i=0; i<hook_count; i++)); do
            local has_matcher
            has_matcher=$(jq -r ".hooks[\"$event\"][$i] | has(\"matcher\")" "$hooks_file")

            if [[ "$has_matcher" == "true" ]]; then
                local matcher
                matcher=$(jq -r ".hooks[\"$event\"][$i].matcher // empty" "$hooks_file")
                log_info "$event hook with matcher: '${matcher:-<empty>}'"

                if [[ -z "$matcher" ]]; then
                    _flag_broad_matcher "$event" "$plugin_name"
                fi

                local nested_count
                nested_count=$(jq ".hooks[\"$event\"][$i].hooks | length" "$hooks_file" 2>/dev/null) || nested_count=0

                for ((j=0; j<nested_count; j++)); do
                    _scan_hook_entry "$plugin_dir" "$plugin_name" "$event" "$matcher" \
                        "$(jq -r ".hooks[\"$event\"][$i].hooks[$j].type // empty" "$hooks_file")" \
                        "$(jq -r ".hooks[\"$event\"][$i].hooks[$j].command // empty" "$hooks_file")" \
                        "$(jq -r ".hooks[\"$event\"][$i].hooks[$j].timeout // empty" "$hooks_file")"
                done
            else
                local matcher=""
                log_info "$event hook (no matcher — direct entry)"
                _flag_broad_matcher "$event" "$plugin_name"

                _scan_hook_entry "$plugin_dir" "$plugin_name" "$event" "$matcher" \
                    "$(jq -r ".hooks[\"$event\"][$i].type // empty" "$hooks_file")" \
                    "$(jq -r ".hooks[\"$event\"][$i].command // empty" "$hooks_file")" \
                    "$(jq -r ".hooks[\"$event\"][$i].timeout // empty" "$hooks_file")"
            fi
        done
    done
}

_flag_broad_matcher() {
    local event="$1"
    local plugin_name="$2"
    if [[ "$event" == "PreToolUse" || "$event" == "PostToolUse" || "$event" == "UserPromptSubmit" ]]; then
        log_warn "$event hook has no/empty matcher — fires on every event"
    fi
}

_scan_hook_entry() {
    local plugin_dir="$1"
    local plugin_name="$2"
    local event="$3"
    local matcher="$4"
    local hook_type="$5"
    local command_str="$6"
    local timeout="$7"

    # Prompt-type safety checks
    if [[ "$hook_type" == "prompt" && "$event" == "UserPromptSubmit" ]]; then
        log_error "prompt-type hook on UserPromptSubmit — injects AI evaluation on every message"
    fi
    if [[ "$hook_type" == "prompt" && "$event" == "PreToolUse" && -z "$matcher" ]]; then
        log_error "prompt-type on PreToolUse with no matcher — AI-evaluates every tool call"
    fi

    # Command-type checks
    if [[ "$hook_type" == "command" ]]; then
        if [[ -z "$timeout" ]]; then
            log_warn "$event command hook has no timeout"
        else
            log_ok "$event command hook has timeout: ${timeout}s"
        fi

        # Resolve script path
        if [[ "$command_str" =~ \$\{CLAUDE_PLUGIN_ROOT\}/(.*) ]]; then
            local relative="${BASH_REMATCH[1]}"
            relative="${relative%% *}"
            local script_path="$plugin_dir/$relative"

            if [[ -f "$script_path" ]]; then
                log_ok "Script exists: $relative"

                # Check for set -e
                if grep -qE '^\s*set\s+-[a-zA-Z]*e' "$script_path" 2>/dev/null; then
                    log_warn "Script '$relative' uses 'set -e' — breaks || fallback patterns"
                fi

                # Check for cat piped to grep (ARG_MAX risk)
                if grep -qE 'cat\s+"?\$' "$script_path" 2>/dev/null; then
                    if grep -qE 'cat\s+"?\$.*\|\s*grep' "$script_path" 2>/dev/null; then
                        log_warn "Script '$relative' uses 'cat \$file | grep' — grep the file directly to avoid ARG_MAX issues"
                    fi
                fi
            else
                log_error "Script not found: $relative (expected at $script_path)"
            fi
        fi
    fi
}

# Scan a single plugin
scan_plugin() {
    local plugin_dir="$1"
    local plugin_name
    plugin_name=$(basename "$plugin_dir")
    local manifest_file="$plugin_dir/.claude-plugin/plugin.json"

    echo ""
    echo "=========================================="
    echo -e "Scanning: ${BLUE}$plugin_name${NC}"
    echo "=========================================="

    if [[ ! -f "$manifest_file" ]]; then
        log_error "Missing manifest: .claude-plugin/plugin.json"
        return 1
    fi

    if ! jq empty "$manifest_file" 2>/dev/null; then
        log_error "Invalid JSON in plugin.json"
        return 1
    fi

    scan_component_paths "$plugin_dir" "$plugin_name"
    scan_hook_safety "$plugin_dir" "$plugin_name"
}

# Main
main() {
    echo "========================================"
    echo "  Plugin Deep Scanner"
    echo "  Path Resolution + Hook Safety"
    echo "========================================"

    if [[ $# -gt 0 ]]; then
        scan_plugin "$1"
    else
        # Scan all plugins
        local plugin_dirs=()

        if [[ -d "$ROOT_DIR/plugins" ]]; then
            while IFS= read -r -d '' dir; do
                [[ -d "$dir/.claude-plugin" ]] && plugin_dirs+=("$dir")
            done < <(find "$ROOT_DIR/plugins" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
        fi

        if [[ -d "$ROOT_DIR/external_plugins" ]]; then
            while IFS= read -r -d '' dir; do
                [[ -d "$dir/.claude-plugin" ]] && plugin_dirs+=("$dir")
            done < <(find "$ROOT_DIR/external_plugins" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
        fi

        if [[ ${#plugin_dirs[@]} -eq 0 ]]; then
            echo "No plugins found to scan"
            exit 0
        fi

        for dir in "${plugin_dirs[@]}"; do
            scan_plugin "$dir"
        done
    fi

    echo ""
    echo "========================================"
    echo "  Scan Summary"
    echo "========================================"
    echo -e "  ${GREEN}Passed:${NC}   $PASSED"
    echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
    echo -e "  ${RED}Errors:${NC}   $ERRORS"
    echo "========================================"

    if [[ $ERRORS -gt 0 ]]; then
        exit 1
    fi
    exit 0
}

main "$@"
