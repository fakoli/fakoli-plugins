#!/usr/bin/env bash
# Check whether the anvil-pulse dashboard server is running for a project.
# Usage: check-server.sh [--project-dir <path>]
# Prints {"running": true|false, ...} and exits 0 when running, 1 when not.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/process-identity.sh"
PROJECT_DIR="$(pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir) [[ $# -ge 2 && -n "$2" ]] || { echo '{"error":"--project-dir requires a value"}'; exit 2; }; PROJECT_DIR="$2"; shift 2 ;;
    *) echo '{"error":"unknown option"}'; exit 2 ;;
  esac
done

PROJECT_DIR="$(cd -- "$PROJECT_DIR" && pwd -P)" || exit 1

PULSE_HOME="${PROJECT_DIR}/.anvil-pulse"
PID_FILE="${PULSE_HOME}/server.pid"
LOG_FILE="${PULSE_HOME}/server.log"

if [[ ! -f "$PID_FILE" ]]; then
  echo '{"running": false, "note": "no pid file"}'
  exit 1
fi

pid=$(cat "$PID_FILE")
if ! pulse_pid_is_ours "$pid" "$PROJECT_DIR"; then
  echo '{"running":false,"note":"unverified or stale pid file"}'
  exit 1
fi

started=$(grep "server-started" "$LOG_FILE" 2>/dev/null | head -1)
if [[ -n "$started" ]]; then
  echo "$started" | sed 's/"event": *"server-started"/"running": true/'
else
  echo "{\"running\": true, \"pid\": $pid, \"note\": \"no server-started line in log (foreground mode?)\"}"
fi
exit 0
