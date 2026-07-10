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

echo
echo "passed=$pass failed=$fail"
[[ $fail -eq 0 ]]
