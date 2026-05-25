#!/usr/bin/env bash
#
# test-gh-generation.sh — End-to-end smoke test for cli-to-plugin against the
# captured gh help-tree fixture.
#
# Usage: bash tests/smoke/test-gh-generation.sh
#   Exits 0 on all checks PASS, 0 on SKIP (claude not on PATH), 1 on any failure.
#
# Compliance notes (from CLAUDE.md hook safety rules):
#   - No set -e; all exit codes captured explicitly.
#   - Cleanup via trap EXIT (fires on success and failure).
#   - No cat | grep patterns.
#   - All paths quoted.
#   - claude not on PATH → SKIP (exit 0, not failure).
#
# Non-interactive flag: claude -p / --print
#   The claude CLI uses -p/--print for non-interactive output (confirmed via
#   `claude --help`). There is no --no-interactive flag on this version.
#   The slash command is passed as the prompt argument to `claude -p`.
#

# ── Path setup ───────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$SCRIPT_DIR/../.."
MARKETPLACE_ROOT="$SCRIPT_DIR/../../../.."

FIXTURE="$PLUGIN_ROOT/tests/fixtures/gh-help-tree.expected.json"
VALIDATE_SH="$MARKETPLACE_ROOT/scripts/validate.sh"
PATH_RESOLUTION_SH="$MARKETPLACE_ROOT/scripts/test-path-resolution.sh"

# ── Expected groups (derived from gh-help-tree.expected.json) ─────────────────

EXPECTED_GROUPS=(pr issue repo workflow release gist)

# ── Temp dir and cleanup ──────────────────────────────────────────────────────

TMP=""

cleanup() {
    if [ -n "$TMP" ] && [ -d "$TMP" ]; then
        rm -rf "$TMP"
    fi
}

trap cleanup EXIT

# ── Helpers ───────────────────────────────────────────────────────────────────

pass() { echo "[smoke]   $1 ... PASS"; }
fail() { echo "[smoke]   FAIL: $1" >&2; }

# ── Gate: claude must be on PATH ─────────────────────────────────────────────

if ! command -v claude >/dev/null 2>&1; then
    echo "[smoke] SKIP: claude CLI not available; smoke test skipped"
    exit 0
fi

# ── Gate: fixture must exist ──────────────────────────────────────────────────

if [ ! -f "$FIXTURE" ]; then
    echo "[smoke] FAIL: fixture not found: $FIXTURE" >&2
    exit 1
fi

# ── Gate: validators must exist ──────────────────────────────────────────────

if [ ! -f "$VALIDATE_SH" ]; then
    echo "[smoke] FAIL: validate.sh not found: $VALIDATE_SH" >&2
    exit 1
fi

if [ ! -f "$PATH_RESOLUTION_SH" ]; then
    echo "[smoke] FAIL: test-path-resolution.sh not found: $PATH_RESOLUTION_SH" >&2
    exit 1
fi

# ── Set up temp directory ─────────────────────────────────────────────────────

TMP="$(mktemp -d /tmp/cli-to-plugin-smoke-XXXX)"
mktemp_result=$?
if [ $mktemp_result -ne 0 ] || [ ! -d "$TMP" ]; then
    echo "[smoke] FAIL: could not create temp directory" >&2
    exit 1
fi

echo "[smoke] Setting up temp dir: $TMP"

OUT="$TMP/gh"

# ── Run the slash command via claude -p ───────────────────────────────────────
#
# claude -p / --print is the non-interactive output mode for this version of
# the claude CLI (confirmed via `claude --help`). There is no --no-interactive
# flag. The slash command is passed as the prompt argument.
#
# IMPORTANT: claude -p does NOT execute slash commands in some installed
# versions — it prints "Unknown command: /cli-to-plugin" and exits 0.
# When this happens the test SKIPs gracefully (exit 0) so CI without a
# fully-configured claude installation does not false-fail.
#
# Manual run (for local development when SKIP fires):
#   mkdir -p /tmp/gh-smoke-out/gh
#   cd <marketplace-root>
#   claude '/cli-to-plugin gh \
#     --from-tree plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json \
#     --out /tmp/gh-smoke-out/gh \
#     --no-meta-skills'
# Then verify the output directory against the assertions below.

SLASH_COMMAND="/cli-to-plugin gh --from-tree \"$FIXTURE\" --out \"$OUT\" --no-meta-skills"

echo "[smoke] Running: claude -p '$SLASH_COMMAND'"

claude_output="$(claude -p "$SLASH_COMMAND" 2>&1)"
claude_exit=$?

# Detect the "slash commands not supported in -p mode" condition:
# claude exits 0 but prints "Unknown command: /cli-to-plugin".
if echo "$claude_output" | grep -qF "Unknown command: /cli-to-plugin"; then
    echo "[smoke] SKIP: /cli-to-plugin slash command not available in claude -p on this machine"
    echo "[smoke] (claude output: $claude_output)"
    exit 0
fi

if [ $claude_exit -ne 0 ]; then
    echo "[smoke] FAIL: claude exited with code $claude_exit" >&2
    echo "$claude_output" >&2
    exit 1
fi

echo "[smoke] claude exited 0"

# ── Assert plugin.json exists and parses as JSON ──────────────────────────────

echo "[smoke] Asserting plugin.json exists ..."

PLUGIN_JSON="$OUT/.claude-plugin/plugin.json"

if [ ! -f "$PLUGIN_JSON" ]; then
    fail "$PLUGIN_JSON not found"
    exit 1
fi

pass "plugin.json exists"

jq_check=$(jq empty "$PLUGIN_JSON" 2>&1)
jq_exit=$?
if [ $jq_exit -ne 0 ]; then
    fail "plugin.json is not valid JSON: $jq_check"
    exit 1
fi

pass "plugin.json parses as JSON"

# ── Assert README.md exists ───────────────────────────────────────────────────

if [ ! -f "$OUT/README.md" ]; then
    fail "README.md not found at $OUT/README.md"
    exit 1
fi

pass "README.md exists"

# ── Assert per-group skill directories ───────────────────────────────────────

echo "[smoke] Asserting skill dirs ..."

skills_failed=0

for group in "${EXPECTED_GROUPS[@]}"; do
    skill_dir="$OUT/skills/gh-$group"
    skill_md="$skill_dir/SKILL.md"
    if [ ! -f "$skill_md" ]; then
        fail "gh-$group: $skill_md not found"
        skills_failed=$((skills_failed + 1))
    else
        echo "[smoke]   gh-$group ... PASS"
    fi
done

if [ $skills_failed -ne 0 ]; then
    echo "[smoke] FAIL: $skills_failed skill(s) missing" >&2
    exit 1
fi

# ── Run validate.sh ───────────────────────────────────────────────────────────

echo "[smoke] Running validate.sh on $OUT ..."

validate_output="$(bash "$VALIDATE_SH" "$OUT" 2>&1)"
validate_exit=$?

if [ $validate_exit -ne 0 ]; then
    fail "validate.sh exited with code $validate_exit"
    echo "$validate_output" >&2
    exit 1
fi

pass "validate.sh"

# ── Run test-path-resolution.sh ───────────────────────────────────────────────

echo "[smoke] Running test-path-resolution.sh on $OUT ..."

path_output="$(bash "$PATH_RESOLUTION_SH" "$OUT" 2>&1)"
path_exit=$?

if [ $path_exit -ne 0 ]; then
    fail "test-path-resolution.sh exited with code $path_exit"
    echo "$path_output" >&2
    exit 1
fi

pass "test-path-resolution.sh"

# ── All checks passed ─────────────────────────────────────────────────────────

echo "[smoke] All checks passed."
exit 0
