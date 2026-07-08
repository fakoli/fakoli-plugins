#!/usr/bin/env bash
#
# test-bump-plugin.sh — guards for scripts/bump-plugin.sh (version lockstep).
#
# Exercises the helper in --dry-run (which writes nothing) and its error paths,
# so the one-command version bump can't silently regress. Does NOT perform a
# real bump — that would dirty the tree; the dry-run asserts the plan instead.
#
# Usage: ./tests/test-bump-plugin.sh   (exit 0 on full PASS)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BUMP="$ROOT_DIR/scripts/bump-plugin.sh"

PASS_COUNT=0
FAIL_COUNT=0
pass() { echo "  PASS $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  FAIL $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

# Pick any existing plugin to exercise the happy-path dry-run.
SAMPLE="$(cd "$ROOT_DIR/plugins" && ls -d */ 2>/dev/null | head -1 | tr -d /)"

echo "== bump-plugin.sh guards =="

# 1. script exists and is executable
if [[ -x "$BUMP" ]]; then pass "script exists and is executable"
else fail "scripts/bump-plugin.sh missing or not executable"; fi

# 2. dry-run on a real plugin succeeds, plans a bump, writes nothing
before="$(git -C "$ROOT_DIR" status --porcelain)"
out="$("$BUMP" "$SAMPLE" patch --dry-run 2>&1)"; rc=$?
after="$(git -C "$ROOT_DIR" status --porcelain)"
if [[ $rc -eq 0 ]]; then pass "dry-run exits 0"; else fail "dry-run exit $rc"; fi
if grep -q -- "->" <<<"$out" && grep -qi "generate-index" <<<"$out"; then
  pass "dry-run prints the lockstep plan"
else fail "dry-run plan missing"; fi
if [[ "$before" == "$after" ]]; then pass "dry-run changed no files"
else fail "dry-run modified the working tree"; fi

# 3. error paths
"$BUMP" >/dev/null 2>&1 && fail "missing args should error" || pass "missing args errors"
"$BUMP" no-such-plugin patch >/dev/null 2>&1 && fail "unknown plugin should error" || pass "unknown plugin errors"
"$BUMP" "$SAMPLE" sideways --dry-run >/dev/null 2>&1 && fail "bad spec should error" || pass "bad version spec errors"

# 4. explicit semver + bump levels are accepted (dry-run)
for spec in patch minor major 9.9.9; do
  if "$BUMP" "$SAMPLE" "$spec" --dry-run >/dev/null 2>&1; then pass "accepts spec: $spec"
  else fail "rejected valid spec: $spec"; fi
done

echo "========================================"
echo "  Passed: $PASS_COUNT"
echo "  Failed: $FAIL_COUNT"
echo "========================================"
[[ $FAIL_COUNT -eq 0 ]]
