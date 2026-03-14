# Changelog

## [1.0.0] - 2026-03-14

### Added
- Initial release
- MCP server with `fetch`, `search`, and `check_url` tools
- 6-layer sanitization pipeline (URL policy, rate limiting, HTTP fetch, HTML sanitization, text sanitization, context framing)
- 14 attack vector defenses (CSS-hidden text, fake LLM delimiters, zero-width Unicode, base64 payloads, markdown exfiltration, SSRF, etc.)
- PDF extraction via PyMuPDF
- `prompt` parameter for focused content extraction
- `max_tokens` parameter for content truncation
- Geo-localized search via `country`/`city` parameters
- PreToolUse hooks to block built-in WebFetch/WebSearch and redirect to safe-fetch
- PostToolUse hook to warn on curl/wget usage
- `/fetch`, `/search`, `/check-url` slash commands
- `web-researcher` autonomous research agent
- 83 unit tests covering all attack vectors, SSRF, rate limiting, extraction
- Performance optimized: combined regex patterns, `str.translate()` for char removal, pre-compiled XPath
