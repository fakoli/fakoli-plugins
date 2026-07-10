#!/usr/bin/env bash
# handoff-meta.sh — print a YAML frontmatter block capturing the state the
# handoff note was saved against, so /recall can tell whether the note has
# gone stale (branch moved, HEAD advanced, claims released).
#
# Every field is best-effort and independently optional: outside a git repo
# the git fields are omitted; without the anvil CLI (or outside an anvil
# project) the anvil fields are omitted. Always exits 0 — metadata must never
# block a save. Keys are FLAT (no nesting) so handoff-freshness.sh can parse
# them with plain grep; this file is the only writer, freshness the only
# reader — keep them in lockstep.
#
# Usage: handoff-meta.sh [project_dir]   (defaults to $PWD)
set -uo pipefail

project_dir="${1:-$PWD}"
cd "$project_dir" 2>/dev/null || exit 0

echo "---"
# date -u is portable across Git Bash/Linux/macOS for this format.
echo "saved_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

if git rev-parse --git-dir >/dev/null 2>&1; then
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  head="$(git rev-parse HEAD 2>/dev/null || true)"
  dirty="$(git status --porcelain 2>/dev/null | grep -c . || true)"
  [[ -n "$branch" ]] && echo "branch: $branch"
  [[ -n "$head" ]] && echo "head: $head"
  echo "dirty_files: ${dirty:-0}"
fi

# Optional anvil snapshot — the anvil-pulse guard pattern: probe only when the
# CLI exists, stay silent on any failure (not an anvil project, transient).
if command -v anvil >/dev/null 2>&1; then
  PY=""
  for cand in python3 python; do
    if "$cand" -c "pass" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
  if [[ -n "$PY" ]]; then
    anvil status --json --cwd "$project_dir" 2>/dev/null | "$PY" -c "
import json, sys
try:
    env = json.loads(sys.stdin.read() or '')
except Exception:
    sys.exit(0)
if not env.get('ok'):
    sys.exit(0)
data = env.get('data') or {}
claims = data.get('claims') or []
tasks = data.get('tasks') or {}
# task:phase pairs, comma-separated — flat and grep-friendly.
if claims:
    pairs = []
    for c in claims:
        task = c.get('task_id') or c.get('task') or '?'
        phase = c.get('phase') or '-'
        pairs.append('%s:%s' % (task, phase))
    print('anvil_claims: ' + ','.join(pairs))
for key in ('ready', 'needs_review'):
    v = tasks.get(key)
    if isinstance(v, int):
        print('anvil_%s: %d' % (key, v))
" 2>/dev/null
  fi
fi

echo "---"
exit 0
