#!/usr/bin/env bash
#
# check-changelogs.sh - Detect changelog/version documentation drift.
#
# Pragmatic coverage:
# - every active plugin directory must include CHANGELOG.md
# - plugin.json version must have a matching Markdown heading in CHANGELOG.md
#
# This does not attempt semantic README comparison. It catches high-value
# release hygiene drift that can be validated reliably from local metadata.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_ok() { echo -e "${GREEN}OK:${NC} $1"; }
log_error() { echo -e "${RED}ERROR:${NC} $1" >&2; }
log_info() { echo "INFO: $1"; }

if ! command -v jq &> /dev/null; then
    log_error "jq is required but not installed"
    exit 2
fi

escape_regex() {
    printf '%s' "$1" | sed -E 's/[][(){}.^$+*?|\\-]/\\&/g'
}

plugin_dirs=()
for root in "$ROOT_DIR/plugins" "$ROOT_DIR/external_plugins"; do
    [[ -d "$root" ]] || continue
    while IFS= read -r -d '' manifest; do
        plugin_dirs+=("$(dirname "$(dirname "$manifest")")")
    done < <(find "$root" -mindepth 3 -maxdepth 3 -path '*/.claude-plugin/plugin.json' -print0 2>/dev/null | LC_ALL=C sort -z)
done

echo "========================================"
echo "  Changelog Drift Detection"
echo "========================================"
log_info "Checking CHANGELOG.md presence and manifest-version headings only; semantic README drift is out of scope."

if [[ ${#plugin_dirs[@]} -eq 0 ]]; then
    log_info "No active plugin manifests found"
    exit 0
fi

errors=0
for plugin_dir in "${plugin_dirs[@]}"; do
    manifest_file="$plugin_dir/.claude-plugin/plugin.json"
    rel="${plugin_dir#$ROOT_DIR/}"
    plugin_name="$(jq -r '.name // empty' "$manifest_file")"
    version="$(jq -r '.version // empty' "$manifest_file")"
    changelog_file="$plugin_dir/CHANGELOG.md"

    if [[ -z "$plugin_name" ]]; then
        plugin_name="$(basename "$plugin_dir")"
    fi

    if [[ ! -f "$changelog_file" ]]; then
        log_error "MISSING CHANGELOG: $rel/"
        ((errors++))
        continue
    fi

    if [[ -z "$version" ]]; then
        log_error "[$plugin_name] manifest missing version; cannot match changelog entry"
        ((errors++))
        continue
    fi

    version_re="$(escape_regex "$version")"
    if grep -Eq "^#{1,6}[[:space:]]+\\[?v?$version_re\\]?([[:space:]-]|$)" "$changelog_file"; then
        log_ok "[$plugin_name] CHANGELOG.md contains version $version"
    else
        log_error "[$plugin_name] manifest version $version has no matching CHANGELOG.md heading"
        ((errors++))
    fi
done

echo ""
echo "========================================"
echo "  Changelog Check Summary"
echo "========================================"
echo "Checked: ${#plugin_dirs[@]}"
echo "Errors:  $errors"
echo "========================================"

if [[ "$errors" -gt 0 ]]; then
    exit 1
fi
