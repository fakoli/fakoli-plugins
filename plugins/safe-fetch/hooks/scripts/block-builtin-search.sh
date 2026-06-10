#!/usr/bin/env bash
# PreToolUse hook: blocks the built-in WebSearch tool and redirects to safe-fetch.
#
# Emits both the current PreToolUse contract (hookSpecificOutput.permissionDecision)
# and the legacy top-level decision/reason fields for older Claude Code versions.
# The whole payload is built with json.dumps so a query containing quotes or
# backslashes can never produce malformed JSON (which would silently fail open).

INPUT=$(cat)
echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    query = data.get('tool_input', {}).get('query', 'the requested query')
except Exception:
    query = 'the requested query'
reason = (
    'The built-in WebSearch tool is disabled by security policy. Use the safe-fetch '
    'MCP tools instead, which sanitize results to prevent prompt injection.\n\n'
    f'To search safely, use: mcp__safe-fetch__search with query=\"{query}\"\n\n'
    'The safe-fetch search tool strips hidden text, fake LLM delimiters, and '
    'exfiltration URLs from all results.'
)
print(json.dumps({
    'decision': 'block',
    'reason': reason,
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason,
    },
}))
" 2>/dev/null || cat <<'EOF'
{
  "decision": "block",
  "reason": "The built-in WebSearch tool is disabled by security policy. Use the safe-fetch MCP tools instead (mcp__safe-fetch__search), which sanitize results to prevent prompt injection.",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "The built-in WebSearch tool is disabled by security policy. Use the safe-fetch MCP tools instead (mcp__safe-fetch__search), which sanitize results to prevent prompt injection."
  }
}
EOF
