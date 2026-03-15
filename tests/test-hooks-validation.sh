#!/usr/bin/env bash
#
# test-hooks-validation.sh - Tests that validate.sh catches hook structure errors
#
# Usage: ./tests/test-hooks-validation.sh
#
# Tests hook validation against known-good and known-bad fixtures to ensure
# Claude Code compatibility issues are caught before installation.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VALIDATE="$ROOT_DIR/scripts/validate.sh"
FIXTURES="$SCRIPT_DIR/fixtures"
trap 'rm -rf "$FIXTURES"' EXIT

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    echo -e "  ${GREEN}PASS${NC} $1"
    ((TESTS_PASSED++)) || true
}

fail() {
    echo -e "  ${RED}FAIL${NC} $1"
    echo -e "       $2"
    ((TESTS_FAILED++)) || true
}

# Create a temporary plugin with given hooks.json content
make_fixture() {
    local name="$1"
    local hooks_content="$2"
    local plugin_json="${3:-}"
    local dir="$FIXTURES/$name"

    rm -rf "$dir"
    mkdir -p "$dir/.claude-plugin" "$dir/hooks" "$dir/hooks/scripts"

    # Default minimal plugin.json
    if [[ -z "$plugin_json" ]]; then
        cat > "$dir/.claude-plugin/plugin.json" <<'MANIFEST'
{
  "name": "test-fixture",
  "version": "1.0.0",
  "description": "Test fixture for hook validation"
}
MANIFEST
    else
        echo "$plugin_json" > "$dir/.claude-plugin/plugin.json"
    fi

    echo "$hooks_content" > "$dir/hooks/hooks.json"

    # Create a dummy hook script for tests that reference one
    cat > "$dir/hooks/scripts/test-hook.sh" <<'SCRIPT'
#!/usr/bin/env bash
echo '{}'
SCRIPT
    chmod +x "$dir/hooks/scripts/test-hook.sh"

    echo "$dir"
}

# Run validate.sh on a fixture and capture output
run_validate() {
    local fixture_dir="$1"
    "$VALIDATE" "$fixture_dir" 2>&1
}

echo "========================================"
echo "  Hook Validation Tests"
echo "========================================"
echo ""

# ─────────────────────────────────────────────
# Test 1: Direct hook entry (missing hooks wrapper) → ERROR
# ─────────────────────────────────────────────
echo "--- Structure Tests ---"

fixture=$(make_fixture "direct-hook" '{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "echo hello",
        "timeout": 5
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "missing required 'hooks' array wrapper"; then
    pass "Detects direct hook entry without hooks wrapper"
else
    fail "Should detect direct hook entry without hooks wrapper" "Output: $(echo "$output" | grep -i 'error\|hooks')"
fi

# ─────────────────────────────────────────────
# Test 2: Correct wrapper format → no structure errors
# ─────────────────────────────────────────────

fixture=$(make_fixture "correct-wrapper" '{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo hello",
            "timeout": 5
          }
        ]
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "missing required 'hooks' array wrapper"; then
    fail "Correct wrapper format should not trigger wrapper error" "Output: $(echo "$output" | grep 'wrapper')"
else
    pass "Correct wrapper format passes structure check"
fi

# ─────────────────────────────────────────────
# Test 3: PreToolUse with matcher + hooks wrapper → pass
# ─────────────────────────────────────────────

fixture=$(make_fixture "pretooluse-matcher" '{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo ok",
            "timeout": 5
          }
        ]
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "ERROR"; then
    fail "PreToolUse with matcher should pass" "Output: $(echo "$output" | grep 'ERROR')"
else
    pass "PreToolUse with matcher + wrapper passes"
fi

# ─────────────────────────────────────────────
# Test 4: PreToolUse without matcher → WARN
# ─────────────────────────────────────────────

fixture=$(make_fixture "pretooluse-no-matcher" '{
  "hooks": {
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo ok",
            "timeout": 5
          }
        ]
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "no matcher"; then
    pass "Warns about PreToolUse without matcher"
else
    fail "Should warn about PreToolUse without matcher" "Output: $(echo "$output" | grep -i 'warn\|matcher')"
fi

# ─────────────────────────────────────────────
# Test 5: Empty hooks array → ERROR
# ─────────────────────────────────────────────

fixture=$(make_fixture "empty-hooks-array" '{
  "hooks": {
    "SessionStart": [
      {
        "hooks": []
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "empty 'hooks' array"; then
    pass "Detects empty hooks array"
else
    fail "Should detect empty hooks array" "Output: $(echo "$output" | grep -i 'error\|empty')"
fi

# ─────────────────────────────────────────────
echo ""
echo "--- Safety Tests ---"

# ─────────────────────────────────────────────
# Test 6: Command hook without timeout → WARN
# ─────────────────────────────────────────────

fixture=$(make_fixture "no-timeout" '{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo hello"
          }
        ]
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "no timeout"; then
    pass "Warns about missing timeout"
else
    fail "Should warn about missing timeout" "Output: $(echo "$output" | grep -i 'warn\|timeout')"
fi

# ─────────────────────────────────────────────
# Test 7: prompt-type on UserPromptSubmit → ERROR
# ─────────────────────────────────────────────

fixture=$(make_fixture "prompt-userprompt" '{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "evaluate this",
            "timeout": 10
          }
        ]
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "prompt-type hook on UserPromptSubmit"; then
    pass "Catches prompt-type on UserPromptSubmit"
else
    fail "Should catch prompt-type on UserPromptSubmit" "Output: $(echo "$output" | grep -i 'error\|prompt')"
fi

# ─────────────────────────────────────────────
# Test 8: prompt-type on PreToolUse without matcher → ERROR
# ─────────────────────────────────────────────

fixture=$(make_fixture "prompt-pretooluse-no-matcher" '{
  "hooks": {
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "evaluate this",
            "timeout": 10
          }
        ]
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "prompt-type hook on PreToolUse with no matcher"; then
    pass "Catches prompt-type on PreToolUse without matcher"
else
    fail "Should catch prompt-type on PreToolUse without matcher" "Output: $(echo "$output" | grep -i 'error\|prompt')"
fi

# ─────────────────────────────────────────────
# Test 9: set -e in hook script → WARN
# ─────────────────────────────────────────────

fixture=$(make_fixture "set-e-script" '{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/test-hook.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}')
# Add set -e to the test script
cat > "$fixture/hooks/scripts/test-hook.sh" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
echo '{}'
SCRIPT
chmod +x "$fixture/hooks/scripts/test-hook.sh"

output=$(run_validate "$fixture")
if echo "$output" | grep -q "set -e"; then
    pass "Warns about set -e in hook scripts"
else
    fail "Should warn about set -e in hook scripts" "Output: $(echo "$output" | grep -i 'warn\|set')"
fi

# ─────────────────────────────────────────────
echo ""
echo "--- Manifest Tests ---"

# ─────────────────────────────────────────────
# Test 10: $schema in plugin.json → ERROR
# ─────────────────────────────────────────────

fixture=$(make_fixture "schema-in-manifest" '{"hooks":{}}' '{
  "$schema": "../../../schemas/plugin.schema.json",
  "name": "test-fixture",
  "version": "1.0.0",
  "description": "Test fixture with banned schema field"
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "Unrecognized field"; then
    pass "Catches \$schema in plugin.json"
else
    fail "Should catch \$schema in plugin.json as unrecognized field" "Output: $(echo "$output" | grep -i 'error\|unrecognized\|schema')"
fi

# ─────────────────────────────────────────────
# Test 11: Missing hook script → ERROR
# ─────────────────────────────────────────────

fixture=$(make_fixture "missing-script" '{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/nonexistent.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}')

output=$(run_validate "$fixture")
if echo "$output" | grep -q "does not exist"; then
    pass "Catches missing hook script"
else
    fail "Should catch missing hook script" "Output: $(echo "$output" | grep -i 'error\|script\|exist')"
fi

# ─────────────────────────────────────────────
echo ""
echo "--- Real Plugin Tests ---"

# ─────────────────────────────────────────────
# Test 12: Validate all real plugins pass
# ─────────────────────────────────────────────

full_output=$("$VALIDATE" 2>&1) || true
# Strip ANSI color codes for matching
clean_output=$(echo "$full_output" | sed 's/\x1b\[[0-9;]*m//g')
if echo "$clean_output" | grep -q "Failed: 0"; then
    pass "All real plugins pass validation"
else
    failed_line=$(echo "$clean_output" | grep "Failed:" | head -1)
    fail "Real plugins have validation failures" "$failed_line — run ./scripts/validate.sh for details"
fi

# ─────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────
rm -rf "$FIXTURES"

echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo -e "${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Failed:${NC} $TESTS_FAILED"
echo "========================================"

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
exit 0
