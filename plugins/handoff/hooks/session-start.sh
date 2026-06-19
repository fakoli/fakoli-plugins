#!/usr/bin/env bash
# SessionStart hook — print this project's handoff note as a resume banner so a
# new session (in any worktree) sees where the last one left off. Quiet when no
# handoff exists. Deliberately no `set -e`: a context hook must never block or
# fail the session — it always falls through to exit 0.

plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# handoff-path.sh resolves the repo from $PWD (the session cwd) via the git
# common dir, so there is no need to parse the hook's stdin for cwd.
path="$(bash "$plugin_root/scripts/handoff-path.sh" 2>/dev/null || true)"

if [ -s "$path" ]; then
  printf '▶ HANDOFF — resume point for this project (from the last session):\n\n'
  cat "$path"
  printf '\n(Refresh it with /handoff:handoff; show it with /handoff:recall.)\n'
fi
