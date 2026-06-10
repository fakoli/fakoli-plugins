# Changelog

## 1.1.0 — 2026-06-10

Security hardening release. Two independent warden-methodology audits converged on the same two HIGH SSRF findings in the fetch path; both are closed here, along with a DoS and a startup-crash bug found in the same pass. The `fetch` tool's signature is unchanged.

### Security
- **Fixed (HIGH): SSRF via unvalidated redirects.** `fetch` followed up to 5 redirects with `follow_redirects=True`, but only the *initial* URL was policy-checked — a fetched page returning `302 Location: http://169.254.169.254/…` (or `127.0.0.1`, RFC-1918) was followed straight to the internal target, bypassing both the private-IP guard and the `ALLOWED_DOMAINS` allowlist. The fetch now follows redirects manually and re-runs the full policy (allowlist + private/metadata-IP guard) on **every hop**.
- **Fixed (HIGH): SSRF via DNS-rebinding TOCTOU.** `validate_url` resolved the hostname and checked the IPs, then handed the *hostname* to httpx, which re-resolved independently at connect time — a short-TTL attacker could answer public during validation and private at connect. New `validate_and_resolve()` resolves once and returns the validated IP; the connection is **pinned to that IP** (with the original Host header and SNI preserved, so TLS still verifies against the hostname). Verified end-to-end over real TLS and with a mismatched-hostname negative test.
- **Fixed (MEDIUM): unbounded body buffering (DoS).** `_MAX_BODY` was checked only *after* `response.content` had already materialized the entire body, so a multi-GB response or a gzip decompression bomb could OOM the process before the cap applied. The body is now streamed and the cap enforced incrementally, aborting once the cumulative size exceeds the limit.

### Fixed
- **Startup crash on current `mcp` (≥ the locked 1.26.0):** `FastMCP(description=…)` raised `TypeError: unexpected keyword argument 'description'` — `FastMCP` renamed that parameter to `instructions`. The server failed at import (i.e. would not launch at all) on a fresh install; switched to `instructions=`. The existing test suite missed this because no test imported `server`; a new test now does.

### Added
- `tests/test_fetch_security.py` — 11 offline tests (httpx `MockTransport`) covering redirect-to-private-host blocking, the redirect cap, IP-pinned connections, and incremental body-cap enforcement; plus unit tests for the IP-rewrite helper (IPv4/IPv6/port).

## 1.0.6 — 2026-06-10
- Fix: block hooks emitted only the legacy top-level `decision: block` shape, which current Claude Code versions ignore — the WebFetch/WebSearch blocks were silently inoperative. Both scripts now emit `hookSpecificOutput.permissionDecision: "deny"` (current contract) alongside the legacy fields, build the payload via `json.dumps` (a URL/query containing quotes can no longer corrupt the JSON into a fail-open), and keep a static both-schema fallback if python3 is unavailable. Same bug class Greptile flagged in fakoli-flow's gate-check.sh (#79)

## 1.0.5 — 2026-03-21
- Fix pyproject.toml: sync project name and version with plugin manifest

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
