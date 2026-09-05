#!/usr/bin/env bash
# Compatibility entrypoint; Python handles NUL-delimited Git paths and JSON.
set -uo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for interpreter in python3 python; do
  if "$interpreter" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    exec "$interpreter" "$script_dir/gate_router.py" "$@"
  fi
done
printf '%s\n' 'gate-router: Python 3.10+ is required' >&2
exit 2
