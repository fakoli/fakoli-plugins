#!/usr/bin/env bash
#
# test-critic-gate-hooks.sh - Tests the fakoli-flow critic-gate enforcement hooks
#
# Usage: ./tests/test-critic-gate-hooks.sh
#
# Exercises the gate state machine end-to-end: arming, writer-completion
# pending, dispatch denial, critic clearance, fix-cycle re-pending, escape
# hatches, and fail-open behavior on malformed input.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TRACK="$ROOT_DIR/plugins/fakoli-flow/hooks/gate-track.sh"
CHECK="$ROOT_DIR/plugins/fakoli-flow/hooks/gate-check.sh"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
cd "$WORKDIR" || exit 1

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    echo -e "  ${GREEN}PASS${NC} $1"
    ((TESTS_PASSED++)) || true
}

fail() {
    echo -e "  ${RED}FAIL${NC} $1"
    ((TESTS_FAILED++)) || true
}

dispatch_json() {
    printf '{"tool_input":{"subagent_type":"%s"}}' "$1"
}

is_blocked() {
    # A real block must satisfy the PreToolUse contract Claude Code enforces:
    # hookSpecificOutput.permissionDecision == "deny". The legacy top-level
    # decision field alone is NOT sufficient (it is ignored by current
    # Claude Code versions — checking only for it would let the gate be
    # silently inoperative while tests pass).
    python3 -c "
import json, sys
d = json.load(sys.stdin)
h = d.get('hookSpecificOutput', {})
ok = (h.get('hookEventName') == 'PreToolUse'
      and h.get('permissionDecision') == 'deny'
      and bool(h.get('permissionDecisionReason')))
sys.exit(0 if ok else 1)
" 2>/dev/null
}

# --- 1. Unarmed: everything passes through silently
OUT=$(dispatch_json "fakoli-crew:guido" | bash "$CHECK")
[ -z "$OUT" ] && pass "unarmed run does not gate dispatches" || fail "unarmed run emitted output: $OUT"

dispatch_json "fakoli-crew:welder" | bash "$TRACK"
[ ! -f .fakoli/gate-state.json ] && pass "unarmed run does not track state" || fail "unarmed run wrote gate-state.json"

# --- 2. Armed: writer completion sets gate pending
mkdir -p .fakoli && echo "test-run" > .fakoli/gate-armed
dispatch_json "fakoli-crew:welder" | bash "$TRACK"
grep -q '"pending": true' .fakoli/gate-state.json 2>/dev/null \
    && pass "writer completion sets gate pending" \
    || fail "writer completion did not set pending"

# --- 3. Pending gate blocks non-critic/welder dispatch
OUT=$(dispatch_json "fakoli-crew:guido" | bash "$CHECK")
echo "$OUT" | is_blocked && pass "pending gate blocks guido dispatch" || fail "guido dispatch was not blocked"

OUT=$(dispatch_json "fakoli-crew:sentinel" | bash "$CHECK")
echo "$OUT" | is_blocked && pass "pending gate blocks sentinel dispatch" || fail "sentinel dispatch was not blocked"

# --- 4. Pending gate allows critic (the gate) and welder (fix cycles)
OUT=$(dispatch_json "fakoli-crew:critic" | bash "$CHECK")
[ -z "$OUT" ] && pass "pending gate allows critic dispatch" || fail "critic dispatch was blocked"

OUT=$(dispatch_json "fakoli-crew:welder" | bash "$CHECK")
[ -z "$OUT" ] && pass "pending gate allows welder dispatch (fix cycle)" || fail "welder dispatch was blocked"

# --- 5. Critic completion clears the gate
dispatch_json "fakoli-crew:critic" | bash "$TRACK"
grep -q '"pending": false' .fakoli/gate-state.json 2>/dev/null \
    && pass "critic completion clears the gate" \
    || fail "critic completion did not clear pending"

OUT=$(dispatch_json "fakoli-crew:guido" | bash "$CHECK")
[ -z "$OUT" ] && pass "cleared gate allows next-wave dispatch" || fail "cleared gate still blocked guido"

# --- 6. Fix-cycle invariant: welder completion re-pends after a clearance
dispatch_json "fakoli-crew:welder" | bash "$TRACK"
grep -q '"pending": true' .fakoli/gate-state.json 2>/dev/null \
    && pass "welder fix completion re-pends the gate (forces critic re-review)" \
    || fail "welder fix completion did not re-pend"

# --- 7. Escape hatches
OUT=$(dispatch_json "fakoli-crew:guido" | FAKOLI_FLOW_NO_GATE=1 bash "$CHECK")
[ -z "$OUT" ] && pass "FAKOLI_FLOW_NO_GATE=1 bypasses the gate" || fail "env escape hatch did not bypass"

rm .fakoli/gate-armed
OUT=$(dispatch_json "fakoli-crew:guido" | bash "$CHECK")
[ -z "$OUT" ] && pass "removing gate-armed disarms enforcement" || fail "disarmed gate still blocked"
echo "test-run" > .fakoli/gate-armed

# --- 8. Fail-open on malformed input
OUT=$(echo 'not json' | bash "$CHECK"); RC=$?
[ -z "$OUT" ] && [ "$RC" -eq 0 ] && pass "malformed input fails open in gate-check" || fail "gate-check did not fail open"

echo 'not json' | bash "$TRACK"; RC=$?
[ "$RC" -eq 0 ] && pass "malformed input fails open in gate-track" || fail "gate-track did not fail open"

# --- 9. JSON-injection-shaped subagent_type cannot corrupt the state file
printf '{"tool_input":{"subagent_type":"fakoli-crew:welder\\" , \\\\evil"}}' | bash "$TRACK"
python3 -c "import json; json.load(open('.fakoli/gate-state.json'))" 2>/dev/null \
    && pass "quote/backslash in subagent_type still produces valid JSON state" \
    || fail "state file corrupted by special characters in subagent_type"

# --- 10. Stale-arm expiry (abandoned-run protection): armed file >24h old is ignored
dispatch_json "fakoli-crew:welder" | bash "$TRACK"   # ensure pending=true with fresh arm
touch -t 202601010000 .fakoli/gate-armed              # backdate arming to Jan 1 (>24h)
OUT=$(dispatch_json "fakoli-crew:guido" | bash "$CHECK"); RC=$?
[ -z "$OUT" ] && [ "$RC" -eq 0 ] \
    && pass "stale armed file (>24h) fails open in gate-check" \
    || fail "stale armed file still blocked dispatch"

rm -f .fakoli/gate-state.json
dispatch_json "fakoli-crew:welder" | bash "$TRACK"
[ ! -f .fakoli/gate-state.json ] \
    && pass "stale armed file (>24h) is ignored by gate-track" \
    || fail "gate-track wrote state despite stale arming"

# --- Summary
echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo -e "${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Failed:${NC} $TESTS_FAILED"
echo "========================================"

[ "$TESTS_FAILED" -eq 0 ]
