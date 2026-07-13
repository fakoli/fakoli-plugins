#!/usr/bin/env bash
#
# test-ship-worktree.sh — integration test for ship.sh's merge/sync split
# (issue #137).
#
# Scenario: `main` is checked out in worktree A (intentionally dirty), the
# feature branch in linked worktree B. A stubbed `gh` reproduces the real
# failure mode: `gh pr merge` merges the PR on GitHub, then exits nonzero on
# the local sync ("'main' is already used by worktree at ..."), leaving the
# remote feature branch undeleted.
#
# Expected: ship.sh detects the PR is MERGED remotely, deletes the remote
# feature branch itself, reports the local sync as skipped (worktree), and
# exits 5 (partial success) — NOT 3 (merge failure). A control case where the
# PR is genuinely not merged must still exit 3.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHIP="$SCRIPT_DIR/../scripts/ship.sh"

PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); echo "  ok: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1" >&2; }

assert_eq() { # label expected actual
  if [ "$2" = "$3" ]; then ok "$1"; else fail "$1 (expected '$2', got '$3')"; fi
}

assert_contains() { # label needle haystack
  if printf '%s' "$3" | grep -qF "$2"; then ok "$1"; else fail "$1 (missing '$2')"; fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------------------
# fixture: bare origin, primary clone (main, dirty), linked feature worktree
# ---------------------------------------------------------------------------
git init --bare -q "$TMP/origin.git"
git clone -q "$TMP/origin.git" "$TMP/repo"
GIT="git -C $TMP/repo -c user.email=t@example.test -c user.name=t"
$GIT checkout -q -b main
echo base > "$TMP/repo/file.txt"
$GIT add file.txt
$GIT commit -qm "base"
$GIT push -q -u origin main
echo dirty >> "$TMP/repo/file.txt"   # worktree A stays dirty on main

$GIT worktree add -q "$TMP/feature-wt" -b feature
GITF="git -C $TMP/feature-wt -c user.email=t@example.test -c user.name=t"
echo change > "$TMP/feature-wt/change.txt"
$GITF add change.txt
$GITF commit -qm "feature change"

# ---------------------------------------------------------------------------
# stub gh: merge succeeds REMOTELY but the command exits nonzero, exactly as
# gh does when the base branch's worktree blocks its local post-merge sync.
# ---------------------------------------------------------------------------
export GH_STATE_DIR="$TMP/gh-state"
mkdir -p "$GH_STATE_DIR"
mkdir -p "$TMP/bin"
cat > "$TMP/bin/gh" <<'GH'
#!/usr/bin/env bash
args="$*"
case "$args" in
  *"pr merge"*)
    if [ -n "${GH_MERGE_REALLY_FAILS:-}" ]; then
      echo "GraphQL: Pull request is not mergeable" >&2
      exit 1
    fi
    touch "$GH_STATE_DIR/merged"
    echo "failed to run git: fatal: 'main' is already used by worktree at '/tmp/repo'" >&2
    exit 1
    ;;
  *"--json state"*)
    if [ -f "$GH_STATE_DIR/merged" ]; then echo "MERGED"; else echo "OPEN"; fi
    ;;
  *"--json mergeCommit"*) echo "abc123def456789" ;;
  *"--json number"*)      echo "42" ;;
  *"--json url"*)         echo "https://example.test/pr/42" ;;
  *"defaultBranchRef"*)   echo "main" ;;
  *) : ;;
esac
exit 0
GH
chmod +x "$TMP/bin/gh"
export PATH="$TMP/bin:$PATH"

# ---------------------------------------------------------------------------
# case 1: remote merge landed despite nonzero exit → partial success (5)
# ---------------------------------------------------------------------------
echo "case 1: merged remotely, base branch owned by another worktree"
out="$(cd "$TMP/feature-wt" && bash "$SHIP" --no-wait "feature change" 2>&1)"
rc=$?

assert_eq "exit code is 5 (partial success), not 3" 5 "$rc"
assert_contains "reports the PR merged remotely" "MERGED remotely" "$out"
assert_contains "reports base sync skipped for worktree" "checked out in another worktree" "$out"
assert_contains "summary carries sync status" "sync worktree" "$out"
if git -C "$TMP/origin.git" show-ref --verify --quiet refs/heads/feature; then
  fail "remote feature branch deleted after remote-only merge"
else
  ok "remote feature branch deleted after remote-only merge"
fi

# ---------------------------------------------------------------------------
# case 2: --then must not run when the base was never synced locally
# ---------------------------------------------------------------------------
echo "case 2: --then is skipped on partial success"
rm -f "$GH_STATE_DIR/merged"
$GITF push -q -u origin feature   # restore the remote branch for a re-run
out="$(cd "$TMP/feature-wt" && bash "$SHIP" --no-wait --then "touch $TMP/then-ran" "feature change" 2>&1)"
rc=$?

assert_eq "exit code is 5" 5 "$rc"
assert_contains "reports --then skipped" "skipping --then" "$out"
if [ -e "$TMP/then-ran" ]; then
  fail "--then did not run against an unsynced base"
else
  ok "--then did not run against an unsynced base"
fi

# ---------------------------------------------------------------------------
# case 3: merged, but base pull does not fast-forward → partial success (5)
# ---------------------------------------------------------------------------
echo "case 3: non-fast-forward base pull is partial success, --then skipped"
rm -f "$GH_STATE_DIR/merged"
git clone -q "$TMP/origin.git" "$TMP/repo2"
GIT2="git -C $TMP/repo2 -c user.email=t@example.test -c user.name=t"
$GIT2 checkout -q main
$GIT2 checkout -q -b feature2
echo change2 > "$TMP/repo2/change2.txt"
$GIT2 add change2.txt
$GIT2 commit -qm "feature2 change"
# Diverge local main from origin main so `git pull --ff-only` must fail.
$GIT2 branch -f main HEAD   # local main now carries the feature commit
git clone -q "$TMP/origin.git" "$TMP/repo3"
GIT3="git -C $TMP/repo3 -c user.email=t@example.test -c user.name=t"
$GIT3 checkout -q main
echo remote-advance > "$TMP/repo3/remote.txt"
$GIT3 add remote.txt
$GIT3 commit -qm "remote advance"
$GIT3 push -q origin main
out="$(cd "$TMP/repo2" && bash "$SHIP" --no-wait --then "touch $TMP/then-ran-2" "feature2 change" 2>&1)"
rc=$?

assert_eq "exit code is 5 on pull-failed" 5 "$rc"
assert_contains "summary carries sync pull-failed" "sync pull-failed" "$out"
if [ -e "$TMP/then-ran-2" ]; then
  fail "--then did not run after a failed base pull"
else
  ok "--then did not run after a failed base pull"
fi

# ---------------------------------------------------------------------------
# case 4: genuine merge failure (PR still open) → merge failure (3)
# ---------------------------------------------------------------------------
echo "case 4: genuine merge failure still exits 3"
rm -f "$GH_STATE_DIR/merged"
$GITF push -q -u origin feature 2>/dev/null || true   # restore branch for re-run
export GH_MERGE_REALLY_FAILS=1
out="$(cd "$TMP/feature-wt" && bash "$SHIP" --no-wait "feature change" 2>&1)"
rc=$?
unset GH_MERGE_REALLY_FAILS

assert_eq "exit code is 3 (merge failure)" 3 "$rc"
assert_contains "reports PR left open" "PR left open" "$out"

echo ""
echo "test-ship-worktree: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
