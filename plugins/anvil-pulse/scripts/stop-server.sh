#!/usr/bin/env bash
# Stop the anvil-pulse dashboard server for a project.
# Usage: stop-server.sh [--project-dir <path>]

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

PID_FILE="${PROJECT_DIR}/.anvil-pulse/server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo '{"event": "server-stopped", "note": "no pid file; nothing to stop"}'
  exit 0
fi

pid=$(cat "$PID_FILE")

# Guard against PID recycling: refuse to kill a process that no longer looks
# like the dashboard (node/server.cjs) - a crashed server leaves a stale pid
# file and the OS may reassign the number to an unrelated process.
if ! pulse_pid_is_ours "$pid" "$PROJECT_DIR"; then
  rm -f "$PID_FILE"
  echo '{"event":"server-stopped","note":"unverified or stale PID; no process signalled"}'
  exit 0
fi

if kill "$pid" 2>/dev/null; then
  # Give it a moment to exit cleanly, then force.
  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  pulse_pid_is_ours "$pid" "$PROJECT_DIR" && kill -9 "$pid" 2>/dev/null
  rm -f "$PID_FILE"
  echo "{\"event\": \"server-stopped\", \"pid\": $pid}"
else
  rm -f "$PID_FILE"
  echo "{\"event\": \"server-stopped\", \"note\": \"process $pid was not running; cleaned pid file\"}"
fi
