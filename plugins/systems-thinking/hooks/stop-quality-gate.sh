#!/bin/bash
# Gate script for the Stop hook: only trigger the quality check
# when systems-thinking agents or skills were actually invoked.
#
# Reads JSON from stdin (provided by Claude Code hook system).
# Checks the transcript for actual tool invocations (not casual mentions).
# Exit 0 = approve (no quality check needed)
# Exit 2 + stderr = block (quality sections missing)
#
# Spawn-frugal: bash builtins plus a single jq call and the transcript grep
# (each subprocess costs 100-700ms under Git Bash on Windows).

set -uo pipefail

# Parameter expansion instead of $(cd ... && pwd) — avoids two subshell spawns
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[ "$SCRIPT_DIR" = "${BASH_SOURCE[0]}" ] && SCRIPT_DIR="."
source "$SCRIPT_DIR/discover-components.sh"

# Read all of stdin without spawning cat (read returns non-zero at EOF)
IFS= read -r -d '' input || true

# One jq call extracts both fields; @tsv escapes embedded tabs/newlines so
# `read` consumes exactly one line. Escaped newlines do not affect the
# word-presence checks below. If jq is missing or parsing fails, approve
# silently (the SessionStart hook has already warned about missing jq).
fields=$(jq -r '[(.transcript_path // ""), (.last_assistant_message // "")] | @tsv' <<< "$input" 2>/dev/null) || exit 0
IFS=$'\t' read -r transcript_path last_assistant_message <<< "$fields"

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
shopt -s nocasematch
has_quality_signal() {
  local pattern="$1"
  if [ -n "$last_assistant_message" ]; then
    [[ "$last_assistant_message" =~ $pattern ]]
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
