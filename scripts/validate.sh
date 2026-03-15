#!/usr/bin/env bash
#
# validate.sh - Validates plugin manifests in the fakoli-plugins marketplace
#
# Usage: ./scripts/validate.sh [plugin-path]
#   If no path provided, validates all plugins in plugins/ and external_plugins/
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMA_FILE="$ROOT_DIR/schemas/plugin.schema.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

log_error() {
    echo -e "${RED}ERROR:${NC} $1" >&2
    ((FAILED++)) || true
}

log_warn() {
    echo -e "${YELLOW}WARN:${NC} $1" >&2
    ((WARNINGS++)) || true
}

log_success() {
    echo -e "${GREEN}OK:${NC} $1"
    ((PASSED++)) || true
}

log_info() {
    echo -e "INFO: $1"
}

# Check if jq is available
check_dependencies() {
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}Error: jq is required but not installed.${NC}"
        echo "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
        exit 1
    fi
}

# Validate JSON syntax
validate_json_syntax() {
    local file="$1"
    if jq empty "$file" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Validate semver format
validate_semver() {
    local version="$1"
    local semver_regex='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$'
    if [[ "$version" =~ $semver_regex ]]; then
        return 0
    else
        return 1
    fi
}

# Derive allowed fields from schema (single source of truth)
# Reference: https://code.claude.com/docs/en/plugins-reference
if [[ ! -f "$SCHEMA_FILE" ]]; then
    echo -e "${RED}Error: Schema file not found: $SCHEMA_FILE${NC}"
    exit 1
fi
ALLOWED_FIELDS=$(jq -c '[.properties | keys[]]' "$SCHEMA_FILE")
if [[ -z "$ALLOWED_FIELDS" || "$ALLOWED_FIELDS" == "null" ]]; then
    echo -e "${RED}Error: Could not extract allowed fields from schema${NC}"
    exit 1
fi

# Validate a single plugin
validate_plugin() {
    local plugin_dir="$1"
    local plugin_name
    plugin_name=$(basename "$plugin_dir")
    local manifest_file="$plugin_dir/.claude-plugin/plugin.json"
    local has_errors=0

    echo ""
    echo "=========================================="
    echo "Validating: $plugin_name"
    echo "=========================================="

    # Check manifest exists
    if [[ ! -f "$manifest_file" ]]; then
        log_error "[$plugin_name] Missing manifest: .claude-plugin/plugin.json"
        return 1
    fi

    # Validate JSON syntax
    if ! validate_json_syntax "$manifest_file"; then
        log_error "[$plugin_name] Invalid JSON syntax in plugin.json"
        return 1
    fi
    log_success "[$plugin_name] Valid JSON syntax"

    # Check for unrecognized fields (Claude Code will reject these)
    local unrecognized_fields
    unrecognized_fields=$(jq -r --argjson allowed "$ALLOWED_FIELDS" \
        'keys | map(select(. as $k | $allowed | index($k) | not)) | .[]' "$manifest_file" 2>/dev/null)
    if [[ -n "$unrecognized_fields" ]]; then
        for field in $unrecognized_fields; do
            log_error "[$plugin_name] Unrecognized field '$field' - Claude Code will reject this"
            has_errors=1
        done
    fi

    # Extract and validate required field: name
    local name
    name=$(jq -r '.name // empty' "$manifest_file")
    if [[ -z "$name" ]]; then
        log_error "[$plugin_name] Missing required field: name"
        has_errors=1
    else
        # Validate name format (kebab-case, no spaces)
        if [[ ! "$name" =~ ^[a-z0-9-]+$ ]]; then
            log_error "[$plugin_name] Invalid name format: must be kebab-case (lowercase, alphanumeric, hyphens)"
            has_errors=1
        else
            log_success "[$plugin_name] Valid name: $name"
        fi
    fi

    # Validate optional metadata fields
    local version
    version=$(jq -r '.version // empty' "$manifest_file")
    if [[ -n "$version" ]]; then
        if ! validate_semver "$version"; then
            log_error "[$plugin_name] Invalid version format: $version (must be semver)"
            has_errors=1
        else
            log_success "[$plugin_name] Valid version: $version"
        fi
    fi

    local description
    description=$(jq -r '.description // empty' "$manifest_file")
    if [[ -n "$description" ]]; then
        log_success "[$plugin_name] Has description"
    fi

    # Validate author field (must be object with name, optional email/url)
    local has_author
    has_author=$(jq 'has("author")' "$manifest_file")
    if [[ "$has_author" == "true" ]]; then
        local author_type
        author_type=$(jq -r '.author | type' "$manifest_file")
        if [[ "$author_type" != "object" ]]; then
            log_error "[$plugin_name] author must be an object with name, email, url fields"
            has_errors=1
        else
            local author_name
            author_name=$(jq -r '.author.name // empty' "$manifest_file")
            if [[ -z "$author_name" ]]; then
                log_warn "[$plugin_name] author object should have 'name' field"
            else
                log_success "[$plugin_name] Valid author: $author_name"
            fi
        fi
    fi

    # Validate repository field (must be string URL, not object)
    local has_repo
    has_repo=$(jq 'has("repository")' "$manifest_file")
    if [[ "$has_repo" == "true" ]]; then
        local repo_type
        repo_type=$(jq -r '.repository | type' "$manifest_file")
        if [[ "$repo_type" != "string" ]]; then
            log_error "[$plugin_name] repository must be a string URL, not an object"
            has_errors=1
        else
            log_success "[$plugin_name] Has repository URL"
        fi
    fi

    # Validate keywords field (must be array of strings)
    local has_keywords
    has_keywords=$(jq 'has("keywords")' "$manifest_file")
    if [[ "$has_keywords" == "true" ]]; then
        local keywords_type
        keywords_type=$(jq -r '.keywords | type' "$manifest_file")
        if [[ "$keywords_type" != "array" ]]; then
            log_error "[$plugin_name] keywords must be an array"
            has_errors=1
        else
            log_success "[$plugin_name] Has keywords"
        fi
    fi

    # Check for README
    if [[ -f "$plugin_dir/README.md" ]]; then
        log_success "[$plugin_name] README.md present"
    else
        log_warn "[$plugin_name] Missing README.md"
    fi

    # Check for CHANGELOG
    if [[ -f "$plugin_dir/CHANGELOG.md" ]]; then
        log_success "[$plugin_name] CHANGELOG.md present"
    else
        log_warn "[$plugin_name] Missing CHANGELOG.md"
    fi

    # Check for LICENSE
    if [[ -f "$plugin_dir/LICENSE" ]] || [[ -f "$plugin_dir/LICENSE.md" ]] || [[ -f "$plugin_dir/LICENSE.txt" ]]; then
        log_success "[$plugin_name] LICENSE present"
    else
        local license
        license=$(jq -r '.license // empty' "$manifest_file")
        if [[ -n "$license" ]]; then
            log_success "[$plugin_name] License declared in manifest: $license"
        else
            log_warn "[$plugin_name] No LICENSE file or license field"
        fi
    fi

    # Check for at least one component directory (skills, commands, agents, or hooks)
    # Claude Code discovers these from directories, not manifest fields
    local has_skills=0 has_commands=0 has_agents=0 has_hooks=0

    if [[ -d "$plugin_dir/skills" ]]; then
        has_skills=$(find "$plugin_dir/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$has_skills" -gt 0 ]]; then
            log_success "[$plugin_name] Has $has_skills skill(s) in skills/ directory"
        fi
    fi

    if [[ -d "$plugin_dir/commands" ]]; then
        has_commands=$(find "$plugin_dir/commands" -mindepth 1 -maxdepth 1 \( -type d -o -name "*.md" \) 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$has_commands" -gt 0 ]]; then
            log_success "[$plugin_name] Has $has_commands command(s) in commands/ directory"
        fi
    fi

    if [[ -d "$plugin_dir/agents" ]]; then
        has_agents=$(find "$plugin_dir/agents" -mindepth 1 -maxdepth 1 \( -type d -o -name "*.md" \) 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$has_agents" -gt 0 ]]; then
            log_success "[$plugin_name] Has $has_agents agent(s) in agents/ directory"
        fi
    fi

    if [[ -d "$plugin_dir/hooks" ]]; then
        has_hooks=$(find "$plugin_dir/hooks" -mindepth 1 -maxdepth 1 \( -type f -o -type d \) 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$has_hooks" -gt 0 ]]; then
            log_success "[$plugin_name] Has $has_hooks hook(s) in hooks/ directory"
        fi
    fi

    if [[ "$has_skills" -eq 0 && "$has_commands" -eq 0 && "$has_agents" -eq 0 && "$has_hooks" -eq 0 ]]; then
        log_warn "[$plugin_name] No skills/, commands/, agents/, or hooks/ directories found"
    fi

    # Validate component paths and hook safety
    validate_component_paths "$plugin_dir" "$plugin_name" "$manifest_file" || has_errors=1
    validate_hook_safety "$plugin_dir" "$plugin_name" || true

    return $has_errors
}

# Validate component paths declared in manifest
validate_component_paths() {
    local plugin_dir="$1"
    local plugin_name="$2"
    local manifest_file="$3"
    local has_errors=0

    # Auto-discovered directories: warn if declared in manifest
    for field in commands agents skills; do
        local has_field
        has_field=$(jq "has(\"$field\")" "$manifest_file")
        if [[ "$has_field" == "true" ]]; then
            log_warn "[$plugin_name] '$field' is auto-discovered from directories — declaring it in manifest is unnecessary"
        fi
    done

    # Check for ./commands, ./agents, ./skills, ./hooks path confusion
    for field in commands agents skills hooks mcpServers; do
        local field_type
        field_type=$(jq -r ".$field | type" "$manifest_file" 2>/dev/null)

        [[ "$field_type" == "null" || "$field_type" == "object" ]] && continue

        local paths=()
        if [[ "$field_type" == "string" ]]; then
            paths+=("$(jq -r ".$field" "$manifest_file")")
        elif [[ "$field_type" == "array" ]]; then
            while IFS= read -r p; do
                paths+=("$p")
            done < <(jq -r ".$field[]" "$manifest_file" 2>/dev/null)
        fi

        if [[ ${#paths[@]} -eq 0 ]]; then
            continue
        fi

        for path in "${paths[@]}"; do
            [[ -z "$path" || "$path" == "null" ]] && continue
            # Check for ./ prefix that likely should be ../
            if [[ "$path" =~ ^\./((commands|agents|skills|hooks)(/|$)) ]]; then
                log_warn "[$plugin_name] '$field' path '$path' starts with ./ — paths resolve relative to .claude-plugin/, did you mean '../${path#./}'?"
            fi
        done
    done

    # Validate hooks string path resolves to existing file
    local hooks_type
    hooks_type=$(jq -r '.hooks | type' "$manifest_file" 2>/dev/null)
    if [[ "$hooks_type" == "string" ]]; then
        local hooks_path
        hooks_path=$(jq -r '.hooks' "$manifest_file")
        local resolved="$plugin_dir/.claude-plugin/$hooks_path"
        if [[ ! -f "$resolved" ]]; then
            log_error "[$plugin_name] hooks path '$hooks_path' not found (resolved to $resolved)"
            has_errors=1
            # Suggest ../fix if file exists at plugin root
            local alt="$plugin_dir/$hooks_path"
            if [[ -f "$alt" ]]; then
                log_info "[$plugin_name]   Did you mean '../$hooks_path'? File exists at plugin root."
            fi
        fi
    fi

    # Validate mcpServers string path resolves to existing file
    local mcp_type
    mcp_type=$(jq -r '.mcpServers | type' "$manifest_file" 2>/dev/null)
    if [[ "$mcp_type" == "string" ]]; then
        local mcp_path
        mcp_path=$(jq -r '.mcpServers' "$manifest_file")
        local resolved="$plugin_dir/.claude-plugin/$mcp_path"
        if [[ ! -f "$resolved" ]]; then
            log_error "[$plugin_name] mcpServers path '$mcp_path' not found (resolved to $resolved)"
            has_errors=1
            local alt="$plugin_dir/$mcp_path"
            if [[ -f "$alt" ]]; then
                log_info "[$plugin_name]   Did you mean '../$mcp_path'? File exists at plugin root."
            fi
        fi
    fi

    # License file consistency check
    local license_field
    license_field=$(jq -r '.license // empty' "$manifest_file")
    if [[ -n "$license_field" ]]; then
        if [[ ! -f "$plugin_dir/LICENSE" && ! -f "$plugin_dir/LICENSE.md" && ! -f "$plugin_dir/LICENSE.txt" ]]; then
            log_warn "[$plugin_name] license field set to '$license_field' but no LICENSE file found"
        fi
    fi

    return $has_errors
}

# Validate hook safety configurations
validate_hook_safety() {
    local plugin_dir="$1"
    local plugin_name="$2"

    # Find hooks.json — check hooks/ directory first, then manifest path
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

    # Validate JSON syntax
    if ! validate_json_syntax "$hooks_file"; then
        log_error "[$plugin_name] Invalid JSON in hooks file: $hooks_file"
        return 1
    fi

    # Check each event type for safety issues
    local events
    events=$(jq -r '.hooks | keys[]' "$hooks_file" 2>/dev/null) || return 0

    for event in $events; do
        local hook_count
        hook_count=$(jq ".hooks[\"$event\"] | length" "$hooks_file")

        for ((i=0; i<hook_count; i++)); do
            local matcher hook_type command_str

            # Check if this entry has nested hooks (matcher pattern) or is a direct hook
            local has_matcher
            has_matcher=$(jq -r ".hooks[\"$event\"][$i] | has(\"matcher\")" "$hooks_file")

            if [[ "$has_matcher" == "true" ]]; then
                matcher=$(jq -r ".hooks[\"$event\"][$i].matcher // empty" "$hooks_file")

                # Check nested hooks array
                local nested_count
                nested_count=$(jq ".hooks[\"$event\"][$i].hooks | length" "$hooks_file" 2>/dev/null) || nested_count=0

                for ((j=0; j<nested_count; j++)); do
                    hook_type=$(jq -r ".hooks[\"$event\"][$i].hooks[$j].type // empty" "$hooks_file")
                    command_str=$(jq -r ".hooks[\"$event\"][$i].hooks[$j].command // empty" "$hooks_file")
                    local timeout
                    timeout=$(jq -r ".hooks[\"$event\"][$i].hooks[$j].timeout // empty" "$hooks_file")

                    _check_hook_safety "$plugin_dir" "$plugin_name" "$event" "$matcher" "$hook_type" "$command_str" "$timeout"
                done
            else
                # Direct hook entry (no matcher)
                hook_type=$(jq -r ".hooks[\"$event\"][$i].type // empty" "$hooks_file")
                command_str=$(jq -r ".hooks[\"$event\"][$i].command // empty" "$hooks_file")
                local timeout
                timeout=$(jq -r ".hooks[\"$event\"][$i].timeout // empty" "$hooks_file")
                matcher=""

                _check_hook_safety "$plugin_dir" "$plugin_name" "$event" "$matcher" "$hook_type" "$command_str" "$timeout"
            fi
        done
    done

    return 0
}

# Helper: check individual hook for safety issues
_check_hook_safety() {
    local plugin_dir="$1"
    local plugin_name="$2"
    local event="$3"
    local matcher="$4"
    local hook_type="$5"
    local command_str="$6"
    local timeout="$7"

    # High-frequency events with broad/missing matchers
    if [[ "$event" == "PreToolUse" || "$event" == "PostToolUse" || "$event" == "UserPromptSubmit" ]]; then
        if [[ -z "$matcher" ]]; then
            log_warn "[$plugin_name] $event hook has no matcher — fires on every ${event/Pre/}${event/Post/} event"
        fi
    fi

    # Prompt-type on UserPromptSubmit = conversation hijack
    if [[ "$hook_type" == "prompt" && "$event" == "UserPromptSubmit" ]]; then
        log_error "[$plugin_name] prompt-type hook on UserPromptSubmit will inject AI evaluation on every message — use command-type instead"
    fi

    # Prompt-type on PreToolUse without matcher = AI-evaluates every tool call
    if [[ "$hook_type" == "prompt" && "$event" == "PreToolUse" && -z "$matcher" ]]; then
        log_error "[$plugin_name] prompt-type hook on PreToolUse with no matcher — AI-evaluates every tool call"
    fi

    # Command-type: check for missing timeout
    if [[ "$hook_type" == "command" && -z "$timeout" ]]; then
        log_warn "[$plugin_name] $event command hook has no timeout — could hang indefinitely"
    fi

    # Command-type: check script existence and for set -e
    if [[ "$hook_type" == "command" && -n "$command_str" ]]; then
        # Extract script path from command (handle bash/sh prefix and ${CLAUDE_PLUGIN_ROOT})
        local script_path=""
        if [[ "$command_str" =~ \$\{CLAUDE_PLUGIN_ROOT\}/(.*) ]]; then
            local relative="${BASH_REMATCH[1]}"
            # Strip any arguments after the script path
            relative="${relative%% *}"
            script_path="$plugin_dir/$relative"
        fi

        if [[ -n "$script_path" ]]; then
            if [[ ! -f "$script_path" ]]; then
                log_error "[$plugin_name] $event hook references script that does not exist: $script_path"
            else
                # Check for set -e in the script
                if grep -qE '^\s*set\s+-[a-zA-Z]*e' "$script_path" 2>/dev/null; then
                    log_warn "[$plugin_name] $event hook script '$script_path' uses 'set -e' — breaks || fallback patterns, can cause false blocks"
                fi
            fi
        fi
    fi
}

# Validate marketplace.json schema for Claude Code compatibility
validate_marketplace() {
    local marketplace_file="$ROOT_DIR/.claude-plugin/marketplace.json"

    echo ""
    echo "=========================================="
    echo "Validating: marketplace.json"
    echo "=========================================="

    if [[ ! -f "$marketplace_file" ]]; then
        log_warn "No marketplace.json found at .claude-plugin/marketplace.json"
        return 0
    fi

    # Validate JSON syntax
    if ! validate_json_syntax "$marketplace_file"; then
        log_error "[marketplace] Invalid JSON syntax"
        return 1
    fi
    log_success "[marketplace] Valid JSON syntax"

    # Check required top-level fields
    local name
    name=$(jq -r '.name // empty' "$marketplace_file")
    if [[ -z "$name" ]]; then
        log_error "[marketplace] Missing required field: name"
    else
        log_success "[marketplace] Has name: $name"
    fi

    # Check plugins array exists
    local has_plugins
    has_plugins=$(jq 'has("plugins")' "$marketplace_file")
    if [[ "$has_plugins" != "true" ]]; then
        log_error "[marketplace] Missing required field: plugins"
        return 1
    fi

    # Validate each plugin entry
    local plugin_count
    plugin_count=$(jq '.plugins | length' "$marketplace_file")
    log_info "[marketplace] Found $plugin_count plugin(s)"

    local plugin_errors=0
    for ((i=0; i<plugin_count; i++)); do
        local plugin_name
        plugin_name=$(jq -r ".plugins[$i].name // empty" "$marketplace_file")

        # Check 'name' field exists
        if [[ -z "$plugin_name" ]]; then
            log_error "[marketplace] Plugin at index $i missing required 'name' field"
            ((plugin_errors++))
            continue
        fi

        # Check 'source' field exists (not 'path')
        local source
        source=$(jq -r ".plugins[$i].source // empty" "$marketplace_file")
        if [[ -z "$source" ]]; then
            log_error "[marketplace] Plugin '$plugin_name' missing required 'source' field"
            ((plugin_errors++))
        elif [[ ! "$source" =~ ^\./  ]]; then
            log_error "[marketplace] Plugin '$plugin_name' source must start with './' (got: $source)"
            ((plugin_errors++))
        else
            log_success "[marketplace] Plugin '$plugin_name' has valid source: $source"
        fi

        # Check for invalid 'path' field (common mistake)
        local has_path
        has_path=$(jq -r ".plugins[$i] | has(\"path\")" "$marketplace_file")
        if [[ "$has_path" == "true" ]]; then
            log_error "[marketplace] Plugin '$plugin_name' has invalid 'path' field - use 'source' instead"
            ((plugin_errors++))
        fi
    done

    if [[ $plugin_errors -gt 0 ]]; then
        return 1
    fi

    return 0
}

# Find and validate all plugins
validate_all_plugins() {
    local plugin_dirs=()

    # Find plugins in plugins/
    if [[ -d "$ROOT_DIR/plugins" ]]; then
        while IFS= read -r -d '' dir; do
            if [[ -d "$dir/.claude-plugin" ]]; then
                plugin_dirs+=("$dir")
            fi
        done < <(find "$ROOT_DIR/plugins" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    fi

    # Find plugins in external_plugins/
    if [[ -d "$ROOT_DIR/external_plugins" ]]; then
        while IFS= read -r -d '' dir; do
            if [[ -d "$dir/.claude-plugin" ]]; then
                plugin_dirs+=("$dir")
            fi
        done < <(find "$ROOT_DIR/external_plugins" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    fi

    if [[ ${#plugin_dirs[@]} -eq 0 ]]; then
        log_info "No plugins found to validate"
        return 0
    fi

    for plugin_dir in "${plugin_dirs[@]}"; do
        validate_plugin "$plugin_dir" || true
    done
}

# Main
main() {
    check_dependencies

    echo "========================================"
    echo "  Fakoli Plugins Marketplace Validator"
    echo "========================================"

    if [[ $# -gt 0 ]]; then
        # Validate specific plugin
        validate_plugin "$1"
    else
        # Validate all plugins
        validate_all_plugins
        # Validate marketplace.json
        validate_marketplace || true
    fi

    echo ""
    echo "========================================"
    echo "  Validation Summary"
    echo "========================================"
    echo -e "${GREEN}Passed:${NC} $PASSED"
    echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
    echo -e "${RED}Failed:${NC} $FAILED"
    echo "========================================"

    if [[ $FAILED -gt 0 ]]; then
        exit 1
    fi
    exit 0
}

main "$@"
