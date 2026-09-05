#!/usr/bin/env bash
# Shared by start/check/stop. A bare PID or any node process is insufficient.
pulse_pid_is_ours() {
  local pid="$1" project="$2" command_line
  [[ "$pid" =~ ^[1-9][0-9]*$ && "$pid" -gt 1 ]] || return 1
  command_line=$(ps -p "$pid" -o args= 2>/dev/null) || return 1
  [[ "$command_line" == *"$SCRIPT_DIR/server.cjs"* && "$command_line" == *"--pulse-project $project" ]]
}
