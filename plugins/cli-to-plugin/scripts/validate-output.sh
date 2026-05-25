#!/usr/bin/env bash
#
# validate-output.sh — Validate a generated cli-to-plugin output.
#
# Self-contained: uses schemas bundled inside the plugin at ../schemas/. Works
# whether the plugin is installed via the marketplace or run from a dev checkout.
#
# Usage: validate-output.sh <absolute-path-to-plugin>
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLUGIN_SCHEMA="$SCRIPT_DIR/../schemas/plugin.schema.json"
SKILL_SCHEMA="$SCRIPT_DIR/../schemas/skill.schema.json"

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

# ── Bundled-schema sanity check ──────────────────────────────────────────────

if [[ ! -f "$PLUGIN_SCHEMA" ]]; then
    echo -e "${RED}ERROR:${NC} Bundled plugin schema missing: $PLUGIN_SCHEMA" >&2
    echo "This plugin's installation is corrupted — reinstall via /plugin install" >&2
    exit 1
fi

if [[ ! -f "$SKILL_SCHEMA" ]]; then
    echo -e "${RED}ERROR:${NC} Bundled skill schema missing: $SKILL_SCHEMA" >&2
    echo "This plugin's installation is corrupted — reinstall via /plugin install" >&2
    exit 1
fi

# ── Counters ─────────────────────────────────────────────────────────────────

manifest_status="PASS"
manifest_warns=0

plugin_json_status="PASS"

skill_count=0
skill_fails=0
skill_result_status="PASS"

overall_status="PASS"

# ── Check 1: Manifest sanity (JSON syntax + license↔LICENSE) ─────────────────

echo ""
echo "========================================"
echo "  [1/3] Manifest sanity"
echo "========================================"

plugin_json="$TARGET/.claude-plugin/plugin.json"

if [[ ! -f "$plugin_json" ]]; then
    echo -e "${RED}ERROR:${NC} plugin.json not found at $plugin_json" >&2
    manifest_status="FAIL"
    overall_status="FAIL"
else
    if ! jq empty "$plugin_json" 2>/dev/null; then
        echo -e "${RED}ERROR:${NC} plugin.json is not valid JSON" >&2
        jq empty "$plugin_json" 2>&1 | sed 's/^/  /' >&2
        manifest_status="FAIL"
        overall_status="FAIL"
    else
        echo -e "${GREEN}OK:${NC} plugin.json is valid JSON"

        # license↔LICENSE cross-check (the one validate.sh rule jsonschema can't replicate)
        license_field=$(jq -r '.license // empty' "$plugin_json")
        if [[ -n "$license_field" ]] && [[ ! -f "$TARGET/LICENSE" ]] && [[ ! -f "$TARGET/LICENSE.md" ]] && [[ ! -f "$TARGET/LICENSE.txt" ]]; then
            echo -e "${YELLOW}WARN:${NC} license field set to '$license_field' but no LICENSE file found"
            ((manifest_warns++)) || true
        fi

        # README hint (informational)
        if [[ ! -f "$TARGET/README.md" ]]; then
            echo -e "${YELLOW}WARN:${NC} No README.md found in plugin root"
            ((manifest_warns++)) || true
        fi
    fi
fi

# ── Check 2: plugin.json schema validation ───────────────────────────────────

echo ""
echo "========================================"
echo "  [2/3] plugin.json schema validation"
echo "========================================"

if [[ "$manifest_status" == "PASS" ]]; then
    plugin_schema_output=$(uv run --with jsonschema python -W ignore::DeprecationWarning -m jsonschema \
        --instance "$plugin_json" \
        "$PLUGIN_SCHEMA" 2>&1)
    plugin_schema_exit=$?

    if [[ "$plugin_schema_exit" -eq 0 ]]; then
        echo -e "${GREEN}OK:${NC} plugin.json passes schema validation"
    else
        echo -e "${RED}FAIL:${NC} plugin.json schema validation failed:" >&2
        echo "$plugin_schema_output" | sed 's/^/  /' >&2
        plugin_json_status="FAIL"
        overall_status="FAIL"
    fi
else
    echo "INFO: Skipping schema check — manifest sanity failed first"
    plugin_json_status="SKIP"
fi

# ── Check 3: SKILL.md frontmatter validation ─────────────────────────────────

echo ""
echo "========================================"
echo "  [3/3] SKILL.md frontmatter validation"
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

        # Extract YAML frontmatter between first pair of --- markers.
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
echo "  Manifest sanity:               $manifest_status ($manifest_warns warnings)"
echo "  plugin.json schema:            $plugin_json_status"
echo "  SKILL.md frontmatter:          $skill_result_status ($skill_count skills checked, $skill_fails failed)"
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
