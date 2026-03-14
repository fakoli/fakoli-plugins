#!/usr/bin/env bash
set -euo pipefail

# ─── resolve plugin root ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PLUGIN_ROOT"

# ─── counters ───────────────────────────────────────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf "  PASS  %s\n" "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf "  FAIL  %s\n" "$1"
}

section() {
  printf "\n── %s ──\n" "$1"
}

# ─────────────────────────────────────────────────────────────────────────────────
# 1. Structure tests
# ─────────────────────────────────────────────────────────────────────────────────
section "Structure tests"

# plugin.json exists
if [[ -f .claude-plugin/plugin.json ]]; then
  pass "plugin.json exists"
else
  fail "plugin.json exists"
fi

# plugin.json is valid JSON
if jq empty .claude-plugin/plugin.json 2>/dev/null; then
  pass "plugin.json is valid JSON"
else
  fail "plugin.json is valid JSON"
fi

# Required fields in plugin.json
for field in name version description; do
  val=$(jq -r ".$field // empty" .claude-plugin/plugin.json 2>/dev/null)
  if [[ -n "${val:-}" ]]; then
    pass "plugin.json has required field '$field'"
  else
    fail "plugin.json has required field '$field'"
  fi
done

# README.md exists
if [[ -f README.md ]]; then
  pass "README.md exists"
else
  fail "README.md exists"
fi

# CHANGELOG.md exists
if [[ -f CHANGELOG.md ]]; then
  pass "CHANGELOG.md exists"
else
  fail "CHANGELOG.md exists"
fi

# LICENSE exists
if [[ -f LICENSE ]]; then
  pass "LICENSE exists"
else
  fail "LICENSE exists"
fi

# hooks/hooks.json exists and is valid JSON
if [[ -f hooks/hooks.json ]]; then
  pass "hooks/hooks.json exists"
  if jq empty hooks/hooks.json 2>/dev/null; then
    pass "hooks/hooks.json is valid JSON"
  else
    fail "hooks/hooks.json is valid JSON"
  fi
else
  fail "hooks/hooks.json exists"
  fail "hooks/hooks.json is valid JSON"
fi

# ─────────────────────────────────────────────────────────────────────────────────
# 2. Skill tests
# ─────────────────────────────────────────────────────────────────────────────────
section "Skill tests"

skill_pass=0
skill_fail=0

for skill_md in skills/*/SKILL.md; do
  skill_name="$(basename "$(dirname "$skill_md")")"

  # Extract frontmatter (between first pair of --- markers)
  frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill_md" | sed '1d;$d')

  if [[ -z "$frontmatter" ]]; then
    fail "skill '$skill_name': has valid YAML frontmatter"
    skill_fail=$((skill_fail + 1))
    continue
  fi

  # Check required frontmatter fields
  ok=true
  for field in name description version; do
    if ! echo "$frontmatter" | grep -qE "^${field}:"; then
      fail "skill '$skill_name': frontmatter has '$field'"
      ok=false
      skill_fail=$((skill_fail + 1))
    fi
  done

  # Stale pattern checks
  content=$(cat "$skill_md")
  if echo "$content" | grep -q "PREREQUISITE: Load"; then
    fail "skill '$skill_name': no stale 'PREREQUISITE: Load' pattern"
    ok=false
    skill_fail=$((skill_fail + 1))
  fi
  if echo "$content" | grep -qi "openclaw"; then
    fail "skill '$skill_name': no stale 'openclaw' reference"
    ok=false
    skill_fail=$((skill_fail + 1))
  fi
  if echo "$content" | grep -q "generate-skills"; then
    fail "skill '$skill_name': no stale 'generate-skills' reference"
    ok=false
    skill_fail=$((skill_fail + 1))
  fi

  if $ok; then
    skill_pass=$((skill_pass + 1))
  fi
done

pass "Skills with valid frontmatter + no stale patterns: $skill_pass"
if [[ $skill_fail -gt 0 ]]; then
  fail "Skills with issues: $skill_fail"
fi

# ─────────────────────────────────────────────────────────────────────────────────
# 3. Command tests
# ─────────────────────────────────────────────────────────────────────────────────
section "Command tests"

cmd_pass=0
cmd_fail=0

for cmd_md in commands/*.md; do
  cmd_name="$(basename "$cmd_md")"
  frontmatter=$(sed -n '/^---$/,/^---$/p' "$cmd_md" | sed '1d;$d')

  if [[ -z "$frontmatter" ]]; then
    fail "command '$cmd_name': has YAML frontmatter"
    cmd_fail=$((cmd_fail + 1))
    continue
  fi

  ok=true
  if ! echo "$frontmatter" | grep -qE "^description:"; then
    fail "command '$cmd_name': frontmatter has 'description'"
    ok=false
    cmd_fail=$((cmd_fail + 1))
  fi
  if ! echo "$frontmatter" | grep -qE "^allowed-tools:"; then
    fail "command '$cmd_name': frontmatter has 'allowed-tools'"
    ok=false
    cmd_fail=$((cmd_fail + 1))
  fi

  if $ok; then
    cmd_pass=$((cmd_pass + 1))
  fi
done

pass "Commands with valid frontmatter: $cmd_pass"
if [[ $cmd_fail -gt 0 ]]; then
  fail "Commands with issues: $cmd_fail"
fi

# ─────────────────────────────────────────────────────────────────────────────────
# 4. Agent tests
# ─────────────────────────────────────────────────────────────────────────────────
section "Agent tests"

agent_pass=0
agent_fail=0

for agent_md in agents/*.md; do
  agent_name="$(basename "$agent_md")"
  frontmatter=$(sed -n '/^---$/,/^---$/p' "$agent_md" | sed '1d;$d')

  if [[ -z "$frontmatter" ]]; then
    fail "agent '$agent_name': has YAML frontmatter"
    agent_fail=$((agent_fail + 1))
    continue
  fi

  ok=true
  if ! echo "$frontmatter" | grep -qE "^name:"; then
    fail "agent '$agent_name': frontmatter has 'name'"
    ok=false
    agent_fail=$((agent_fail + 1))
  fi
  if ! echo "$frontmatter" | grep -qE "^description:"; then
    fail "agent '$agent_name': frontmatter has 'description'"
    ok=false
    agent_fail=$((agent_fail + 1))
  fi

  if $ok; then
    agent_pass=$((agent_pass + 1))
  fi
done

pass "Agents with valid frontmatter: $agent_pass"
if [[ $agent_fail -gt 0 ]]; then
  fail "Agents with issues: $agent_fail"
fi

# ─────────────────────────────────────────────────────────────────────────────────
# 5. Count verification
# ─────────────────────────────────────────────────────────────────────────────────
section "Count verification"

skill_count=$(find skills -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
cmd_count=$(find commands -maxdepth 1 -name '*.md' -type f | wc -l | tr -d ' ')
agent_count=$(find agents -maxdepth 1 -name '*.md' -type f | wc -l | tr -d ' ')
hook_count=$(find hooks -maxdepth 1 -name '*.json' -type f | wc -l | tr -d ' ')

if [[ "$skill_count" -eq 100 ]]; then
  pass "Exactly 100 skill directories (found $skill_count)"
else
  fail "Exactly 100 skill directories (found $skill_count)"
fi

if [[ "$cmd_count" -eq 15 ]]; then
  pass "Exactly 15 command files (found $cmd_count)"
else
  fail "Exactly 15 command files (found $cmd_count)"
fi

if [[ "$agent_count" -eq 11 ]]; then
  pass "Exactly 11 agent files (found $agent_count)"
else
  fail "Exactly 11 agent files (found $agent_count)"
fi

if [[ "$hook_count" -eq 1 ]]; then
  pass "Exactly 1 hooks file (found $hook_count)"
else
  fail "Exactly 1 hooks file (found $hook_count)"
fi

# ─────────────────────────────────────────────────────────────────────────────────
# 6. Cross-reference tests
# ─────────────────────────────────────────────────────────────────────────────────
section "Cross-reference tests"

# Each persona-* skill should have a matching agent
persona_ok=true
for persona_dir in skills/persona-*; do
  persona_name="$(basename "$persona_dir" | sed 's/^persona-//')"
  if [[ ! -f "agents/${persona_name}.md" ]]; then
    fail "persona skill 'persona-${persona_name}' has matching agent '${persona_name}.md'"
    persona_ok=false
  fi
done

if $persona_ok; then
  pass "All persona-* skills have matching agents"
fi

# plugin.json version matches CHANGELOG latest version
plugin_version=$(jq -r '.version' .claude-plugin/plugin.json)
changelog_version=$(grep -oE '\[([0-9]+\.[0-9]+\.[0-9]+)\]' CHANGELOG.md | head -1 | tr -d '[]')

if [[ "$plugin_version" == "$changelog_version" ]]; then
  pass "plugin.json version ($plugin_version) matches CHANGELOG latest ($changelog_version)"
else
  fail "plugin.json version ($plugin_version) matches CHANGELOG latest ($changelog_version)"
fi

# ─────────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────────
printf "\n══ Summary ══\n"
printf "  Passed: %d\n" "$PASS_COUNT"
printf "  Failed: %d\n" "$FAIL_COUNT"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  printf "\nResult: FAIL\n"
  exit 1
else
  printf "\nResult: ALL PASS\n"
  exit 0
fi
