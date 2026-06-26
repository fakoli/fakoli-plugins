#!/bin/bash
# Discovers skill and agent names from the plugin directory structure.
# Sourced by other hook scripts. Requires CLAUDE_PLUGIN_ROOT to be set.
#
# Exports:
#   SKILL_NAMES        — pipe-delimited skill directory names (e.g. "complexity-mapper|decision-brief|...")
#   AGENT_NAMES        — pipe-delimited agent file names without .md (e.g. "doc-reader|caveat-extractor|...")
#   INVOCATION_PATTERNS — regex matching actual agent/skill invocations in transcript JSON

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# jq is required for parsing hook stdin JSON. If missing, set a flag so
# callers can decide how to handle it (approve silently vs warn).
JQ_AVAILABLE=true
if ! command -v jq > /dev/null 2>&1; then
  JQ_AVAILABLE=false
fi

# Discover skills from skills/ subdirectories
SKILL_NAMES=""
if [ -d "$PLUGIN_ROOT/skills" ]; then
  SKILL_NAMES=$(ls -1 "$PLUGIN_ROOT/skills" 2>/dev/null | tr '\n' '|' | sed 's/|$//')
fi

# Discover agents from agents/*.md files (strip .md extension)
AGENT_NAMES=""
if [ -d "$PLUGIN_ROOT/agents" ]; then
  AGENT_NAMES=$(ls -1 "$PLUGIN_ROOT/agents" 2>/dev/null | sed 's/\.md$//' | tr '\n' '|' | sed 's/|$//')
fi

# Build invocation patterns for transcript matching (actual tool calls, not mentions)
INVOCATION_PATTERNS='"subagent_type"\s*:\s*"systems-thinking:|"skill"\s*:\s*"systems-thinking:'
if [ -n "$AGENT_NAMES" ]; then
  INVOCATION_PATTERNS="${INVOCATION_PATTERNS}|\"subagent_type\"\s*:\s*\"(${AGENT_NAMES})\""
fi
if [ -n "$SKILL_NAMES" ]; then
  INVOCATION_PATTERNS="${INVOCATION_PATTERNS}|\"skill\"\s*:\s*\"(${SKILL_NAMES})\""
fi
INVOCATION_PATTERNS="(${INVOCATION_PATTERNS})"
