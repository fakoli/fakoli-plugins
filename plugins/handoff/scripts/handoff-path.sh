#!/usr/bin/env bash
# handoff-path.sh — print the absolute path to THIS project's handoff file.
#
# Correctness requirement (the bug this plugin exists to avoid): the path is
# keyed by project identity, not cwd, which is often a throwaway per-session
# worktree. Repos with an origin remote use that remote so separate clones of
# the same project share one handoff; local repos fall back to the git COMMON
# dir, which is shared by every linked worktree.
#
# Storage lives under ~/.claude/handoff/<repo-key>/ — private (home, not the
# repo), project-scoped, and independent of Claude Code's internal slugs.
#
# Usage: handoff-path.sh [project_dir]   (defaults to $PWD)
# Side effect: ensures the directory exists. Prints the file path on stdout.
set -euo pipefail

project_dir="${1:-$PWD}"
base="${HOME}/.claude/handoff"

normalize_remote() {
  local url="$1"
  local rest host path

  url="${url%$'\r'}"
  url="${url%/}"

  case "$url" in
    git@*:*)
      rest="${url#git@}"
      host="${rest%%:*}"
      path="${rest#*:}"
      ;;
    ssh://git@*/*)
      rest="${url#ssh://git@}"
      host="${rest%%/*}"
      path="${rest#*/}"
      ;;
    http://*/*|https://*/*)
      rest="${url#*://}"
      rest="${rest#*@}"
      host="${rest%%/*}"
      path="${rest#*/}"
      ;;
    *)
      printf '%s' "$url"
      return
      ;;
  esac

  host=$(printf '%s' "$host" | tr '[:upper:]' '[:lower:]')
  path="${path%/}"
  path="${path%.git}"
  if [[ "$host" == "github.com" ]]; then
    path=$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')
  fi
  printf '%s/%s' "$host" "$path"
}

handoff_key() {
  local key_hint="$1"
  local key_src="$2"
  local key_hash

  key_hint=${key_hint//[^A-Za-z0-9]/-}
  key_hash=$(printf '%s' "$key_src" | git hash-object --stdin | cut -c1-12)
  printf '%s-%s' "$key_hint" "$key_hash"
}

# Canonicalize the project dir to its PHYSICAL path (resolve symlinks) up front.
# This is essential: git returns an already-canonical path from a linked
# worktree, while the cwd Claude Code passes in may be uncanonical (e.g. macOS
# /var vs /private/var). Without this, the main checkout and its worktrees would
# key to DIFFERENT files — the exact bug this plugin exists to prevent.
project_dir="$(cd "$project_dir" 2>/dev/null && pwd -P || printf '%s' "$project_dir")"

legacy_src=""
legacy_hint=""

if common=$(git -C "$project_dir" rev-parse --git-common-dir 2>/dev/null); then
  # `--git-common-dir` is the MAIN repo's .git (e.g. ".git" in the main
  # worktree, or an absolute path from a linked worktree). Normalize to an
  # absolute, physical repo root so every worktree yields the same key.
  case "$common" in
    /*) ;;                                  # already absolute (linked worktree)
    [A-Za-z]:/*) ;;                         # absolute Windows drive path: git on
                                            # Windows/MSYS emits C:/... here, which
                                            # the /* pattern misses; treating it as
                                            # relative mangled the key hint to "-git"
    *)  common="${project_dir%/}/$common" ;;  # relative (main worktree) → absolute
  esac
  # dirname of the common ".git" dir is the repo root (standard non-bare layout);
  # pwd -P keeps it physical so it matches the canonical project_dir above.
  legacy_src=$(cd "$(dirname "$common")" 2>/dev/null && pwd -P) || legacy_src="$common"
else
  # Not a git repo — best-effort fall back to the (canonical) project dir.
  legacy_src="$project_dir"
fi
legacy_hint=$(basename "$legacy_src")

src="$legacy_src"
hint="$legacy_hint"

if remote=$(git -C "$project_dir" remote get-url origin 2>/dev/null); then
  remote_id=$(normalize_remote "$remote")
  if [[ -n "$remote_id" ]]; then
    src="remote:${remote_id}"
    hint="${remote_id##*/}"
  fi
fi

# Key = a readable hint (repo basename) + a hash of the stable project identity.
# The hash guarantees uniqueness: a plain "non-alnum -> '-'" sanitize aliases
# distinct paths (e.g. /a/b-c and /a-b/c both collapse to -a-b-c). git
# hash-object is portable (git is already required) — unlike sha256sum, which
# is absent on macOS.
key=$(handoff_key "$hint" "$src")

dir="${base}/${key}"
mkdir -p "$dir"
handoff="${dir}/handoff.md"

legacy_key=$(handoff_key "$legacy_hint" "$legacy_src")
legacy_handoff="${base}/${legacy_key}/handoff.md"
if [[ "$legacy_key" != "$key" && ! -s "$handoff" && -s "$legacy_handoff" ]]; then
  cp -p "$legacy_handoff" "$handoff"
fi

printf '%s\n' "$handoff"
