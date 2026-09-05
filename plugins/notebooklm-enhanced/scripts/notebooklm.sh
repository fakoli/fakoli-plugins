#!/usr/bin/env bash
# Lock-backed CLI entrypoint; works independently of the user's current project.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --frozen --project "$SCRIPT_DIR" notebooklm "$@"
