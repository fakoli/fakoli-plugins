#!/usr/bin/env bash
#
# test-lint-frontmatter.sh - Tests for scripts/lint-frontmatter.py's SKILL.md
# name-matches-directory enforcement (plus a baseline YAML-validity check).
#
# Usage: ./tests/test-lint-frontmatter.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LINTER="$ROOT_DIR/scripts/lint-frontmatter.py"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

RED='\033[0;31m'
GREEN='\033[0;32m'
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

echo "========================================"
echo "  lint-frontmatter.py Tests"
echo "========================================"
echo ""

# ─────────────────────────────────────────────
# Case a: valid SKILL.md — name == directory name, valid slug -> exit 0
# ─────────────────────────────────────────────

dir="$TMP_DIR/skills/good-skill"
mkdir -p "$dir"
cat > "$dir/SKILL.md" <<'EOF'
---
name: good-skill
description: A valid skill for the happy path
---

# Good Skill
EOF
output=$(python3 "$LINTER" "$dir/SKILL.md" 2>&1); status=$?
if [[ $status -eq 0 ]]; then
    pass "valid SKILL.md (name == dir, valid slug) passes"
else
    fail "valid SKILL.md (name == dir, valid slug) should pass" "Output: $output"
fi

# ─────────────────────────────────────────────
# Case b: SKILL.md name != directory name -> exit 1, message names both
# ─────────────────────────────────────────────

dir="$TMP_DIR/skills/mismatch-skill"
mkdir -p "$dir"
cat > "$dir/SKILL.md" <<'EOF'
---
name: other-name
description: A skill whose frontmatter name drifted from its directory
---
EOF
output=$(python3 "$LINTER" "$dir/SKILL.md" 2>&1); status=$?
if [[ $status -ne 0 ]] && echo "$output" | grep -q "'other-name'" && echo "$output" | grep -q "'mismatch-skill'"; then
    pass "SKILL.md name != directory name fails and names both in the message"
else
    fail "SKILL.md name != directory name should fail and name both" "Output: $output"
fi

# ─────────────────────────────────────────────
# Case c: SKILL.md name with uppercase/space (equal to dir, still an invalid slug) -> exit 1
# ─────────────────────────────────────────────

dir="$TMP_DIR/skills/Bad Name Skill"
mkdir -p "$dir"
cat > "$dir/SKILL.md" <<'EOF'
---
name: Bad Name Skill
description: A skill name that is not a valid slug even though it matches its directory
---
EOF
output=$(python3 "$LINTER" "$dir/SKILL.md" 2>&1); status=$?
if [[ $status -ne 0 ]] && echo "$output" | grep -q "not a valid skill name"; then
    pass "SKILL.md name with uppercase/space fails as an invalid slug"
else
    fail "SKILL.md name with uppercase/space should fail as an invalid slug" "Output: $output"
fi

# ─────────────────────────────────────────────
# Case d: SKILL.md missing name field -> exit 1
# ─────────────────────────────────────────────

dir="$TMP_DIR/skills/missing-name-skill"
mkdir -p "$dir"
cat > "$dir/SKILL.md" <<'EOF'
---
description: A skill with no name field at all
---
EOF
output=$(python3 "$LINTER" "$dir/SKILL.md" 2>&1); status=$?
if [[ $status -ne 0 ]] && echo "$output" | grep -q "has no name field"; then
    pass "SKILL.md missing name field fails"
else
    fail "SKILL.md missing name field should fail" "Output: $output"
fi

# ─────────────────────────────────────────────
# Case e: SKILL.md with no frontmatter block at all -> exit 1
# ─────────────────────────────────────────────

dir="$TMP_DIR/skills/no-frontmatter-skill"
mkdir -p "$dir"
cat > "$dir/SKILL.md" <<'EOF'
# No Frontmatter Skill

This SKILL.md never opens a `---` block, so it is undiscoverable.
EOF
output=$(python3 "$LINTER" "$dir/SKILL.md" 2>&1); status=$?
if [[ $status -ne 0 ]]; then
    pass "SKILL.md with no frontmatter block fails"
else
    fail "SKILL.md with no frontmatter block should fail" "Output: $output"
fi

# ─────────────────────────────────────────────
# Case f: non-SKILL.md file with a mismatched name -> exit 0 (rule scoped to SKILL.md)
# ─────────────────────────────────────────────

dir="$TMP_DIR/commands"
mkdir -p "$dir"
cat > "$dir/command.md" <<'EOF'
---
name: totally-unrelated-name
description: Command frontmatter is not subject to the SKILL.md directory-name rule
---
EOF
output=$(python3 "$LINTER" "$dir/command.md" 2>&1); status=$?
if [[ $status -eq 0 ]]; then
    pass "non-SKILL.md file with mismatched name is unaffected by the rule"
else
    fail "non-SKILL.md file with mismatched name should still pass" "Output: $output"
fi

# ─────────────────────────────────────────────
# Case g: malformed frontmatter (quoted value followed by trailing junk) -> exit 1
# ─────────────────────────────────────────────

dir="$TMP_DIR/skills/broken-yaml-skill"
mkdir -p "$dir"
cat > "$dir/SKILL.md" <<'EOF'
---
name: broken-yaml-skill
description: "x" [y]
---
EOF
output=$(python3 "$LINTER" "$dir/SKILL.md" 2>&1); status=$?
if [[ $status -ne 0 ]]; then
    pass "malformed frontmatter (trailing junk after quoted value) still fails"
else
    fail "malformed frontmatter (trailing junk after quoted value) should still fail" "Output: $output"
fi

# ─────────────────────────────────────────────
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
