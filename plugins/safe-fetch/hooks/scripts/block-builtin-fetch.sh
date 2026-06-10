#!/usr/bin/env bash
# PreToolUse hook: blocks the built-in WebFetch tool and redirects to safe-fetch.
#
# This ensures all web fetching goes through the sanitization pipeline,
# even if Claude's default behavior is to use its own WebFetch tool.
#
# Emits both the current PreToolUse contract (hookSpecificOutput.permissionDecision)
# and the legacy top-level decision/reason fields for older Claude Code versions.
# The whole payload is built with json.dumps so a URL containing quotes or
# backslashes can never produce malformed JSON (which would silently fail open).

INPUT=$(cat)
echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    url = data.get('tool_input', {}).get('url', 'the requested URL')
except Exception:
    url = 'the requested URL'
reason = (
    'The built-in WebFetch tool is disabled by security policy. Use the safe-fetch '
    'MCP tools instead, which sanitize content to prevent prompt injection.\n\n'
    f'To fetch this URL safely, use: mcp__safe-fetch__fetch with url=\"{url}\"\n\n'
    'The safe-fetch tool strips hidden text, fake LLM delimiters, zero-width '
    'characters, and exfiltration URLs before content reaches your context.'
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
  "reason": "The built-in WebFetch tool is disabled by security policy. Use the safe-fetch MCP tools instead (mcp__safe-fetch__fetch), which sanitize content to prevent prompt injection.",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "The built-in WebFetch tool is disabled by security policy. Use the safe-fetch MCP tools instead (mcp__safe-fetch__fetch), which sanitize content to prevent prompt injection."
  }
}
EOF
