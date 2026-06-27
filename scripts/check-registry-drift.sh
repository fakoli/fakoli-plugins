#!/usr/bin/env bash
#
# check-registry-drift.sh - Detect drift in generated registry metadata.
#
# Exits non-zero when marketplace metadata is incomplete, category definitions
# are unused/stale, or generated registry files differ from the committed files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok() { echo -e "${GREEN}OK:${NC} $1"; }
log_warn() { echo -e "${YELLOW}WARN:${NC} $1"; }
log_error() { echo -e "${RED}ERROR:${NC} $1" >&2; }
log_info() { echo "INFO: $1"; }

for cmd in jq python3 diff; do
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd is required but not installed"
        exit 2
    fi
done

MARKETPLACE_FILE="$ROOT_DIR/.claude-plugin/marketplace.json"
INDEX_FILE="$ROOT_DIR/registry/index.json"
CATEGORIES_FILE="$ROOT_DIR/registry/categories.json"
TAGS_FILE="$ROOT_DIR/registry/tags.json"
GENERATED_FILES=(
    "$MARKETPLACE_FILE"
    "$INDEX_FILE"
    "$CATEGORIES_FILE"
    "$TAGS_FILE"
)

for file in "${GENERATED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        log_error "Missing generated file: ${file#$ROOT_DIR/}"
        exit 1
    fi
done

TMP_DIR="$(mktemp -d)"
restore_files() {
    for file in "${GENERATED_FILES[@]}"; do
        local rel="${file#$ROOT_DIR/}"
        if [[ -f "$TMP_DIR/$rel" ]]; then
            cp "$TMP_DIR/$rel" "$file"
        fi
    done
    rm -rf "$TMP_DIR"
}
trap restore_files EXIT

for file in "${GENERATED_FILES[@]}"; do
    rel="${file#$ROOT_DIR/}"
    mkdir -p "$TMP_DIR/$(dirname "$rel")"
    cp "$file" "$TMP_DIR/$rel"
done

echo "========================================"
echo "  Registry Drift Detection"
echo "========================================"

(cd "$ROOT_DIR" && python3 - <<'PY'
import json
import pathlib
from collections import Counter, defaultdict

root = pathlib.Path.cwd()
marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())
index = json.loads((root / "registry/index.json").read_text())
categories = json.loads((root / "registry/categories.json").read_text())
tags = json.loads((root / "registry/tags.json").read_text())

plugin_dirs = sorted(
    p.parent.parent.name
    for p in (root / "plugins").glob("*/.claude-plugin/plugin.json")
)
market_plugins = marketplace.get("plugins", [])
market_by_name = {p.get("name"): p for p in market_plugins}
index_plugins = index.get("plugins", [])
index_by_name = {p.get("name"): p for p in index_plugins}

if sorted(market_by_name) != plugin_dirs:
    raise SystemExit(
        "marketplace plugin list does not match active plugin directories: "
        f"missing={sorted(set(plugin_dirs) - set(market_by_name))}, "
        f"extra={sorted(set(market_by_name) - set(plugin_dirs))}"
    )

if sorted(index_by_name) != plugin_dirs:
    raise SystemExit(
        "registry index plugin list does not match active plugin directories: "
        f"missing={sorted(set(plugin_dirs) - set(index_by_name))}, "
        f"extra={sorted(set(index_by_name) - set(plugin_dirs))}"
    )

category_defs = marketplace.get("categories", [])
category_ids = [c.get("id") for c in category_defs]
if any(not category for category in category_ids):
    raise SystemExit("marketplace categories must have non-empty ids")

duplicates = [item for item, count in Counter(category_ids).items() if count > 1]
if duplicates:
    raise SystemExit(f"duplicate marketplace category ids: {duplicates}")

category_set = set(category_ids)
used_categories = set()
for plugin in market_plugins:
    name = plugin.get("name")
    category = plugin.get("category")
    description = plugin.get("description")
    if not category:
        raise SystemExit(f"marketplace plugin missing category: {name}")
    if category not in category_set:
        raise SystemExit(f"marketplace plugin {name} references unknown category: {category}")
    if not description:
        raise SystemExit(f"marketplace plugin missing description: {name}")
    used_categories.add(category)

unused = sorted(category_set - used_categories)
if unused:
    raise SystemExit(f"marketplace categories declared but unused: {unused}")

category_groups = categories.get("categories", [])
seen_in_categories = []
for group in category_groups:
    category = group.get("category")
    if category not in category_set:
        raise SystemExit(f"registry category group is not declared in marketplace: {category}")
    plugins = group.get("plugins", [])
    if group.get("count") != len(plugins):
        raise SystemExit(f"registry category count mismatch for {category}")
    for plugin in plugins:
        name = plugin.get("name")
        seen_in_categories.append(name)
        if name not in index_by_name:
            raise SystemExit(f"registry category references unknown plugin: {name}")
        if index_by_name[name].get("category") != category:
            raise SystemExit(f"registry category mismatch for plugin: {name}")

if sorted(seen_in_categories) != sorted(index_by_name):
    raise SystemExit("registry category groups do not cover the same plugin set as registry index")

expected_tags = defaultdict(list)
for plugin in index_plugins:
    for tag in plugin.get("keywords") or []:
        expected_tags[tag].append(plugin["name"])

tag_entries = tags.get("tags", [])
if tags.get("totalTags") != len(tag_entries):
    raise SystemExit("registry tag totalTags does not match tag entry count")

seen_tags = set()
for entry in tag_entries:
    tag = entry.get("tag")
    plugins = sorted(expected_tags.get(tag, []))
    if tag in seen_tags:
        raise SystemExit(f"duplicate registry tag entry: {tag}")
    seen_tags.add(tag)
    if not plugins:
        raise SystemExit(f"registry tag has no source plugin keywords: {tag}")
    if entry.get("count") != len(plugins):
        raise SystemExit(f"registry tag count mismatch for {tag}")
    if entry.get("plugins") != plugins:
        raise SystemExit(f"registry tag plugin list mismatch for {tag}")

missing_tags = sorted(set(expected_tags) - seen_tags)
if missing_tags:
    raise SystemExit(f"registry tags missing keyword entries: {missing_tags}")
PY
)
log_ok "Marketplace categories and registry aggregates are internally consistent"

log_info "Regenerating registry output for drift comparison"
(cd "$ROOT_DIR" && ./scripts/generate-index.sh >/tmp/fakoli-registry-generate.out)
cat /tmp/fakoli-registry-generate.out
rm -f /tmp/fakoli-registry-generate.out

DRIFT_FOUND=0
for file in "${GENERATED_FILES[@]}"; do
    rel="${file#$ROOT_DIR/}"
    before="$TMP_DIR/$rel"
    old_stripped="$TMP_DIR/$rel.old.stripped"
    new_stripped="$TMP_DIR/$rel.new.stripped"

    jq 'walk(if type == "object" then del(.generatedAt, .indexedAt) else . end)' "$before" > "$old_stripped"
    jq 'walk(if type == "object" then del(.generatedAt, .indexedAt) else . end)' "$file" > "$new_stripped"

    if ! diff -u "$old_stripped" "$new_stripped" > "$TMP_DIR/$rel.diff"; then
        log_warn "Drift detected in $rel"
        cat "$TMP_DIR/$rel.diff"
        DRIFT_FOUND=1
    fi
done

if [[ "$DRIFT_FOUND" -ne 0 ]]; then
    log_error "Registry drift detected. Run ./scripts/generate-index.sh and commit the updated output."
    exit 1
fi

log_ok "No registry drift detected"
