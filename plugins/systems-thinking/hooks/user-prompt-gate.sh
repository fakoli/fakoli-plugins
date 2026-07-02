#!/bin/bash
# Only inject the extraction/synthesis reminder when a systems-thinking
# skill or agent is being explicitly invoked — not on casual mentions.
#
# Reads JSON from stdin (Claude Code hook system).
# Outputs a prompt message to stdout only when relevant.
# Exit 0 = always approve (never block user input).
#
# Runs on EVERY user prompt, so it is spawn-frugal: bash builtins plus a
# single jq call (each subprocess costs 100-700ms under Git Bash on Windows).

set -uo pipefail

# Parameter expansion instead of $(cd ... && pwd) — avoids two subshell spawns
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[ "$SCRIPT_DIR" = "${BASH_SOURCE[0]}" ] && SCRIPT_DIR="."
source "$SCRIPT_DIR/discover-components.sh"

# Read all of stdin without spawning cat (read returns non-zero at EOF)
IFS= read -r -d '' input || true

# One jq call extracts both fields; @tsv escapes embedded tabs/newlines so
# `read` consumes exactly one line and the tab separator stays unambiguous.
# If jq is missing or parsing fails, approve silently (the SessionStart hook
# has already warned the user about missing jq).
fields=$(jq -r '[(.prompt // .user_prompt // ""), (.transcript_path // "")] | @tsv' <<< "$input" 2>/dev/null) || exit 0
IFS=$'\t' read -r user_prompt transcript_path <<< "$fields"

REMINDER="Before proceeding, remember: separate extraction from synthesis. Preserve source anchors (file, section, page) on every finding. Do not collapse raw evidence into inferred conclusions until extraction is complete."

# Only match explicit slash-command invocations in the user's prompt.
# This avoids false positives when users paste code reviews or discuss
# plugin internals that happen to mention component names.
if [ -n "$SKILL_NAMES" ]; then
  shopt -s nocasematch
  if [[ "$user_prompt" =~ ^/($SKILL_NAMES) ]]; then
    echo "$REMINDER"
    exit 0
  fi
  shopt -u nocasematch
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
