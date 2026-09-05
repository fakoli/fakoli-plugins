#!/usr/bin/env bash
# Fail-open context hook: resolve an available Python and emit SessionStart JSON.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for interpreter in python3 python; do
  if "$interpreter" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    "$interpreter" "$script_dir/session-start.py" || printf '{}\n'
    exit 0
  fi
done
printf '{}\n'
exit 0
