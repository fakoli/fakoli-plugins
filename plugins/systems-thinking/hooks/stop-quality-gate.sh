#!/bin/bash
# Gate script for the Stop hook: only trigger the quality check
# when systems-thinking agents or skills were actually invoked.
#
# Reads JSON from stdin (provided by Claude Code hook system).
# Checks the transcript for actual tool invocations (not casual mentions).
# Exit 0 = approve (no quality check needed)
# Exit 2 + stderr = block (quality sections missing)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/discover-components.sh"

# jq is required to parse hook input — approve silently if missing
# (SessionStart hook will have already warned the user)
if [ "$JQ_AVAILABLE" = "false" ]; then
  exit 0
fi

input=$(cat)
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')
last_assistant_message=$(echo "$input" | jq -r '.last_assistant_message // empty')

# If no transcript available, approve silently
if [ -z "$transcript_path" ] || [ ! -f "$transcript_path" ]; then
  exit 0
fi

# Check if any systems-thinking component was actually invoked
if ! grep -qE "$INVOCATION_PATTERNS" "$transcript_path" 2>/dev/null; then
  # No actual invocation — approve, skip quality check
  exit 0
fi

# Systems-thinking was invoked — check for required quality sections
has_quality_signal() {
  local pattern="$1"
  if [ -n "$last_assistant_message" ]; then
    printf '%s\n' "$last_assistant_message" | grep -qiE "$pattern" 2>/dev/null
  else
    grep -qiE "$pattern" "$transcript_path" 2>/dev/null
  fi
}

missing=""
has_quality_signal "assumption" || missing="${missing}assumptions, "
has_quality_signal "risk" || missing="${missing}risks, "
has_quality_signal "unresolved" || missing="${missing}unresolved questions, "
has_quality_signal "next step|next check|recommended" || missing="${missing}next steps, "

if [ -n "$missing" ]; then
  missing="${missing%, }"  # trim trailing comma
  echo "{\"decision\": \"block\", \"reason\": \"Systems-thinking analysis is missing: ${missing}. Add these sections before completing.\"}" >&2
  exit 2
fi

# All quality sections present
exit 0
