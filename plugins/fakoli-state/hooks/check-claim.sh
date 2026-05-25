#!/usr/bin/env bash

# check-claim.sh — PreToolUse hook for fakoli-state (Phase 4)
# Fires before Edit, Write, or NotebookEdit tool calls.
# Warns (non-blocking) when there are active claims and the agent modifies a file,
# so the agent can verify the file is in scope before proceeding.
#
# Rules: no set -e, no piped grep, always exit 0, complete in < 200ms.
# Performance: only shells out to the CLI when .fakoli-state/ exists; otherwise fast-paths.
#
# Claude Code hook payload arrives on stdin as JSON.
# Relevant fields (Phase 4 minimal extraction):
#   .tool_input.path   — file being modified (Edit, Write)
#   .tool_name         — e.g. "Edit", "Write", "NotebookEdit"
#   .session_id        — session identifier (used as actor proxy when no claim actor available)

STATE_DIR=".fakoli-state"

# Fast-path: no project state, nothing to check.
if [ ! -d "$STATE_DIR" ]; then
  exit 0
fi

# Read and parse stdin payload (best-effort; failures are silent).
PAYLOAD=""
if [ -t 0 ]; then
  # stdin is a terminal — no payload (e.g. manual smoke-test invocation)
  PAYLOAD="{}"
else
  PAYLOAD=$(cat)
fi

# Extract the file path being modified.
# Try .tool_input.path first (Edit, Write); fall back to .tool_input.notebook_path (NotebookEdit).
FILE_PATH=""
if command -v python3 >/dev/null 2>&1; then
  FILE_PATH=$(printf '%s' "$PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('path') or ti.get('notebook_path') or '')
except Exception:
    print('')
" 2>/dev/null)
fi

# Extract the actor identifier from the payload (session_id as proxy).
ACTOR=""
if command -v python3 >/dev/null 2>&1; then
  ACTOR=$(printf '%s' "$PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id') or '')
except Exception:
    print('')
" 2>/dev/null)
fi

# Normalise: if FILE_PATH is empty, we can't check anything — exit silently.
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# If the file is outside the project tree (absolute path not under cwd), skip silently.
# We detect "outside" by checking whether FILE_PATH starts with / AND does not start
# with the resolved cwd.  Relative paths are always considered in-project.
if [ "${FILE_PATH#/}" != "$FILE_PATH" ]; then
  # FILE_PATH is absolute
  CWD="$(pwd)"
  if [ "${FILE_PATH#"$CWD/"}" = "$FILE_PATH" ] && [ "$FILE_PATH" != "$CWD" ]; then
    # Absolute path that does not reside under cwd — skip silently.
    exit 0
  fi
fi

# Shell out to the CLI to get current status.
# Expected output from `fakoli-state status --hook-format`:
#   active-claims:<N> ready-tasks:<N> blockers:<N> prd-status:<STATUS>
# We only need the active-claims count for Phase 4.
CLI="${CLAUDE_PLUGIN_ROOT}/bin/fakoli-state"

if [ ! -x "$CLI" ]; then
  # CLI not available — degrade silently; never break the session.
  exit 0
fi

STATUS_OUTPUT=$("$CLI" status --hook-format 2>/dev/null)
STATUS_EXIT=$?

if [ "$STATUS_EXIT" -ne 0 ] || [ -z "$STATUS_OUTPUT" ]; then
  # CLI failed or returned nothing (DB locked, not yet wired, etc.) — degrade silently.
  exit 0
fi

# Extract active-claims count.
# Example line: active-claims:2 ready-tasks:7 blockers:0 prd-status:approved
ACTIVE_CLAIMS=""
# Use parameter expansion to avoid piped grep.
for TOKEN in $STATUS_OUTPUT; do
  case "$TOKEN" in
    active-claims:*)
      ACTIVE_CLAIMS="${TOKEN#active-claims:}"
      ;;
  esac
done

# Only warn when there ARE active claims.
if [ -z "$ACTIVE_CLAIMS" ] || [ "$ACTIVE_CLAIMS" = "0" ]; then
  exit 0
fi

# Emit a single-line warning to stderr.  Non-blocking — does NOT prevent the edit.
# Phase 5 will add per-file scope checking via `fakoli-state hook check-claim --file <PATH> --actor <ACTOR>`.
ACTOR_DISPLAY="${ACTOR:-unknown}"
printf '[fakoli-state:check-claim] %d active claim(s) exist — verify "%s" is within your claimed scope before editing (actor: %s)\n' \
  "$ACTIVE_CLAIMS" "$FILE_PATH" "$ACTOR_DISPLAY" >&2

exit 0
