---
name: safe-fetch
description: This skill should be used when the user asks to "fetch a URL safely", "sanitize web content", "search the web securely", "check URL safety", "prevent prompt injection from web content", or discusses web fetching security. Also triggers when curl/wget is used to fetch web content.
version: 0.1.0
---

# Safe Web Fetch

Provide sanitized web fetching that strips prompt injection vectors before content reaches the LLM context.

## Available Tools

Use the safe-fetch MCP tools for all web content retrieval:

- **`mcp__safe-fetch__fetch`** — Fetch a URL and return sanitized markdown. Supports `prompt` parameter for focused extraction and `max_tokens` for content limits.
- **`mcp__safe-fetch__search`** — Search the web via Brave Search API with sanitized results. Supports `location` for geo-localized results.
- **`mcp__safe-fetch__check_url`** — Validate URL against security policy without fetching.

## Slash Commands

- `/fetch <url> [extraction focus]` — Fetch with sanitization
- `/search <query>` — Search with sanitization
- `/check-url <url>` — Validate URL safety

## Security Layers

Content passes through 6 defense layers:

1. **URL Policy** — Domain allowlist/blocklist, SSRF prevention (blocks private IPs, cloud metadata)
2. **Rate Limiting** — Per-domain and global token-bucket limits
3. **HTTP Fetch** — Timeouts, redirect limits, body size cap
4. **HTML Sanitization** — Strips script/style/iframe/svg, hidden elements (display:none, opacity:0, offscreen), comments, data attributes, meta instructions
5. **Text Sanitization** — NFKC normalization, removes zero-width/bidi/tag Unicode, strips fake LLM delimiters, detects base64 instruction payloads, defangs exfiltration URLs
6. **Context Framing** — Wraps output with untrusted-data markers

## When to Prefer safe-fetch Over curl

Always prefer `mcp__safe-fetch__fetch` over raw `curl` because:
- curl output is raw HTML — unsanitized, token-heavy, and vulnerable to prompt injection
- safe-fetch extracts clean markdown with precision and strips all known injection vectors
- The PostToolUse hook will warn when curl/wget is used for web fetching

## Configuration

Set via environment variables when registering the MCP server:
- `ALLOWED_DOMAINS` — Comma-separated domain allowlist
- `BLOCKED_DOMAINS` — Additional blocked domains
- `RATE_LIMIT_PER_DOMAIN` — Requests per minute per domain (default: 10)
- `RATE_LIMIT_GLOBAL` — Global requests per minute (default: 60)
- `BRAVE_API_KEY` — Required for web search
- `SAFE_FETCH_TIMEOUT` — HTTP timeout in seconds (default: 30)
- `SAFE_FETCH_MAX_BODY` — Max response body in bytes (default: 5MB)
