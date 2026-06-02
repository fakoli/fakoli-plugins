#!/usr/bin/env bash
#
# test-fakoli-crew-agent-models.sh - Fakoli Crew model selection invariant
#
# Usage: ./tests/test-fakoli-crew-agent-models.sh
#
# Ensures every active fakoli-crew agent keeps its Claude model selection while
# also shipping an OpenAI/Codex custom-agent model selection that Claude ignores.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
AGENTS_DIR="$ROOT_DIR/plugins/fakoli-crew/agents"
CODEX_AGENTS_DIR="$ROOT_DIR/plugins/fakoli-crew/.codex/agents"

FAIL_COUNT=0
shopt -s nullglob
AGENT_FILES=("$AGENTS_DIR"/*.md)

echo "========================================"
echo "  Fakoli Crew Agent Model Tests"
echo "========================================"
echo ""

expected_claude_model() {
    case "$1" in
        critic|guido) echo "opus" ;;
        sentinel) echo "haiku" ;;
        herald|keeper|scout|smith|welder) echo "sonnet" ;;
        *) echo "" ;;
    esac
}

expected_openai_model() {
    case "$1" in
        critic|guido) echo "gpt-5.5" ;;
        sentinel) echo "gpt-5.4-mini" ;;
        herald|keeper|scout|smith|welder) echo "gpt-5.4" ;;
        *) echo "" ;;
    esac
}

expected_openai_effort() {
    case "$1" in
        critic|guido) echo "high" ;;
        sentinel) echo "medium" ;;
        herald|keeper|scout|smith|welder) echo "medium" ;;
        *) echo "" ;;
    esac
}

if [[ ${#AGENT_FILES[@]} -eq 0 ]]; then
    echo "  FAIL no agent files found in $AGENTS_DIR"
    FAIL_COUNT=1
else
for agent_file in "${AGENT_FILES[@]}"; do
    agent_name="$(basename "$agent_file" .md)"
    claude_model="$(expected_claude_model "$agent_name")"
    openai_model="$(expected_openai_model "$agent_name")"
    openai_effort="$(expected_openai_effort "$agent_name")"
    model_line="$(awk '
        NR == 1 && $0 == "---" { in_frontmatter = 1; next }
        in_frontmatter && $0 == "---" { exit }
        in_frontmatter && /^model:/ { print }
    ' "$agent_file")"
    codex_file="$CODEX_AGENTS_DIR/fakoli-$agent_name.toml"

    if [[ "$model_line" == "model: $claude_model" ]]; then
        echo "  PASS $agent_name Claude model is $claude_model"
    else
        echo "  FAIL $agent_name should use Claude model: $claude_model"
        echo "       Found: ${model_line:-missing model field}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    if [[ -f "$codex_file" ]]; then
        echo "  PASS $agent_name has Codex custom-agent metadata"
    else
        echo "  FAIL $agent_name is missing $codex_file"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    fi

    if grep -q "^name = \"fakoli_$agent_name\"$" "$codex_file"; then
        echo "  PASS $agent_name Codex agent name is namespaced"
    else
        echo "  FAIL $agent_name Codex agent name should be fakoli_$agent_name"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    if grep -q "^model = \"$openai_model\"$" "$codex_file"; then
        echo "  PASS $agent_name OpenAI model is $openai_model"
    else
        echo "  FAIL $agent_name OpenAI model should be $openai_model"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    if grep -q "^model_reasoning_effort = \"$openai_effort\"$" "$codex_file"; then
        echo "  PASS $agent_name OpenAI reasoning effort is $openai_effort"
    else
        echo "  FAIL $agent_name OpenAI reasoning effort should be $openai_effort"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    if grep -q '^developer_instructions = """$' "$codex_file"; then
        echo "  PASS $agent_name Codex agent has developer instructions"
    else
        echo "  FAIL $agent_name Codex agent is missing developer_instructions"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done
fi

echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo "Failed: $FAIL_COUNT"
echo "========================================"

if [[ $FAIL_COUNT -gt 0 ]]; then
    exit 1
fi
exit 0
