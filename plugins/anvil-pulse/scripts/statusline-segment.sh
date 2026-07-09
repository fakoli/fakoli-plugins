#!/usr/bin/env bash
# anvil-pulse statusline segment for Claude Code.
#
# Prints a compact one-line anvil summary, e.g.:
#   anvil 2 claims | implement | lease 12m
# Prints NOTHING (and exits 0) when the cwd is not an anvil project, so it is
# safe to call unconditionally from a statusline command.
#
# Usage (from ~/.claude/statusline-command.sh):
#   seg="$(bash /path/to/statusline-segment.sh "$workspace_dir" 2>/dev/null)"
#   [[ -n "$seg" ]] && printf ' | %s' "$seg"
#
# Requires: anvil on PATH, and python3 or python (JSON parsing).
#
# The statusline refreshes every ~3s but `anvil` is a Python CLI with real
# startup cost, so results are cached for CACHE_TTL seconds per project.

PROJECT_DIR="${1:-$(pwd)}"
CACHE_TTL="${ANVIL_PULSE_STATUSLINE_TTL:-10}"

command -v anvil >/dev/null 2>&1 || exit 0

# On Windows, `python3` is often a non-functional WindowsApps alias stub;
# prefer whichever interpreter actually works.
PY=""
for cand in python3 python; do
  if "$cand" -c "pass" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[[ -z "$PY" ]] && exit 0

# Per-project cache file in a private dir (never a predictable /tmp path).
CACHE_DIR="${HOME}/.cache/anvil-pulse"
mkdir -p "$CACHE_DIR" 2>/dev/null && chmod 700 "$CACHE_DIR" 2>/dev/null
key=$(printf '%s' "$PROJECT_DIR" | cksum | cut -d' ' -f1)
CACHE_FILE="${CACHE_DIR}/statusline-${key}.txt"

if [[ -f "$CACHE_FILE" ]]; then
  now=$(date +%s)
  mtime=$(date -r "$CACHE_FILE" +%s 2>/dev/null || stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0)
  if (( now - mtime < CACHE_TTL )); then
    cat "$CACHE_FILE"
    exit 0
  fi
fi

json=$(anvil status --json --cwd "$PROJECT_DIR" 2>/dev/null)

# Exit 3 from the parser = anvil failed / gave no JSON (transient); in that
# case fall back to the stale cache rather than caching emptiness for TTL.
segment=$("$PY" -c '
import json, sys
try:
    env = json.loads(sys.stdin.read() or "")
except Exception:
    sys.exit(3)  # transient failure: caller keeps the previous cache
if not env.get("ok"):
    sys.exit(0)  # not an anvil project: print nothing (cacheable)
data = env.get("data") or {}
claims = data.get("claims") or []
tasks = data.get("tasks") or {}
parts = []
n = len(claims)
if n:
    parts.append(f"{n} claim" + ("s" if n != 1 else ""))
    phases = [c.get("phase") for c in claims if c.get("phase")]
    if phases:
        parts.append(phases[0] if len(set(phases)) == 1 else f"{len(set(phases))} phases")
    leases = [c.get("lease_expires_in_seconds") for c in claims
              if isinstance(c.get("lease_expires_in_seconds"), (int, float))]
    if leases:
        m = min(leases)
        if m <= 0:
            parts.append("lease EXPIRED")
        elif m < 60:
            parts.append(f"lease {int(m)}s!")
        else:
            parts.append(f"lease {int(m // 60)}m")
else:
    ready = tasks.get("ready")
    review = tasks.get("needs_review")
    if ready:
        parts.append(f"{ready} ready")
    if review:
        parts.append(f"{review} review")
if parts:
    print("anvil " + " | ".join(parts))
' <<<"$json" 2>/dev/null)
status=$?

if [[ $status -eq 3 ]]; then
  # Transient anvil failure: serve the previous cache (possibly stale) once.
  [[ -f "$CACHE_FILE" ]] && cat "$CACHE_FILE"
  exit 0
fi

printf '%s' "$segment" > "$CACHE_FILE"
[[ -n "$segment" ]] && echo "$segment"
exit 0
