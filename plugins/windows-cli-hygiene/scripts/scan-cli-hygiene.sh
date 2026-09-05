#!/usr/bin/env bash
# Stable shell entrypoint for the portable scanner.
set -uo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for interpreter in python3 python; do
  if "$interpreter" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    exec "$interpreter" "$script_dir/scan_cli_hygiene.py" "$@"
  fi
done
printf '%s\n' 'cli-hygiene: Python 3.10+ is required' >&2
exit 2
