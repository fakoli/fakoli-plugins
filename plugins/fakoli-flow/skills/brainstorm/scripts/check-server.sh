#!/usr/bin/env bash
# Check whether the fakoli-flow brainstorm server is alive.
# Usage: check-server.sh <state-dir>
#
# Reads <state-dir>/server.pid and uses kill -0 to test if the process exists.
# Outputs exactly one word:
#   alive  — process is running
#   dead   — PID file missing, empty, or process not found
#
# The brainstorm skill runs this before every HTML write. If it outputs "dead",
# the skill restarts the server automatically before continuing.

STATE_DIR="${1:-}"

if [[ -z "$STATE_DIR" ]]; then
  echo "dead"
  exit 1
fi

PID_FILE="${STATE_DIR}/server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "dead"
  exit 0
fi

SERVER_PID=$(cat "$PID_FILE" 2>/dev/null | tr -d '[:space:]')

if [[ -z "$SERVER_PID" ]]; then
  echo "dead"
  exit 0
fi

# kill -0 tests process existence without sending a signal
if kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "alive"
else
  echo "dead"
fi
