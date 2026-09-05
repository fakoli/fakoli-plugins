#!/usr/bin/env bash
# CLI and MCP share one locked runtime environment. No project-state writes here.
set -uo pipefail
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1
if ! command -v uv >/dev/null 2>&1; then
    printf 'fakoli-state: uv is required: https://docs.astral.sh/uv/getting-started/installation/\n' >&2
    exit 127
fi
[ -f "$BIN_DIR/uv.lock" ] || { printf 'fakoli-state: package is missing uv.lock\n' >&2; exit 1; }
ENV_KEY="$(printf '%s' "$BIN_DIR" | cksum | awk '{print $1}')" || exit 1
export UV_PROJECT_ENVIRONMENT="${FAKOLI_STATE_ENVIRONMENT:-${XDG_CACHE_HOME:-$HOME/.cache}/fakoli-state/envs/$ENV_KEY}"
# --locked rejects metadata drift instead of editing the installed lockfile.
# uv performs synchronization once; failure is the process exit, never ignored.
case "${FAKOLI_STATE_EXTRAS:-}" in
    '') set -- python -m "$@" ;;
    custom|bedrock|all-providers) set -- --extra "$FAKOLI_STATE_EXTRAS" python -m "$@" ;;
    *) printf 'fakoli-state: FAKOLI_STATE_EXTRAS must be custom, bedrock, or all-providers\n' >&2; exit 2 ;;
esac
exec uv run --quiet --locked --no-dev --project "$BIN_DIR" "$@"
