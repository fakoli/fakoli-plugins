#!/usr/bin/env bash
#
# Regression tests for scripts/handoff-path.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HANDOFF_PATH="$PLUGIN_DIR/scripts/handoff-path.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

export HOME="$tmp/home"
mkdir -p "$HOME"

make_repo() {
  local dir="$1"
  local remote="$2"

  mkdir -p "$dir"
  git -C "$dir" init --quiet
  git -C "$dir" remote add origin "$remote"
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local label="$3"

  if [[ "$expected" != "$actual" ]]; then
    printf 'FAIL %s\nexpected: %s\nactual:   %s\n' "$label" "$expected" "$actual" >&2
    exit 1
  fi

  printf 'PASS %s\n' "$label"
}

assert_ne() {
  local left="$1"
  local right="$2"
  local label="$3"

  if [[ "$left" == "$right" ]]; then
    printf 'FAIL %s\nboth: %s\n' "$label" "$left" >&2
    exit 1
  fi

  printf 'PASS %s\n' "$label"
}

make_repo "$tmp/clone-a" "https://github.com/fakoli/anvil.git"
make_repo "$tmp/clone-b" "https://github.com/fakoli/anvil.git"

path_a="$(bash "$HANDOFF_PATH" "$tmp/clone-a")"
path_b="$(bash "$HANDOFF_PATH" "$tmp/clone-b")"
assert_eq "$path_a" "$path_b" "same origin shares handoff across separate clones"

make_repo "$tmp/clone-ssh" "git@github.com:fakoli/anvil.git"
path_ssh="$(bash "$HANDOFF_PATH" "$tmp/clone-ssh")"
assert_eq "$path_a" "$path_ssh" "https and ssh GitHub origins normalize together"

make_repo "$tmp/clone-case" "https://github.com/Fakoli/Anvil.git"
path_case="$(bash "$HANDOFF_PATH" "$tmp/clone-case")"
assert_eq "$path_a" "$path_case" "GitHub origin case variants normalize together"

make_repo "$tmp/other" "https://github.com/fakoli/other.git"
path_other="$(bash "$HANDOFF_PATH" "$tmp/other")"
assert_ne "$path_a" "$path_other" "different origins keep separate handoffs"

make_repo "$tmp/legacy-remote" "https://github.com/fakoli/legacy.git"
legacy_src="$(cd "$tmp/legacy-remote" && pwd -P)"
legacy_hint="$(basename "$legacy_src")"
legacy_hint="${legacy_hint//[^A-Za-z0-9]/-}"
legacy_hash="$(printf '%s' "$legacy_src" | git hash-object --stdin | cut -c1-12)"
legacy_path="$HOME/.claude/handoff/${legacy_hint}-${legacy_hash}/handoff.md"
mkdir -p "$(dirname "$legacy_path")"
printf 'legacy note\n' > "$legacy_path"

migrated_path="$(bash "$HANDOFF_PATH" "$tmp/legacy-remote")"
assert_ne "$legacy_path" "$migrated_path" "remote-backed repos move to a remote-scoped key"
assert_eq "legacy note" "$(cat "$migrated_path")" "legacy handoff migrates into remote-scoped key"

mkdir -p "$tmp/local-main"
git -C "$tmp/local-main" init --quiet
touch "$tmp/local-main/README.md"
git -C "$tmp/local-main" add README.md
git -C "$tmp/local-main" -c user.email=test@example.com -c user.name=test commit --quiet -m init
git -C "$tmp/local-main" worktree add --quiet "$tmp/local-worktree"

path_local_main="$(bash "$HANDOFF_PATH" "$tmp/local-main")"
path_local_worktree="$(bash "$HANDOFF_PATH" "$tmp/local-worktree")"
assert_eq "$path_local_main" "$path_local_worktree" "local repos still share handoff across linked worktrees"

# Remote-backed repo across linked worktrees — the exact failure that opened the
# session this plugin's worktree-safety exists for: a repo WITH an origin, worked on
# from a throwaway per-session worktree (and from a subdirectory of it), must resolve
# to the SAME handoff as the main checkout.
make_repo "$tmp/remote-main" "https://github.com/fakoli/wtree.git"
touch "$tmp/remote-main/README.md"
git -C "$tmp/remote-main" add README.md
git -C "$tmp/remote-main" -c user.email=test@example.com -c user.name=test commit --quiet -m init
git -C "$tmp/remote-main" worktree add --quiet "$tmp/remote-worktree"
mkdir -p "$tmp/remote-main/sub/deep"

path_remote_main="$(bash "$HANDOFF_PATH" "$tmp/remote-main")"
path_remote_worktree="$(bash "$HANDOFF_PATH" "$tmp/remote-worktree")"
path_remote_subdir="$(bash "$HANDOFF_PATH" "$tmp/remote-main/sub/deep")"
assert_eq "$path_remote_main" "$path_remote_worktree" "remote-backed repos share handoff across linked worktrees"
assert_eq "$path_remote_main" "$path_remote_subdir" "handoff resolves the same from a subdirectory of a worktree"
