#!/usr/bin/env bash
# Check whether the anvil-pulse dashboard server is running for a project.
# Usage: check-server.sh [--project-dir <path>]
# Prints {"running": true|false, ...} and exits 0 when running, 1 when not.

PROJECT_DIR="$(pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    *) echo "{\"error\": \"Unknown argument: $1\"}"; exit 1 ;;
  esac
done

PULSE_HOME="${PROJECT_DIR}/.anvil-pulse"
PID_FILE="${PULSE_HOME}/server.pid"
LOG_FILE="${PULSE_HOME}/server.log"

if [[ ! -f "$PID_FILE" ]]; then
  echo '{"running": false, "note": "no pid file"}'
  exit 1
fi

pid=$(cat "$PID_FILE")
if ! kill -0 "$pid" 2>/dev/null; then
  echo "{\"running\": false, \"note\": \"stale pid file (pid $pid not alive)\"}"
  exit 1
fi

started=$(grep "server-started" "$LOG_FILE" 2>/dev/null | head -1)
if [[ -n "$started" ]]; then
  echo "$started" | sed 's/"event": *"server-started"/"running": true/'
else
  echo "{\"running\": true, \"pid\": $pid, \"note\": \"no server-started line in log (foreground mode?)\"}"
fi
exit 0
