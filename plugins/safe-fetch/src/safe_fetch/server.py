"""FastMCP server — exposes fetch, search, and check_url tools."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv

# Load project .env first (higher priority), then ~/.env (fallback).
# Existing env vars (e.g. from .mcp.json) take precedence over both.
load_dotenv(override=False)
load_dotenv(Path.home() / ".env", override=False)

import httpx
from mcp.server.fastmcp import FastMCP

from .extractor import extract_by_content_type, truncate_to_tokens
from .rate_limiter import RateLimiter, RateLimitError
from .sanitizer import sanitize_html, sanitize_text, frame_content
from .url_policy import (
    validate_url,
    validate_and_resolve,
    check_url_safety,
    URLPolicyError,
)

# Logging to stderr (stdout is reserved for JSON-RPC)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [safe-fetch] %(levelname)s %(message)s",
)
log = logging.getLogger("safe-fetch")

mcp = FastMCP(
    "safe-fetch",
    instructions="Sanitizing web fetch — strips prompt injection vectors before content reaches the LLM.",
)

_rate_limiter = RateLimiter()

_USER_AGENT = os.environ.get(
    "SAFE_FETCH_USER_AGENT",
    "Mozilla/5.0 (compatible; safe-fetch-mcp/0.1; +https://github.com/anthropics/claude-code)",
)
_TIMEOUT = float(os.environ.get("SAFE_FETCH_TIMEOUT", "30"))
_MAX_BODY = int(os.environ.get("SAFE_FETCH_MAX_BODY", str(5 * 1024 * 1024)))  # 5 MB
_MAX_REDIRECTS = 5


class _BodyTooLarge(Exception):
    """Raised when a response body exceeds _MAX_BODY (checked incrementally)."""


class _TooManyRedirects(Exception):
    """Raised when a redirect chain exceeds _MAX_REDIRECTS hops."""


def _pin_to_ip(url: str, ip: str) -> str:
    """Return *url* with its host replaced by *ip* (IPv6 bracketed, port kept).

    The connection is made to this IP-based URL while the original hostname is
    carried in the Host header and SNI, so the HTTP client never performs a
    second DNS resolution. TLS still verifies the certificate against the
    hostname (via the SNI extension), not the IP.
    """
    parsed = urlparse(url)
    host_for_url = f"[{ip}]" if ":" in ip else ip
    netloc = f"{host_for_url}:{parsed.port}" if parsed.port else host_for_url
    return parsed._replace(netloc=netloc).geturl()


async def _fetch_pinned(
    start_url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bytes, str, str]:
    """Fetch *start_url*, following redirects safely. Returns (body, content_type, final_url).

    Security properties (closing two HIGH SSRF findings):
      - Every hop — the initial URL AND each redirect target — is re-run through
        ``validate_and_resolve`` (allowlist + private/metadata IP guard). httpx's
        own ``follow_redirects`` is OFF; redirects to internal hosts are blocked.
      - Each hop connects to the exact IP the policy validated (Host + SNI
        preserved), so a DNS-rebinding answer between check and connect cannot
        redirect the socket to an internal address.
      - The body cap is enforced incrementally while streaming, so an oversized
        body or decompression bomb is aborted before it is fully buffered.

    ``transport`` is for tests (inject an ``httpx.MockTransport``); production
    passes None and uses the default transport with TLS verification.
    """
    client = httpx.AsyncClient(
        follow_redirects=False,
        timeout=_TIMEOUT,
        transport=transport,
    )
    try:
        # current_url is always hostname-based (for policy checks + relative-redirect joins).
        current_url = start_url
        for _hop in range(_MAX_REDIRECTS + 1):
            normalized, pinned_ip = validate_and_resolve(current_url)
            host = urlparse(normalized).hostname or ""
            request_url = _pin_to_ip(normalized, pinned_ip)
            headers = {"User-Agent": _USER_AGENT, "Host": host}

            async with client.stream(
                "GET",
                request_url,
                headers=headers,
                extensions={"sni_hostname": host},
            ) as response:
                if response.is_redirect and "location" in response.headers:
                    # Resolve the redirect against the hostname URL, not the IP URL,
                    # so a relative Location keeps the right host for the next check.
                    current_url = urljoin(normalized, response.headers["location"])
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "text/html")

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > _MAX_BODY:
                        raise _BodyTooLarge(
                            f"[TOO LARGE] Response body exceeds {_MAX_BODY} bytes"
                        )
                    chunks.append(chunk)
                return b"".join(chunks), content_type, normalized

        raise _TooManyRedirects()
    finally:
        await client.aclose()


@mcp.tool()
async def fetch(url: str, prompt: str = "", max_tokens: int = 0) -> str:
    """Fetch a URL and return sanitized markdown content.

    The content is sanitized to remove prompt injection vectors including:
    - CSS-hidden text, HTML comments, script/style tags
    - Fake LLM delimiters, zero-width Unicode, bidi overrides
    - Base64-encoded instruction payloads
    - Markdown image exfiltration URLs

    Supports HTML pages, PDFs, JSON, and plain text.

    Args:
        url: The URL to fetch (http/https only)
        prompt: Optional — focus extraction on this topic (e.g. "extract the API reference section")
        max_tokens: Optional — truncate output to approximately this many tokens (0 = no limit)
    """
    # Layer 1: URL validation
    try:
        validated_url = validate_url(url)
    except URLPolicyError as e:
        return f"[BLOCKED] {e}"

    # Layer 2: Rate limiting
    domain = urlparse(validated_url).hostname or "unknown"
    try:
        _rate_limiter.check(domain)
    except RateLimitError as e:
        return f"[RATE LIMITED] {e}"

    # Layer 3: Fetch — manual redirect loop with per-hop policy re-validation,
    # IP-pinned connections, and incremental size enforcement.
    try:
        body, content_type, validated_url = await _fetch_pinned(validated_url)
    except URLPolicyError as e:
        # A redirect pointed at a disallowed / private / metadata host.
        return f"[BLOCKED] {e}"
    except _BodyTooLarge as e:
        return str(e)
    except _TooManyRedirects:
        return "[BLOCKED] too many redirects (possible SSRF redirect chain)"
    except httpx.HTTPStatusError as e:
        return f"[HTTP ERROR] {e.response.status_code}: {e.response.reason_phrase}"
    except httpx.RequestError as e:
        return f"[REQUEST ERROR] {type(e).__name__}: {e}"

    log.info(
        "Fetched %s (%s, %d bytes)",
        validated_url,
        content_type.split(";")[0],
        len(body),
    )

    # Layer 4–5: Extract + sanitize
    ct = content_type.lower().split(";")[0].strip()
    if ct.startswith("text/html") or ct.startswith("application/xhtml"):
        html_str = body.decode("utf-8", errors="replace")
        clean_html = sanitize_html(html_str)
        extracted = extract_by_content_type(clean_html, content_type, validated_url)
    else:
        extracted = extract_by_content_type(body, content_type, validated_url)

    sanitized = sanitize_text(extracted)

    # Dynamic filtering: if prompt is given, add it as extraction context
    if prompt:
        sanitized = f"[Extraction focus: {prompt}]\n\n{sanitized}"

    # Token truncation
    if max_tokens > 0:
        sanitized = truncate_to_tokens(sanitized, max_tokens)

    # Layer 6: Context framing
    return frame_content(sanitized, validated_url)


@mcp.tool()
async def search(
    query: str,
    num_results: int = 5,
    country: str = "",
    city: str = "",
) -> str:
    """Search the web and return sanitized results.

    Uses the configured search API (Brave Search by default).
    Requires BRAVE_API_KEY environment variable.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5, max: 20)
        country: Optional — 2-letter country code for localized results (e.g. "US", "GB", "DE")
        city: Optional — city name for localized results (e.g. "San Francisco")
    """
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return (
            "[CONFIGURATION ERROR] No search API key configured. "
            "Set BRAVE_API_KEY environment variable to enable web search. "
            "Get a free key at https://brave.com/search/api/"
        )

    num_results = min(max(1, num_results), 20)

    params: dict[str, str | int] = {"q": query, "count": num_results}
    if country:
        params["country"] = country.upper()
    if city:
        # Brave Search uses 'city' in the search_lang or as part of query refinement
        params["q"] = f"{query} {city}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params=params,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"[SEARCH ERROR] HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return f"[SEARCH ERROR] {type(e).__name__}: {e}"

    data = response.json()
    results = data.get("web", {}).get("results", [])

    if not results:
        return frame_content("No results found.", f"search:{query}")

    lines = []
    for i, r in enumerate(results, 1):
        title = sanitize_text(r.get("title", ""))
        desc = sanitize_text(r.get("description", ""))
        url = r.get("url", "")
        lines.append(f"{i}. **{title}**\n   {url}\n   {desc}")

    return frame_content("\n\n".join(lines), f"search:{query}")


@mcp.tool()
async def check_url(url: str) -> str:
    """Check if a URL is safe to fetch without actually fetching it.

    Validates the URL against the domain allowlist, blocklist,
    and SSRF prevention rules.

    Args:
        url: The URL to check
    """
    result = check_url_safety(url)
    if result["safe"]:
        return f"[SAFE] {result['reason']}"
    else:
        return f"[BLOCKED] {result['reason']}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
