#!/usr/bin/env bash
# handoff-path.sh — print the absolute path to THIS project's handoff file.
#
# Correctness requirement (the bug this plugin exists to avoid): the path is
# keyed by the git COMMON dir, which is shared by every linked worktree of a
# repo — NEVER by cwd, which is a throwaway per-session worktree. So all
# worktrees of one repo resolve to the SAME handoff file.
#
# Storage lives under ~/.claude/handoff/<repo-key>/ — private (home, not the
# repo), project-scoped, and independent of Claude Code's internal slugs.
#
# Usage: handoff-path.sh [project_dir]   (defaults to $PWD)
# Side effect: ensures the directory exists. Prints the file path on stdout.
set -euo pipefail

project_dir="${1:-$PWD}"
base="${HOME}/.claude/handoff"

# Canonicalize the project dir to its PHYSICAL path (resolve symlinks) up front.
# This is essential: git returns an already-canonical path from a linked
# worktree, while the cwd Claude Code passes in may be uncanonical (e.g. macOS
# /var vs /private/var). Without this, the main checkout and its worktrees would
# key to DIFFERENT files — the exact bug this plugin exists to prevent.
project_dir="$(cd "$project_dir" 2>/dev/null && pwd -P || printf '%s' "$project_dir")"

if common=$(git -C "$project_dir" rev-parse --git-common-dir 2>/dev/null); then
  # `--git-common-dir` is the MAIN repo's .git (e.g. ".git" in the main
  # worktree, or an absolute path from a linked worktree). Normalize to an
  # absolute, physical repo root so every worktree yields the same key.
  case "$common" in
    /*) ;;                                  # already absolute (linked worktree)
    *)  common="${project_dir%/}/$common" ;;  # relative (main worktree) → absolute
  esac
  # dirname of the common ".git" dir is the repo root (standard non-bare layout);
  # pwd -P keeps it physical so it matches the canonical project_dir above.
  if repo_root=$(cd "$(dirname "$common")" 2>/dev/null && pwd -P); then
    key=$(printf '%s' "$repo_root" | tr -c 'A-Za-z0-9' '-')
  else
    key=$(printf '%s' "$common" | tr -c 'A-Za-z0-9' '-')
  fi
else
  # Not a git repo — best-effort fall back to the (canonical) project dir.
  key=$(printf '%s' "$project_dir" | tr -c 'A-Za-z0-9' '-')
fi

dir="${base}/${key}"
mkdir -p "$dir"
printf '%s/handoff.md\n' "$dir"
