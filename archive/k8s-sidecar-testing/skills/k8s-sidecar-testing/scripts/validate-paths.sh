#!/usr/bin/env bash
# Installed skill entrypoint; run with --help for current arguments.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/sidecar.py" validate-paths "$@"
