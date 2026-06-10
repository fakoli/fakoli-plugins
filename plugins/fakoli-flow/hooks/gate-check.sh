#!/usr/bin/env bash
# PreToolUse hook (Task|Agent): mechanically enforces the fakoli-flow critic
# gate. Companion to gate-track.sh, which maintains the gate state.
#
# Active only while BOTH are true:
#   - .fakoli/gate-armed exists (an execute run is live), and
#   - .fakoli/gate-state.json shows pending=true (a code-writing wave
#     completed and the critic has not reviewed it yet).
#
# While pending, only the critic (the gate itself) and welder (fix cycles
# and verification fixes) may be dispatched. Everything else is denied with
# an explanation of how to proceed.
#
# Escape hatches: FAKOLI_FLOW_NO_GATE=1, or rm .fakoli/gate-armed.
# Fail-open by design: any parse failure or missing dependency exits 0.

ARMED_FILE=".fakoli/gate-armed"
STATE_FILE=".fakoli/gate-state.json"

[ "${FAKOLI_FLOW_NO_GATE:-0}" = "1" ] && exit 0
[ -f "$ARMED_FILE" ] || exit 0
[ -f "$STATE_FILE" ] || exit 0

# Ignore arming older than 24h (abandoned run) — fail open.
if [ -n "$(find "$ARMED_FILE" -mmin +1440 2>/dev/null)" ]; then
  exit 0
fi

INPUT=$(cat)
PARSED=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sub = data.get('tool_input', {}).get('subagent_type', '')
except Exception:
    sub = ''
try:
    with open('.fakoli/gate-state.json') as f:
        pending = bool(json.load(f).get('pending'))
except Exception:
    pending = False
print(sub + '|' + ('1' if pending else '0'))
" 2>/dev/null)

SUBAGENT="${PARSED%|*}"
PENDING="${PARSED##*|}"

[ "$PENDING" = "1" ] || exit 0
[ -n "$SUBAGENT" ] || exit 0

case "$SUBAGENT" in
  *critic|*welder)
    exit 0
    ;;
esac

# Emit both the current PreToolUse contract (hookSpecificOutput.permissionDecision)
# and the legacy top-level decision/reason fields for older Claude Code versions.
cat <<'EOF'
{
  "decision": "block",
  "reason": "fakoli-flow critic gate is PENDING: a code-writing wave completed and the critic has not reviewed it yet. Dispatch fakoli-crew:critic on the wave's modified files (or fakoli-crew:welder for verification/fix cycles) before dispatching any other agent. If this block is wrong for your situation, disarm enforcement with: rm .fakoli/gate-armed (or set FAKOLI_FLOW_NO_GATE=1).",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "fakoli-flow critic gate is PENDING: a code-writing wave completed and the critic has not reviewed it yet. Dispatch fakoli-crew:critic on the wave's modified files (or fakoli-crew:welder for verification/fix cycles) before dispatching any other agent. If this block is wrong for your situation, disarm enforcement with: rm .fakoli/gate-armed (or set FAKOLI_FLOW_NO_GATE=1)."
  }
}
EOF
exit 0
