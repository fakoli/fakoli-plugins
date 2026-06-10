#!/usr/bin/env bash
# PostToolUse hook (Task|Agent): tracks critic-gate state during an active
# /flow:execute run.
#
# Armed only while .fakoli/gate-armed exists in the project — created by the
# execute skill at run start, removed at run end. When a code-writing crew
# agent (guido, smith, welder) completes, the gate becomes PENDING. When the
# critic completes a review pass, the gate clears. gate-check.sh (PreToolUse)
# denies dispatch of next-wave agents while the gate is pending.
#
# A welder fix-cycle completion re-pends the gate, which forces the critic
# re-review that the fix cycle requires — the two transitions together enforce
# the invariant "no new wave starts after a write without a critic pass that
# happened after that write."
#
# Fail-open by design: any parse failure or missing dependency exits 0.

ARMED_FILE=".fakoli/gate-armed"
STATE_FILE=".fakoli/gate-state.json"

[ "${FAKOLI_FLOW_NO_GATE:-0}" = "1" ] && exit 0
[ -f "$ARMED_FILE" ] || exit 0

# Ignore arming older than 24h (abandoned run) — fail open.
if [ -n "$(find "$ARMED_FILE" -mmin +1440 2>/dev/null)" ]; then
  exit 0
fi

INPUT=$(cat)
SUBAGENT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('subagent_type', ''))
except Exception:
    print('')
" 2>/dev/null)

[ -n "$SUBAGENT" ] || exit 0

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# State writes go through json.dumps so a subagent_type containing quotes or
# backslashes can never produce malformed JSON (which would make gate-check
# silently fail open).
write_state() {
  python3 -c "
import json, sys
print(json.dumps({'pending': sys.argv[1] == 'true', sys.argv[2]: sys.argv[3], 'updated': sys.argv[4]}))
" "$1" "$2" "$3" "$NOW" > "${STATE_FILE}.tmp" 2>/dev/null && mv "${STATE_FILE}.tmp" "$STATE_FILE"
}

case "$SUBAGENT" in
  *guido|*smith|*welder)
    write_state true last_writer "$SUBAGENT"
    ;;
  *critic)
    write_state false cleared_by critic
    ;;
esac

exit 0
