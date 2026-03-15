#!/usr/bin/env bash
# PreToolUse hook: blocks the built-in WebSearch tool and redirects to safe-fetch.

INPUT=$(cat)
QUERY=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
print(tool_input.get('query', 'the requested query'))
" 2>/dev/null || echo "the requested query")

cat <<EOF
{
  "decision": "block",
  "reason": "The built-in WebSearch tool is disabled by security policy. Use the safe-fetch MCP tools instead, which sanitize results to prevent prompt injection.\n\nTo search safely, use: mcp__safe-fetch__search with query=\"${QUERY}\"\n\nThe safe-fetch search tool strips hidden text, fake LLM delimiters, and exfiltration URLs from all results."
}
EOF
