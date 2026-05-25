#!/usr/bin/env bash
# test_critics.sh — Manual-verification recipe printer for fakoli-crew critics.
#
# Why this is a printer, not a dispatcher:
#   Critic agents are dispatched via the Claude Code Agent tool, which only
#   exists inside an active Claude Code session. A bash script cannot spawn a
#   subagent. So this runner enumerates the 5 critics, the fixture each
#   consumes, the severity token the critic's findings must contain, and a
#   pointer to RECIPES.md (created by T7) for the full manual procedure.
#
# Usage:
#   bash tests/test_critics.sh --list      # print the recipe table
#   bash tests/test_critics.sh --recipes   # print the full RECIPES.md to stdout
#   bash tests/test_critics.sh --help      # print usage
#
# Exit codes:
#   0   success (printed table, recipes, or help)
#   2   unknown / missing argument
#   3   --recipes invoked but RECIPES.md is missing

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_ROOT="${SCRIPT_DIR}"
FIXTURES_DIR="${TESTS_ROOT}/fixtures/audit-targets"
RECIPES_REL="tests/RECIPES.md"   # Created by T7
RECIPES_ABS="${TESTS_ROOT}/RECIPES.md"

# Critic recipe table.
# Format: <critic-name>|<fixture-basename>|<expected-severity>|<one-line-rationale>
# Fixture filenames are the conventions T6 will follow; if T6 chooses different
# names, update this table to match.
CRITIC_RECIPES=(
  "agent-critic|bad-agent.md|MUST FIX|missing required name: frontmatter key + uses allowed-tools: (command convention) instead of tools: (agent convention)"
  "skill-critic|bad-skill/SKILL.md|SHOULD FIX|vague description ('a skill that helps with things') + no numbered decision flow or step enumeration"
  "hook-critic|bad-hook.sh|MUST FIX|set -e on a script governed by a non-blocking contract + bare './hooks/state.txt' path missing \${CLAUDE_PLUGIN_ROOT} prefix"
  "mcp-critic|bad-mcp.json|MUST FIX|stdio server entry missing required args field (Claude Code's MCP loader requires args, even an empty array)"
  "structure-critic|bad-plugin.json|MUST FIX|missing required version field (semver) + description is 6 chars ('tiny.'), below the meaningful-description floor"
)

_print_help() {
  cat <<EOF
test_critics.sh — fakoli-crew critic recipe printer

Usage:
  bash tests/test_critics.sh --list      List each critic, fixture, expected severity
  bash tests/test_critics.sh --recipes   Print the full ${RECIPES_REL} to stdout
  bash tests/test_critics.sh --help      Show this message

This script does NOT dispatch agents. Bash cannot spawn a Claude Code
subagent. For actual critic invocation, follow the manual recipes documented
in ${RECIPES_REL}.

Tests directory:    ${TESTS_ROOT}
Fixtures directory: ${FIXTURES_DIR}
Recipes file:       ${RECIPES_ABS}
EOF
}

_print_recipes() {
  if [ ! -s "${RECIPES_ABS}" ]; then
    printf 'ERROR: %s is missing or empty.\n' "${RECIPES_ABS}" >&2
    printf 'Expected location: %s\n' "${RECIPES_ABS}" >&2
    return 3
  fi
  cat "${RECIPES_ABS}"
}

_print_list() {
  printf '\n'
  printf 'fakoli-crew critics — manual verification recipes\n'
  printf '%s\n' '-------------------------------------------------'
  printf '\n'
  printf 'Fixtures live under: %s\n' "${FIXTURES_DIR}"
  if [ -s "${RECIPES_ABS}" ]; then
    printf 'Full recipes:        %s (present)\n' "${RECIPES_REL}"
  else
    printf 'Full recipes:        %s (MISSING — expected at %s)\n' "${RECIPES_REL}" "${RECIPES_ABS}"
  fi
  printf '\n'
  printf '%-18s  %-26s  %-10s  %s\n' "CRITIC" "FIXTURE" "SEVERITY" "RATIONALE"
  printf '%-18s  %-26s  %-10s  %s\n' "------" "-------" "--------" "---------"

  local entry critic fixture severity rationale fixture_path status
  for entry in "${CRITIC_RECIPES[@]}"; do
    IFS='|' read -r critic fixture severity rationale <<< "${entry}"
    fixture_path="${FIXTURES_DIR}/${fixture}"
    if [ -e "${fixture_path}" ]; then
      status="present"
    else
      status="pending (T6)"
    fi
    printf '%-18s  %-26s  %-10s  %s\n' \
      "${critic}" "${fixture} [${status}]" "${severity}" "${rationale}"
  done

  printf '\n'
  printf 'To run a critic manually inside Claude Code:\n'
  printf '  1. Open %s/<fixture>\n' "${FIXTURES_DIR}"
  printf '  2. Invoke the critic via the Agent tool (subagent_type "fakoli-crew:<critic>")\n'
  printf '  3. Inspect docs/plans/agent-<critic>-smoke-status.md for the SEVERITY token above\n'
  printf '\n'
  if [ -s "${RECIPES_ABS}" ]; then
    printf 'Full manual-verification recipes (dispatch one-liners + pass/fail criteria):\n'
    printf '  See %s\n' "${RECIPES_REL}"
    printf '  Or run: bash %s/test_critics.sh --recipes\n' "${TESTS_ROOT}"
  else
    printf 'RECIPES.md not found at %s — expected to be created by T7.\n' "${RECIPES_ABS}"
  fi
  printf '\n'
}

# Argument handling.
if [ "$#" -lt 1 ]; then
  _print_help
  exit 2
fi

case "$1" in
  --list)
    _print_list
    exit 0
    ;;
  --recipes)
    _print_recipes
    exit $?
    ;;
  --help|-h)
    _print_help
    exit 0
    ;;
  *)
    printf 'Unknown argument: %s\n\n' "$1" >&2
    _print_help >&2
    exit 2
    ;;
esac
