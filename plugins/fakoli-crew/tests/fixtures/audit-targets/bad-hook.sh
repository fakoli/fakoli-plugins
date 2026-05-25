#!/usr/bin/env bash
# bad-hook.sh — INTENTIONAL ANTIPATTERN FIXTURE — DO NOT FIX
# ============================================================
#
# This script is a deliberately-broken PreToolUse hook used to smoke-test
# fakoli-crew's `hook-critic` per the procedure in tests/RECIPES.md (T7).
#
# Contract: non-blocking (always exit 0; warnings only). Detected from:
# this leading comment block.
#
# The companion bad-hooks.json in the same directory references this script
# and documents the same non-blocking contract — hook-critic's contract-
# detection rule (Step 2: grep for non-blocking signal phrases) must fire
# off this comment block AND the README-style language in bad-hooks.json.
#
# The following bugs are intentional. If you "fix" them, hook-critic will
# no longer surface a finding and the smoke test will regress.
#
# Intentional bugs:
#   1. `set -e` is declared on a script governed by a non-blocking contract.
#      Expected critic finding: MUST FIX — under a non-blocking contract,
#      `set -e` causes the script to exit non-zero on any internal failure
#      (e.g., a failing `grep`), which Claude Code interprets as a
#      PreToolUse BLOCK. The unconditional `exit 0` at the bottom never
#      runs. This is the exact bug pattern non-blocking contracts exist
#      to forbid.
#
#   2. Plugin-internal path is referenced without `${CLAUDE_PLUGIN_ROOT}`.
#      The script greps `./hooks/state.txt` (a bare relative path) — this
#      will resolve against the user's project cwd, not the plugin root,
#      and will break the moment the plugin runs from anywhere other than
#      the plugin directory.
#      Expected critic finding: SHOULD FIX (per hook-critic's Portability
#      checklist; the rule is "every intra-plugin path uses
#      ${CLAUDE_PLUGIN_ROOT}").
#
# Expected verdict from hook-critic when run against this file (with
# bad-hooks.json as the contract source): FAIL — 1x MUST FIX (set -e
# contract violation) + 1x SHOULD FIX (missing CLAUDE_PLUGIN_ROOT).

set -e

# Read JSON payload from stdin (PreToolUse contract).
if [ -t 0 ]; then
  PAYLOAD="{}"
else
  PAYLOAD=$(cat)
fi

# BUG #2: bare relative path — should be "${CLAUDE_PLUGIN_ROOT}/hooks/state.txt".
# Under `set -e` (BUG #1), if this grep fails the script exits non-zero
# RIGHT HERE, before the `exit 0` at the bottom — blocking the tool call.
grep -q "ok" ./hooks/state.txt

echo "[bad-hook] payload processed" >&2

exit 0
