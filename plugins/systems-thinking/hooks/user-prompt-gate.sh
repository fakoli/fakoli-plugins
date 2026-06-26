#!/bin/bash
# Only inject the extraction/synthesis reminder when a systems-thinking
# skill or agent is being explicitly invoked — not on casual mentions.
#
# Reads JSON from stdin (Claude Code hook system).
# Outputs a prompt message to stdout only when relevant.
# Exit 0 = always approve (never block user input).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/discover-components.sh"

# jq is required to parse hook input — skip silently if missing
# (SessionStart hook will have already warned the user)
if [ "$JQ_AVAILABLE" = "false" ]; then
  exit 0
fi

input=$(cat)
user_prompt=$(echo "$input" | jq -r '.prompt // .user_prompt // empty')
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

REMINDER="Before proceeding, remember: separate extraction from synthesis. Preserve source anchors (file, section, page) on every finding. Do not collapse raw evidence into inferred conclusions until extraction is complete."

# Only match explicit slash-command invocations in the user's prompt.
# This avoids false positives when users paste code reviews or discuss
# plugin internals that happen to mention component names.
if [ -n "$SKILL_NAMES" ]; then
  SLASH_PATTERN="^/($SKILL_NAMES)"
  if echo "$user_prompt" | grep -qiE "$SLASH_PATTERN" 2>/dev/null; then
    echo "$REMINDER"
    exit 0
  fi
fi

# Check if a systems-thinking workflow is already active in the transcript
# (actual tool invocations, not casual mentions)
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  if grep -qE "$INVOCATION_PATTERNS" "$transcript_path" 2>/dev/null; then
    echo "$REMINDER"
    exit 0
  fi
fi

# Not a systems-thinking workflow — no prompt injection needed
exit 0
