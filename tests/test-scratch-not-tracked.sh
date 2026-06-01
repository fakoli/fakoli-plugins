#!/usr/bin/env bash
#
# test-scratch-not-tracked.sh — Invariant check for P10 (scratch isolation)
#
# Asserts three things:
#   1. A representative path under .fakoli/ is git-ignored
#      (git check-ignore exits 0 for .fakoli/runs/x/agent-y-status.md).
#   2. No file under .fakoli/ is tracked by git
#      (git ls-files .fakoli/ returns nothing).
#   3. No agent*-status.md scratch is tracked anywhere under docs/plans/
#      (guards the legacy cleanup from regressing).
#
# Usage: ./tests/test-scratch-not-tracked.sh
#
# Exits 0 on full PASS, non-zero on any FAIL.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

PASS_COUNT=0
FAIL_COUNT=0

pass() {
    echo "  PASS $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo "  FAIL $1"
    echo "       $2"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

echo "========================================"
echo "  Scratch Isolation Invariant (P10)"
echo "========================================"
echo ""

# ── Check 1: representative path is git-ignored ──────────────────────────────
PROBE=".fakoli/runs/x/agent-y-status.md"

if git -C "$ROOT_DIR" check-ignore -q "$PROBE" 2>/dev/null; then
    pass "$PROBE is git-ignored"
else
    fail "$PROBE is NOT git-ignored" \
         "Add '.fakoli/' to .gitignore — scratch run state must never be committed."
fi

# ── Check 2: no .fakoli/ path is currently tracked ───────────────────────────
TRACKED=$(git -C "$ROOT_DIR" ls-files ".fakoli/" 2>/dev/null)

if [[ -z "$TRACKED" ]]; then
    pass "git ls-files .fakoli/ returns nothing (no scratch tracked)"
else
    fail "git ls-files .fakoli/ returned tracked files" \
         "Tracked: $TRACKED — remove with 'git rm -r --cached .fakoli/'"
fi

# ── Check 3: no agent status scratch tracked under docs/plans/ ───────────────
LEGACY=$(git -C "$ROOT_DIR" ls-files '**/docs/plans/agent*-status.md' 'docs/plans/agent*-status.md' 2>/dev/null)

if [[ -z "$LEGACY" ]]; then
    pass "no agent*-status.md tracked under docs/plans/"
else
    fail "agent status scratch is tracked under docs/plans/" \
         "Tracked: $LEGACY — untrack with 'git rm --cached' (gitignored scratch)."
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"
echo "========================================"

if [[ $FAIL_COUNT -gt 0 ]]; then
    exit 1
fi
exit 0
