#!/bin/bash
# Discovers skill and agent names from the plugin directory structure.
# Sourced by other hook scripts. Requires CLAUDE_PLUGIN_ROOT to be set.
#
# Exports:
#   SKILL_NAMES        — pipe-delimited skill directory names (e.g. "complexity-mapper|decision-brief|...")
#   AGENT_NAMES        — pipe-delimited agent file names without .md (e.g. "doc-reader|caveat-extractor|...")
#   INVOCATION_PATTERNS — regex matching actual agent/skill invocations in transcript JSON
#
# Uses only bash builtins (globs + parameter expansion). This file is sourced
# by hooks that run on every user prompt, and under Git Bash on Windows each
# subprocess spawn costs 100-700ms — an ls|tr|sed pipeline here was enough to
# blow the UserPromptSubmit hook timeout.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-${BASH_SOURCE[0]%/*}/..}"

# Discover skills from skills/ subdirectories
SKILL_NAMES=""
for _d in "$PLUGIN_ROOT/skills"/*/; do
  [ -d "$_d" ] || continue
  _d="${_d%/}"
  SKILL_NAMES="${SKILL_NAMES}|${_d##*/}"
done
SKILL_NAMES="${SKILL_NAMES#|}"

# Discover agents from agents/*.md files (strip .md extension)
AGENT_NAMES=""
for _f in "$PLUGIN_ROOT/agents"/*.md; do
  [ -f "$_f" ] || continue
  _f="${_f##*/}"
  AGENT_NAMES="${AGENT_NAMES}|${_f%.md}"
done
AGENT_NAMES="${AGENT_NAMES#|}"
unset _d _f

# Build invocation patterns for transcript matching (actual tool calls, not mentions)
INVOCATION_PATTERNS='"subagent_type"\s*:\s*"systems-thinking:|"skill"\s*:\s*"systems-thinking:'
if [ -n "$AGENT_NAMES" ]; then
  INVOCATION_PATTERNS="${INVOCATION_PATTERNS}|\"subagent_type\"\s*:\s*\"(${AGENT_NAMES})\""
fi
if [ -n "$SKILL_NAMES" ]; then
  INVOCATION_PATTERNS="${INVOCATION_PATTERNS}|\"skill\"\s*:\s*\"(${SKILL_NAMES})\""
fi
INVOCATION_PATTERNS="(${INVOCATION_PATTERNS})"
