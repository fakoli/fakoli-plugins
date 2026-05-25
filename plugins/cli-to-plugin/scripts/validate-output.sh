#!/usr/bin/env bash
#
# validate-output.sh — Validate a generated cli-to-plugin output against all
# marketplace rules: validate.sh, test-path-resolution.sh, plugin.json schema,
# and SKILL.md frontmatter schema.
#
# Usage: ./plugins/cli-to-plugin/scripts/validate-output.sh <absolute-path-to-plugin>
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MARKETPLACE_ROOT="$SCRIPT_DIR/../../.."
PLUGIN_SCHEMA="$MARKETPLACE_ROOT/schemas/plugin.schema.json"
SKILL_SCHEMA="$MARKETPLACE_ROOT/schemas/skill.schema.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── Argument check ──────────────────────────────────────────────────────────

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <absolute-path-to-plugin>" >&2
    exit 1
fi

TARGET="$1"

if [[ ! -d "$TARGET" ]]; then
    echo -e "${RED}ERROR:${NC} Target directory does not exist: $TARGET" >&2
    exit 1
fi

# ── Dependency check ─────────────────────────────────────────────────────────

if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}ERROR:${NC} jq is required but not installed." >&2
    echo "Install with: brew install jq (macOS) or apt-get install jq (Linux)" >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo -e "${RED}ERROR:${NC} uv is required but not installed." >&2
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# ── Counters ─────────────────────────────────────────────────────────────────

validate_errors=0
validate_warns=0
validate_result_status="PASS"

path_result_status="PASS"

plugin_json_status="PASS"

skill_count=0
skill_fails=0
skill_result_status="PASS"

overall_status="PASS"

# ── Check 1: marketplace validate.sh ─────────────────────────────────────────

echo ""
echo "========================================"
echo "  [1/4] Running validate.sh"
echo "========================================"

validate_output=$("$MARKETPLACE_ROOT/scripts/validate.sh" "$TARGET" 2>&1)
validate_exit=$?

echo "$validate_output"

# Count ERRORs and WARNs from output
validate_errors=$(echo "$validate_output" | grep -c '^ERROR:' 2>/dev/null || true)
validate_warns=$(echo "$validate_output" | grep -c '^WARN:' 2>/dev/null || true)

# Also catch colored variants (strip ansi then count)
validate_errors_colored=$(echo "$validate_output" | sed 's/\x1b\[[0-9;]*m//g' | grep -c 'ERROR:' 2>/dev/null || true)
validate_warns_colored=$(echo "$validate_output" | sed 's/\x1b\[[0-9;]*m//g' | grep -c 'WARN:' 2>/dev/null || true)

# Use the larger of the two counts (colored output may include stderr-merged lines)
if [[ "$validate_errors_colored" -gt "$validate_errors" ]]; then
    validate_errors="$validate_errors_colored"
fi
if [[ "$validate_warns_colored" -gt "$validate_warns" ]]; then
    validate_warns="$validate_warns_colored"
fi

if [[ "$validate_exit" -ne 0 ]]; then
    validate_result_status="FAIL"
    overall_status="FAIL"
fi

# ── Check 2: test-path-resolution.sh ─────────────────────────────────────────

echo ""
echo "========================================"
echo "  [2/4] Running test-path-resolution.sh"
echo "========================================"

path_output=$("$MARKETPLACE_ROOT/scripts/test-path-resolution.sh" "$TARGET" 2>&1)
path_exit=$?

echo "$path_output"

if [[ "$path_exit" -ne 0 ]]; then
    path_result_status="FAIL"
    overall_status="FAIL"
fi

# ── Check 3: plugin.json schema validation ────────────────────────────────────

echo ""
echo "========================================"
echo "  [3/4] Validating plugin.json schema"
echo "========================================"

plugin_json="$TARGET/.claude-plugin/plugin.json"

if [[ ! -f "$plugin_json" ]]; then
    echo -e "${RED}ERROR:${NC} plugin.json not found at $plugin_json" >&2
    plugin_json_status="FAIL"
    overall_status="FAIL"
else
    plugin_schema_output=$(uv run --with jsonschema python -m jsonschema \
        --instance "$plugin_json" \
        "$PLUGIN_SCHEMA" 2>&1)
    plugin_schema_exit=$?

    if [[ "$plugin_schema_exit" -eq 0 ]]; then
        echo -e "${GREEN}OK:${NC} plugin.json passes schema validation"
    else
        echo -e "${RED}FAIL:${NC} plugin.json schema validation failed:" >&2
        echo "$plugin_schema_output" >&2
        plugin_json_status="FAIL"
        overall_status="FAIL"
    fi
fi

# ── Check 4: SKILL.md frontmatter validation ──────────────────────────────────

echo ""
echo "========================================"
echo "  [4/4] Validating SKILL.md frontmatter"
echo "========================================"

# Find all SKILL.md files under skills/*/SKILL.md
skill_files=()
if [[ -d "$TARGET/skills" ]]; then
    while IFS= read -r -d '' skill_file; do
        skill_files+=("$skill_file")
    done < <(find "$TARGET/skills" -mindepth 2 -maxdepth 2 -name "SKILL.md" -print0 2>/dev/null)
fi

skill_count="${#skill_files[@]}"

if [[ "$skill_count" -eq 0 ]]; then
    echo "INFO: No SKILL.md files found — skipping frontmatter check (not a failure)"
else
    echo "INFO: Found $skill_count SKILL.md file(s) to validate"

    for skill_file in "${skill_files[@]}"; do
        skill_name=$(basename "$(dirname "$skill_file")")
        echo ""
        echo "  Checking: $skill_name/SKILL.md"

        # Extract YAML frontmatter between first pair of --- markers
        # Write to a temp file rather than shell-interpolating into Python — protects against
        # frontmatter content containing triple-quotes or other Python-string-terminators.
        frontmatter_tmp=$(mktemp)
        awk '/^---$/{c++; if(c==2) exit; next} c==1 {print}' "$skill_file" > "$frontmatter_tmp"

        if [[ ! -s "$frontmatter_tmp" ]]; then
            # SKILL.md frontmatter is required by the marketplace skill schema, so a missing
            # block is a hard FAIL — not a soft WARN. Label matches the outcome.
            echo -e "  ${RED}FAIL:${NC} No YAML frontmatter found in $skill_name/SKILL.md" >&2
            rm -f "$frontmatter_tmp"
            ((skill_fails++)) || true
            continue
        fi

        skill_validate_output=$(uv run --with jsonschema --with pyyaml python -c "
import sys, json, yaml, jsonschema

with open(sys.argv[1], encoding='utf-8') as fh:
    frontmatter = fh.read()
schema_path = sys.argv[2]

try:
    data = yaml.safe_load(frontmatter)
except yaml.YAMLError as e:
    print(f'YAML parse error: {e}', file=sys.stderr)
    sys.exit(1)

if data is None:
    data = {}

with open(schema_path) as f:
    schema = json.load(f)

try:
    jsonschema.validate(instance=data, schema=schema)
    print('OK')
except jsonschema.ValidationError as e:
    print(f'Schema violation: {e.message}', file=sys.stderr)
    sys.exit(1)
" "$frontmatter_tmp" "$SKILL_SCHEMA" 2>&1)
        skill_validate_exit=$?
        rm -f "$frontmatter_tmp"

        if [[ "$skill_validate_exit" -eq 0 ]]; then
            echo -e "  ${GREEN}OK:${NC} $skill_name/SKILL.md frontmatter valid"
        else
            echo -e "  ${RED}FAIL:${NC} $skill_name/SKILL.md frontmatter invalid:" >&2
            echo "$skill_validate_output" | sed 's/^/    /' >&2
            ((skill_fails++)) || true
        fi
    done

    if [[ "$skill_fails" -gt 0 ]]; then
        skill_result_status="FAIL"
        overall_status="FAIL"
    fi
fi

# ── Summary block ─────────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  validate-output.sh summary for $TARGET"
echo "========================================"
echo "  Marketplace validate.sh:       $validate_result_status ($validate_errors errors, $validate_warns warnings)"
echo "  test-path-resolution.sh:       $path_result_status"
echo "  plugin.json schema check:      $plugin_json_status"
echo "  SKILL.md frontmatter checks:   $skill_result_status ($skill_count skills checked, $skill_fails failed)"
echo "========================================"

if [[ "$overall_status" == "PASS" ]]; then
    echo -e "  Overall:                       ${GREEN}PASS${NC}"
else
    echo -e "  Overall:                       ${RED}FAIL${NC}"
fi

echo "========================================"

if [[ "$overall_status" != "PASS" ]]; then
    exit 1
fi
exit 0
