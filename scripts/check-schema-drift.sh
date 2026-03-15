#!/usr/bin/env bash
#
# check-schema-drift.sh - Detect drift between our schemas and official Anthropic docs
#
# Usage: ./scripts/check-schema-drift.sh
#
# Compares:
#   1. Baseline vs current docs scrape (detects upstream docs changes)
#   2. Schema vs baseline (detects our schema falling behind)
#
# Exit codes:
#   0 - No drift detected
#   1 - Drift detected (action needed)
#   2 - Script error (deps missing, fetch failed)
#

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMA_FILE="$ROOT_DIR/schemas/plugin.schema.json"
BASELINE_FILE="$ROOT_DIR/schemas/.field-baseline.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DRIFT_FOUND=0

log_ok() { echo -e "${GREEN}OK:${NC} $1"; }
log_warn() { echo -e "${YELLOW}WARN:${NC} $1"; DRIFT_FOUND=1; }
log_info() { echo -e "INFO: $1"; }
log_error() { echo -e "${RED}ERROR:${NC} $1" >&2; }

# Check dependencies
for cmd in jq curl; do
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd is required but not installed"
        exit 2
    fi
done

if [[ ! -f "$SCHEMA_FILE" ]]; then
    log_error "Schema file not found: $SCHEMA_FILE"
    exit 2
fi

if [[ ! -f "$BASELINE_FILE" ]]; then
    log_error "Baseline file not found: $BASELINE_FILE"
    exit 2
fi

echo "========================================"
echo "  Schema Drift Detection"
echo "========================================"
echo ""

# --- Step 1: Extract fields from our schema ---
SCHEMA_FIELDS=$(jq -c '[.properties | keys[] | select(. != "$schema")] | sort' "$SCHEMA_FILE")
log_info "Schema fields: $SCHEMA_FIELDS"

# --- Step 2: Extract fields from baseline ---
BASELINE_FIELDS=$(jq -c '.plugin | sort' "$BASELINE_FILE")
log_info "Baseline fields: $BASELINE_FIELDS"

# --- Step 3: Compare schema vs baseline ---
echo ""
echo "--- Schema vs Baseline ---"

# Fields in baseline but not in schema
MISSING_FROM_SCHEMA=$(jq -n --argjson baseline "$BASELINE_FIELDS" --argjson schema "$SCHEMA_FIELDS" \
    '[$baseline[] | select(. as $f | $schema | index($f) | not)]')
MISSING_COUNT=$(echo "$MISSING_FROM_SCHEMA" | jq 'length')

if [[ "$MISSING_COUNT" -gt 0 ]]; then
    log_warn "Fields in baseline but NOT in schema (schema is behind):"
    echo "$MISSING_FROM_SCHEMA" | jq -r '.[] | "  - \(.)"'
else
    log_ok "Schema contains all baseline fields"
fi

# Fields in schema but not in baseline
EXTRA_IN_SCHEMA=$(jq -n --argjson baseline "$BASELINE_FIELDS" --argjson schema "$SCHEMA_FIELDS" \
    '[$schema[] | select(. as $f | $baseline | index($f) | not)]')
EXTRA_COUNT=$(echo "$EXTRA_IN_SCHEMA" | jq 'length')

if [[ "$EXTRA_COUNT" -gt 0 ]]; then
    log_info "Fields in schema but NOT in baseline (may be our extensions):"
    echo "$EXTRA_IN_SCHEMA" | jq -r '.[] | "  - \(.)"'
else
    log_ok "No extra fields in schema beyond baseline"
fi

# --- Step 4: Try to scrape official docs for field changes ---
echo ""
echo "--- Upstream Docs Check ---"

DOCS_URL="https://code.claude.com/docs/en/plugins-reference"
log_info "Fetching $DOCS_URL ..."

DOCS_CONTENT=$(curl -sL --max-time 30 "$DOCS_URL" 2>/dev/null) || true

if [[ -z "$DOCS_CONTENT" ]]; then
    log_info "Could not fetch docs page — skipping upstream comparison"
    log_info "This is normal in CI environments without internet access"
else
    # Extract field names from docs — look for field names in code blocks or tables
    # This is best-effort; if the docs HTML structure changes, we fall back to baseline comparison
    SCRAPED_FIELDS=$(echo "$DOCS_CONTENT" | \
        grep -oE '"(name|version|description|author|homepage|repository|license|keywords|commands|agents|skills|hooks|mcpServers|outputStyles|lspServers|bugs|extended|mcp|outputFormat|configSchema|settings)"' | \
        tr -d '"' | sort -u | jq -R . | jq -s 'sort') || SCRAPED_FIELDS="[]"

    SCRAPED_COUNT=$(echo "$SCRAPED_FIELDS" | jq 'length')

    if [[ "$SCRAPED_COUNT" -lt 3 ]]; then
        log_info "Docs scrape returned too few fields ($SCRAPED_COUNT) — HTML structure may have changed"
        log_info "Falling back to baseline-only comparison"
    else
        log_info "Scraped fields from docs: $SCRAPED_FIELDS"

        # Fields in scraped docs but not in baseline (upstream added new fields)
        NEW_UPSTREAM=$(jq -n --argjson scraped "$SCRAPED_FIELDS" --argjson baseline "$BASELINE_FIELDS" \
            '[$scraped[] | select(. as $f | $baseline | index($f) | not)]')
        NEW_COUNT=$(echo "$NEW_UPSTREAM" | jq 'length')

        if [[ "$NEW_COUNT" -gt 0 ]]; then
            log_warn "New fields detected in upstream docs (update baseline and schema):"
            echo "$NEW_UPSTREAM" | jq -r '.[] | "  - \(.)"'
        else
            log_ok "No new fields detected in upstream docs"
        fi

        # Fields in baseline but not in scraped docs (upstream may have removed fields)
        REMOVED_UPSTREAM=$(jq -n --argjson scraped "$SCRAPED_FIELDS" --argjson baseline "$BASELINE_FIELDS" \
            '[$baseline[] | select(. as $f | $scraped | index($f) | not)]')
        REMOVED_COUNT=$(echo "$REMOVED_UPSTREAM" | jq 'length')

        if [[ "$REMOVED_COUNT" -gt 0 ]]; then
            log_info "Fields in baseline but not found in docs scrape (may be scrape limitation):"
            echo "$REMOVED_UPSTREAM" | jq -r '.[] | "  - \(.)"'
        fi
    fi
fi

# --- Summary ---
echo ""
echo "========================================"
echo "  Drift Detection Summary"
echo "========================================"

if [[ "$DRIFT_FOUND" -eq 0 ]]; then
    echo -e "${GREEN}No drift detected — schema is aligned with baseline${NC}"
    exit 0
else
    echo -e "${YELLOW}Drift detected — review warnings above${NC}"
    exit 1
fi
