#!/usr/bin/env bash
#
# check-all.sh - Run the combined marketplace verification gate.
#
# The gate is intentionally sequential so failures stop at the first broken
# layer: marketplace metadata, path resolution, then affected plugin tests.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

run_step() {
    local label="$1"
    shift

    echo ""
    echo -e "${BLUE}[check-all] START:${NC} $label"
    if "$@"; then
        echo -e "${GREEN}[check-all] PASS:${NC} $label"
    else
        local status=$?
        echo -e "${RED}[check-all] FAIL:${NC} $label (exit $status)" >&2
        exit "$status"
    fi
}

cd "$ROOT_DIR" || exit 1

echo "========================================"
echo "  Fakoli Marketplace Check-All"
echo "========================================"

run_step "marketplace validation" ./scripts/validate.sh
run_step "path-resolution and hook-safety scan" ./scripts/test-path-resolution.sh
run_step "affected plugin tests: systems-thinking" bash -c 'cd plugins/systems-thinking && uv run pytest tests -q'
run_step "affected hook validation suite" ./tests/test-hooks-validation.sh

echo ""
echo -e "${GREEN}[check-all] ALL PASSED${NC}"
