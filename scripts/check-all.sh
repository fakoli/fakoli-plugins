#!/usr/bin/env bash
#
# check-all.sh - Run the combined marketplace verification gate.
#
# The gate is intentionally sequential so failures stop at the first broken
# layer: marketplace metadata, path resolution, then affected plugin tests.

set -uo pipefail

# Ensure authoritative YAML/schema parsing is available to shell subprocesses.
if [ "${FAKOLI_CHECK_ENV_READY:-}" != 1 ]; then
    command -v uv >/dev/null 2>&1 || { echo "check-all: uv is required" >&2; exit 127; }
    export FAKOLI_CHECK_ENV_READY=1
    exec uv run --no-project --with 'PyYAML>=6,<7' --with 'jsonschema>=4.23,<5' bash "$0" "$@"
fi

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
run_step "native packages, skill links and catalogs" uv run --script scripts/validate.py
run_step "offline package behavior" ./scripts/test.sh
run_step "affected hook validation suite" ./tests/test-hooks-validation.sh
run_step "roster audit guards" ./tests/test-roster-audit.sh
run_step "lint-frontmatter unit tests" ./tests/test-lint-frontmatter.sh
run_step "registry consistency" ./scripts/check-registry-drift.sh

echo ""
echo -e "${GREEN}[check-all] ALL PASSED${NC}"
