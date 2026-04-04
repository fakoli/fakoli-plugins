#!/usr/bin/env bash
# Stop the fakoli-flow brainstorm visual companion server.
# Usage: stop-server.sh <session-dir>
#
# Reads the PID from <session-dir>/state/server.pid, kills the process,
# and removes the PID file. Temporary sessions (/tmp) are deleted entirely.
# Sessions created with --project-dir are left in place so mockup files persist.

SESSION_DIR="${1:-}"

if [[ -z "$SESSION_DIR" ]]; then
  echo '{"error": "Usage: stop-server.sh <session-dir>"}'
  exit 1
fi

STATE_DIR="${SESSION_DIR}/state"
PID_FILE="${STATE_DIR}/server.pid"
STOP_MARKER="${STATE_DIR}/server-stopped"

if [[ ! -f "$PID_FILE" ]]; then
  echo '{"status": "not-running", "reason": "no PID file found"}'
  exit 0
fi

SERVER_PID=$(cat "$PID_FILE")

if [[ -z "$SERVER_PID" ]]; then
  echo '{"status": "not-running", "reason": "PID file is empty"}'
  rm -f "$PID_FILE"
  exit 0
fi

# Attempt graceful termination
kill "$SERVER_PID" 2>/dev/null
STATUS=$?

# Wait briefly for the process to exit
for _ in {1..20}; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  sleep 0.1
done

# Force kill if still alive
if kill -0 "$SERVER_PID" 2>/dev/null; then
  kill -9 "$SERVER_PID" 2>/dev/null
fi

# Clean up PID file and write stop marker so check-server.sh reads "dead"
rm -f "$PID_FILE"
touch "$STOP_MARKER"

# Remove the entire session directory only for /tmp sessions
if [[ "$SESSION_DIR" == /tmp/* ]]; then
  rm -rf "$SESSION_DIR"
  echo '{"status": "stopped", "cleaned": true}'
else
  echo "{\"status\": \"stopped\", \"session_dir\": \"$SESSION_DIR\", \"cleaned\": false}"
fi
