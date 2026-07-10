#!/usr/bin/env bash
#
# Regression tests for scripts/gate-router.sh — mktemp sandbox, real git.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROUTER="$PLUGIN_DIR/scripts/gate-router.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"; mkdir -p "$HOME"

pass=0; fail=0
assert_contains() {
  local hay="$1" needle="$2" label="$3"
  if [[ "$hay" == *"$needle"* ]]; then echo "ok - $label"; pass=$((pass+1));
  else echo "FAIL - $label"; echo "  wanted: $needle"; echo "  got: $hay"; fail=$((fail+1)); fi
}
assert_not_contains() {
  local hay="$1" needle="$2" label="$3"
  if [[ "$hay" != *"$needle"* ]]; then echo "ok - $label"; pass=$((pass+1));
  else echo "FAIL - $label"; echo "  unwanted: $needle"; fail=$((fail+1)); fi
}

repo="$tmp/proj"
mkdir -p "$repo/.claude" "$repo/docs" "$repo/src"
git -C "$repo" init -q -b main
git -C "$repo" config user.email t@t; git -C "$repo" config user.name t
echo base > "$repo/README.md"
git -C "$repo" add . && git -C "$repo" commit -qm init

cat > "$repo/.claude/gate-router.local.md" <<'EOF'
---
rules:
  - docs/** => echo DOCS-GATE
  - "**/*.sh" => echo SHELL-GATE {files}
  - src/** => echo SRC-GATE
---
Human notes here.
EOF

# ---- no changes ----------------------------------------------------------------
out="$(bash "$ROUTER" "$repo")"
assert_contains "$out" "no changed files" "clean tree requires nothing"

# ---- docs change routes the docs gate -------------------------------------------
echo d > "$repo/docs/x.md"
out="$(bash "$ROUTER" "$repo")"
assert_contains "$out" "echo DOCS-GATE" "docs change requires docs gate"
assert_not_contains "$out" "SRC-GATE" "unmatched gates not required"

# ---- {files} expansion + root-level **/ match -----------------------------------
echo '#!/bin/bash' > "$repo/tool.sh"
out="$(bash "$ROUTER" "$repo")"
assert_contains "$out" "echo SHELL-GATE tool.sh" "leading **/ matches root files and {files} expands"

# ---- dedup across overlapping rules ---------------------------------------------
echo s > "$repo/src/a.py"; echo s > "$repo/src/b.py"
out="$(bash "$ROUTER" "$repo")"
count="$(grep -c "SRC-GATE" <<<"$out")"
if [[ "$count" == "1" ]]; then echo "ok - one command per gate despite two files"; pass=$((pass+1));
else echo "FAIL - dedup (got $count SRC-GATE lines)"; fail=$((fail+1)); fi

# ---- --run executes and stops on failure ----------------------------------------
cat > "$repo/.claude/gate-router.local.md" <<'EOF'
---
rules:
  - src/** => exit 7
  - docs/** => echo NEVER-REACHED
---
EOF
set +e
out="$(bash "$ROUTER" "$repo" --run 2>&1)"; rc=$?
set -e 2>/dev/null || true
if [[ "$rc" == "7" ]]; then echo "ok - --run propagates failing gate rc"; pass=$((pass+1));
else echo "FAIL - --run rc (got $rc)"; fail=$((fail+1)); fi
assert_contains "$out" "GATE FAILED" "failure reported"
assert_not_contains "$out" "NEVER-REACHED" "stops on first failure"

# ---- --json shape -----------------------------------------------------------------
cat > "$repo/.claude/gate-router.local.md" <<'EOF'
---
rules:
  - docs/** => echo DOCS-GATE
---
EOF
out="$(bash "$ROUTER" "$repo" --json)"
assert_contains "$out" '"gates":[{"command":"echo DOCS-GATE"' "json gate entry"
assert_contains "$out" '"files":["docs/x.md"]' "json files list"

# ---- no config --------------------------------------------------------------------
rm "$repo/.claude/gate-router.local.md"
set +e
out="$(bash "$ROUTER" "$repo" 2>&1)"; rc=$?
if [[ "$rc" == "0" ]]; then echo "ok - missing config is a clean no-op"; pass=$((pass+1));
else echo "FAIL - missing config rc=$rc"; fail=$((fail+1)); fi
assert_contains "$out" "no config" "missing config explained"

# ---- committed diff vs base also counts --------------------------------------------
cat > "$repo/.claude/gate-router.local.md" <<'EOF'
---
rules:
  - docs/** => echo DOCS-GATE
---
EOF
git -C "$repo" add . && git -C "$repo" commit -qm work
git -C "$repo" checkout -qb feature
echo more > "$repo/docs/y.md"
git -C "$repo" add . && git -C "$repo" commit -qm docs
out="$(bash "$ROUTER" "$repo" --base main)"
assert_contains "$out" "echo DOCS-GATE" "committed changes vs --base counted"

# ---- SECURITY: a changed filename with shell metachars is NOT executed -------
repo3="$tmp/inj"
mkdir -p "$repo3/.claude"
git -C "$repo3" init -q -b main
git -C "$repo3" config user.email t@t; git -C "$repo3" config user.name t
echo x > "$repo3/seed"; git -C "$repo3" add .; git -C "$repo3" commit -qm init
cat > "$repo3/.claude/gate-router.local.md" <<'EOF'
---
rules:
  - "**/*.sh" => printf 'GOT:[%s]\n' {files}
---
EOF
# Untracked files whose NAMES are shell-injection payloads (no '/', so they
# are legal single path components). If {files} were interpolated into
# `bash -c`, running --run would create these marker files in the repo.
: > "$repo3/x;touch SEMIPWNED.sh"
: > "$repo3/\$(touch SUBPWNED).sh"
set +e
out="$(bash "$ROUTER" "$repo3" --run 2>&1)"
set -e 2>/dev/null || true
if [[ -e "$repo3/SEMIPWNED" || -e "$repo3/SUBPWNED" ]]; then
  echo "FAIL - injection: metachar filename executed as code"; fail=$((fail+1))
  rm -f "$repo3/SEMIPWNED" "$repo3/SUBPWNED"
else
  echo "ok - metachar filenames passed as inert argv (no injection on --run)"; pass=$((pass+1))
fi
assert_contains "$out" "GOT:[x;touch SEMIPWNED.sh]" "literal metachar name reached the command as one arg"

# --list of a {files} rule is copy-paste-safe (metachars shell-quoted) --------
out="$(bash "$ROUTER" "$repo3" --list)"
assert_contains "$out" "printf" "list renders the command"
# a raw '; touch SEMIPWNED' would be a command separator on paste — must be quoted
assert_not_contains "$out" "printf 'GOT:[%s]\n' x;touch SEMIPWNED.sh" "list output quotes metachar names"

# ---- segment-aware globs: single * does NOT cross '/' ------------------------
repo4="$tmp/seg"
mkdir -p "$repo4/.claude" "$repo4/src/deep"
git -C "$repo4" init -q -b main
git -C "$repo4" config user.email t@t; git -C "$repo4" config user.name t
echo x > "$repo4/seed"; git -C "$repo4" add .; git -C "$repo4" commit -qm init
cat > "$repo4/.claude/gate-router.local.md" <<'EOF'
---
rules:
  - src/*.py => echo SHALLOW
  - src/**/*.py => echo DEEP
---
EOF
echo a > "$repo4/src/top.py"
echo b > "$repo4/src/deep/nested.py"
out="$(bash "$ROUTER" "$repo4")"
assert_contains "$out" "echo SHALLOW" "src/*.py matches a direct child"
assert_contains "$out" "echo DEEP" "src/**/*.py matches a nested file"
# top.py must NOT trigger DEEP-only expectations, and nested.py must NOT match src/*.py:
json="$(bash "$ROUTER" "$repo4" --json)"
assert_contains "$json" '"command":"echo SHALLOW","files":["src/top.py"]' "shallow rule excludes nested file"

# ---- filenames with SPACES stay one argument --------------------------------
repo5="$tmp/space"
mkdir -p "$repo5/.claude/../docs" "$repo5/.claude"
git -C "$repo5" init -q -b main
git -C "$repo5" config user.email t@t; git -C "$repo5" config user.name t
echo x > "$repo5/seed"; git -C "$repo5" add .; git -C "$repo5" commit -qm init
cat > "$repo5/.claude/gate-router.local.md" <<'EOF'
---
rules:
  - "docs/**" => printf 'ARG[%s]\n' {files}
---
EOF
mkdir -p "$repo5/docs"; : > "$repo5/docs/my notes.md"
out="$(bash "$ROUTER" "$repo5" --run 2>&1)"
assert_contains "$out" "ARG[docs/my notes.md]" "space-containing filename is one argument"

echo
echo "passed=$pass failed=$fail"
[[ $fail -eq 0 ]]
