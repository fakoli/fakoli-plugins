#!/usr/bin/env bash
# Stop the anvil-pulse dashboard server for a project.
# Usage: stop-server.sh [--project-dir <path>]

PROJECT_DIR="$(pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    *) echo "{\"error\": \"Unknown argument: $1\"}"; exit 1 ;;
  esac
done

PID_FILE="${PROJECT_DIR}/.anvil-pulse/server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo '{"event": "server-stopped", "note": "no pid file; nothing to stop"}'
  exit 0
fi

pid=$(cat "$PID_FILE")

# Guard against PID recycling: refuse to kill a process that no longer looks
# like the dashboard (node/server.cjs) - a crashed server leaves a stale pid
# file and the OS may reassign the number to an unrelated process.
cmd=$(ps -p "$pid" -o args= 2>/dev/null || ps -p "$pid" 2>/dev/null)
if [[ -n "$cmd" ]] && ! echo "$cmd" | grep -qE "node|server\.cjs"; then
  rm -f "$PID_FILE"
  echo "{\"event\": \"server-stopped\", \"note\": \"pid $pid belongs to an unrelated process now; cleaned stale pid file without killing\"}"
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
  kill -9 "$pid" 2>/dev/null
  rm -f "$PID_FILE"
  echo "{\"event\": \"server-stopped\", \"pid\": $pid}"
else
  rm -f "$PID_FILE"
  echo "{\"event\": \"server-stopped\", \"note\": \"process $pid was not running; cleaned pid file\"}"
fi
