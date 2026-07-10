#!/usr/bin/env bash
#
# Regression tests for scripts/handoff-meta.sh + scripts/handoff-freshness.sh.
# Same style as test-handoff-path.sh: mktemp sandbox, isolated $HOME, real git.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
META="$PLUGIN_DIR/scripts/handoff-meta.sh"
FRESH="$PLUGIN_DIR/scripts/handoff-freshness.sh"
HPATH="$PLUGIN_DIR/scripts/handoff-path.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

export HOME="$tmp/home"
mkdir -p "$HOME"

pass=0
fail=0

assert_contains() {
  local haystack="$1" needle="$2" label="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "ok - $label"
    pass=$((pass + 1))
  else
    echo "FAIL - $label"
    echo "  wanted substring: $needle"
    echo "  got: $haystack"
    fail=$((fail + 1))
  fi
}

assert_not_contains() {
  local haystack="$1" needle="$2" label="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    echo "ok - $label"
    pass=$((pass + 1))
  else
    echo "FAIL - $label"
    echo "  unwanted substring present: $needle"
    fail=$((fail + 1))
  fi
}

make_repo() {
  local dir="$1"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config user.email t@t
  git -C "$dir" config user.name t
  echo hi > "$dir/f.txt"
  git -C "$dir" add . && git -C "$dir" commit -qm init
}

# ---- meta: git fields present, well-formed frontmatter -----------------------
repo="$tmp/proj"
make_repo "$repo"
meta="$(bash "$META" "$repo")"
assert_contains "$meta" "---" "meta emits fenced block"
assert_contains "$meta" "saved_at: " "meta records saved_at"
assert_contains "$meta" "branch: main" "meta records branch"
assert_contains "$meta" "head: " "meta records head"
assert_contains "$meta" "dirty_files: 0" "meta records clean tree"

# ---- meta outside a git repo: only saved_at ----------------------------------
plain="$tmp/plain"; mkdir -p "$plain"
meta2="$(bash "$META" "$plain")"
assert_contains "$meta2" "saved_at: " "non-git meta still has saved_at"
assert_not_contains "$meta2" "branch:" "non-git meta omits branch"

# ---- freshness: fresh note ----------------------------------------------------
note="$(bash "$HPATH" "$repo")"
{ bash "$META" "$repo"; echo; echo "## Resume"; echo "- do the thing"; } > "$note"
out="$(bash "$FRESH" "$repo")"
assert_contains "$out" "fresh" "unchanged repo reads fresh"

# ---- freshness: HEAD advanced -------------------------------------------------
echo more >> "$repo/f.txt"
git -C "$repo" commit -aqm next
out="$(bash "$FRESH" "$repo")"
assert_contains "$out" "STALE" "advanced HEAD flags stale"
assert_contains "$out" "HEAD advanced" "advance vs divergence distinguished"

# ---- freshness: branch moved --------------------------------------------------
git -C "$repo" checkout -qb feature/x
out="$(bash "$FRESH" "$repo")"
assert_contains "$out" "branch moved" "branch switch flagged"
git -C "$repo" checkout -q main

# ---- freshness: divergence ----------------------------------------------------
{ bash "$META" "$repo"; echo; echo "## Resume"; } > "$note"   # re-save fresh
git -C "$repo" reset -q --hard HEAD~1                          # rewind past save
echo other >> "$repo/f.txt"
git -C "$repo" commit -aqm diverge
out="$(bash "$FRESH" "$repo")"
assert_contains "$out" "diverged" "rewritten history flags divergence"

# ---- freshness: legacy note (no frontmatter) ----------------------------------
printf '## Resume\n- old style note\n' > "$note"
out="$(bash "$FRESH" "$repo")"
assert_contains "$out" "freshness unavailable" "legacy note degrades gracefully"
assert_contains "$out" "legacy" "legacy reason named"

# ---- freshness: no note --------------------------------------------------------
repo2="$tmp/proj2"
make_repo "$repo2"
out="$(bash "$FRESH" "$repo2")"
assert_contains "$out" "no handoff note" "missing note handled"

# ---- freshness: age flag (env-tunable) -----------------------------------------
{
  echo "---"
  echo "saved_at: 2020-01-01T00:00:00Z"
  echo "---"
  echo "## Resume"
} > "$note"
out="$(HANDOFF_MAX_AGE_DAYS=14 bash "$FRESH" "$repo")"
assert_contains "$out" "days old" "ancient note flags age"

# ---- freshness: recorded anvil claim no longer active (fake anvil on PATH) -----
mkdir -p "$tmp/bin"
cat > "$tmp/bin/anvil" <<'SHIM'
#!/usr/bin/env bash
# fake anvil: status returns NO active claims
echo '{"ok": true, "data": {"claims": [], "tasks": {"ready": 1, "needs_review": 0}}}'
SHIM
chmod +x "$tmp/bin/anvil"
{
  bash "$META" "$repo"   # (fake anvil emits no claims at save; craft manually)
} > /dev/null
{
  echo "---"
  echo "saved_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "branch: $(git -C "$repo" rev-parse --abbrev-ref HEAD)"
  echo "head: $(git -C "$repo" rev-parse HEAD)"
  echo "dirty_files: 0"
  echo "anvil_claims: T042:implement"
  echo "---"
  echo "## Resume"
} > "$note"
out="$(PATH="$tmp/bin:$PATH" bash "$FRESH" "$repo")"
assert_contains "$out" "T042" "released claim flagged by task id"
assert_contains "$out" "no longer active" "claim staleness reason named"

# ---- freshness: --json shape ----------------------------------------------------
out="$(PATH="$tmp/bin:$PATH" bash "$FRESH" "$repo" --json)"
assert_contains "$out" '"available":true' "json availability"
assert_contains "$out" '"fresh":false' "json staleness"
assert_contains "$out" 'T042' "json carries flag text"

echo
echo "passed=$pass failed=$fail"
[[ $fail -eq 0 ]]
