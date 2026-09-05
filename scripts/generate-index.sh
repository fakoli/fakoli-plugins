#!/usr/bin/env bash
# Regenerate both host catalogs and derived registry; --check never writes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/catalog.py" "$@"
