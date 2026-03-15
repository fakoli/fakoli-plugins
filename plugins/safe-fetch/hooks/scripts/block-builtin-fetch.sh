#!/usr/bin/env bash
# PreToolUse hook: blocks the built-in WebFetch tool and redirects to safe-fetch.
#
# This ensures all web fetching goes through the sanitization pipeline,
# even if Claude's default behavior is to use its own WebFetch tool.

# Extract the URL from the tool input for the redirect message
INPUT=$(cat)
URL=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
print(tool_input.get('url', 'the requested URL'))
" 2>/dev/null || echo "the requested URL")

cat <<EOF
{
  "decision": "block",
  "reason": "The built-in WebFetch tool is disabled by security policy. Use the safe-fetch MCP tools instead, which sanitize content to prevent prompt injection.\n\nTo fetch this URL safely, use: mcp__safe-fetch__fetch with url=\"${URL}\"\n\nThe safe-fetch tool strips hidden text, fake LLM delimiters, zero-width characters, and exfiltration URLs before content reaches your context."
}
EOF
