#!/usr/bin/env bash
# Start the anvil-pulse dashboard server.
# Usage: start-server.sh [--project-dir <path>] [--state-dir <anvil-state-dir>]
#                        [--port <port>] [--host <bind-host>] [--url-host <host>]
#                        [--foreground] [--background]
#
# Prints one JSON line on success: {"event":"server-started","url":...,"pid":...}
#
# Options:
#   --project-dir <path>  Anvil project to watch (default: cwd). PID/log files
#                         live under <project>/.anvil-pulse/ (git-ignore it).
#   --state-dir <path>    Explicit anvil state dir containing events.jsonl
#                         (default: auto-discover).
#   --port <port>         Fixed port (default: random high port).
#   --host <bind-host>    Bind host (default 127.0.0.1).
#   --url-host <host>     Hostname shown in the returned URL.
#   --foreground          Run in the current terminal (no backgrounding).
#   --background          Force background mode (overrides auto-foreground).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PROJECT_DIR="$(pwd)"
STATE_DIR_ARG=""
PORT=""
FOREGROUND="false"
FORCE_BACKGROUND="false"
BIND_HOST="127.0.0.1"
URL_HOST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    --state-dir)   STATE_DIR_ARG="$2"; shift 2 ;;
    --port)        PORT="$2"; shift 2 ;;
    --host)        BIND_HOST="$2"; shift 2 ;;
    --url-host)    URL_HOST="$2"; shift 2 ;;
    --foreground|--no-daemon) FOREGROUND="true"; shift ;;
    --background|--daemon)    FORCE_BACKGROUND="true"; shift ;;
    *) echo "{\"error\": \"Unknown argument: $1\"}"; exit 1 ;;
  esac
done

if [[ -z "$URL_HOST" ]]; then
  if [[ "$BIND_HOST" == "127.0.0.1" || "$BIND_HOST" == "localhost" ]]; then
    URL_HOST="localhost"
  else
    URL_HOST="$BIND_HOST"
  fi
fi

# Some environments reap detached/background processes. Auto-foreground when detected.
if [[ -n "${CODEX_CI:-}" && "$FOREGROUND" != "true" && "$FORCE_BACKGROUND" != "true" ]]; then
  FOREGROUND="true"
fi
# Windows/Git Bash reaps nohup background processes. Auto-foreground when detected.
if [[ "$FOREGROUND" != "true" && "$FORCE_BACKGROUND" != "true" ]]; then
  case "${OSTYPE:-}" in
    msys*|cygwin*|mingw*) FOREGROUND="true" ;;
  esac
  if [[ -n "${MSYSTEM:-}" ]]; then
    FOREGROUND="true"
  fi
fi

PULSE_HOME="${PROJECT_DIR}/.anvil-pulse"
PID_FILE="${PULSE_HOME}/server.pid"
LOG_FILE="${PULSE_HOME}/server.log"
mkdir -p "$PULSE_HOME"

# One dashboard per project: kill any existing server recorded in the PID file.
if [[ -f "$PID_FILE" ]]; then
  old_pid=$(cat "$PID_FILE")
  kill "$old_pid" 2>/dev/null
  rm -f "$PID_FILE"
fi

cd "$SCRIPT_DIR"

ENV_VARS=(
  "PULSE_DIR=$PULSE_HOME"
  "PULSE_PROJECT_DIR=$PROJECT_DIR"
  "PULSE_HOST=$BIND_HOST"
  "PULSE_URL_HOST=$URL_HOST"
)
[[ -n "$STATE_DIR_ARG" ]] && ENV_VARS+=("PULSE_STATE_DIR=$STATE_DIR_ARG")
[[ -n "$PORT" ]] && ENV_VARS+=("PULSE_PORT=$PORT")

# Foreground mode for environments that reap detached/background processes.
if [[ "$FOREGROUND" == "true" ]]; then
  # Write PID before blocking - lets stop-server.sh and check-server.sh work.
  echo "$$" > "$PID_FILE"
  exec env "${ENV_VARS[@]}" node server.cjs
fi

# Background mode: nohup to survive shell exit; disown to leave the job table.
nohup env "${ENV_VARS[@]}" node server.cjs > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
disown "$SERVER_PID" 2>/dev/null
echo "$SERVER_PID" > "$PID_FILE"

# Wait for the server-started line (up to 5 seconds).
for i in {1..50}; do
  if grep -q "server-started" "$LOG_FILE" 2>/dev/null; then
    # Verify the server survived a short window (catches process reapers).
    alive="true"
    for _ in {1..20}; do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        alive="false"
        break
      fi
      sleep 0.1
    done
    if [[ "$alive" != "true" ]]; then
      echo "{\"error\": \"Server started but was killed. Retry in a persistent terminal with: $SCRIPT_DIR/start-server.sh --project-dir $PROJECT_DIR --foreground\"}"
      exit 1
    fi
    grep "server-started" "$LOG_FILE" | head -1
    exit 0
  fi
  sleep 0.1
done

echo '{"error": "Server failed to start within 5 seconds"}'
exit 1
