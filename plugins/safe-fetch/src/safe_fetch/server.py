"""FastMCP server — exposes fetch, search, and check_url tools."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load ~/.env first (lower priority), then project .env (higher priority).
# Existing env vars (e.g. from .mcp.json) take precedence over both.
load_dotenv(Path.home() / ".env", override=False)
load_dotenv(override=False)

import httpx
from mcp.server.fastmcp import FastMCP

from .extractor import extract_by_content_type, truncate_to_tokens
from .rate_limiter import RateLimiter, RateLimitError
from .sanitizer import sanitize_html, sanitize_text, frame_content
from .url_policy import validate_url, check_url_safety, URLPolicyError

# Logging to stderr (stdout is reserved for JSON-RPC)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [safe-fetch] %(levelname)s %(message)s",
)
log = logging.getLogger("safe-fetch")

mcp = FastMCP(
    "safe-fetch",
    description="Sanitizing web fetch — strips prompt injection vectors before content reaches the LLM.",
)

_rate_limiter = RateLimiter()

_USER_AGENT = os.environ.get(
    "SAFE_FETCH_USER_AGENT",
    "Mozilla/5.0 (compatible; safe-fetch-mcp/0.1; +https://github.com/anthropics/claude-code)",
)
_TIMEOUT = float(os.environ.get("SAFE_FETCH_TIMEOUT", "30"))
_MAX_BODY = int(os.environ.get("SAFE_FETCH_MAX_BODY", str(5 * 1024 * 1024)))  # 5 MB


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

    # Layer 3: Fetch
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=_TIMEOUT,
            max_redirects=5,
        ) as client:
            response = await client.get(
                validated_url,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"[HTTP ERROR] {e.response.status_code}: {e.response.reason_phrase}"
    except httpx.RequestError as e:
        return f"[REQUEST ERROR] {type(e).__name__}: {e}"

    # Size check
    body = response.content
    if len(body) > _MAX_BODY:
        return f"[TOO LARGE] Response body exceeds {_MAX_BODY} bytes ({len(body)} bytes received)"

    content_type = response.headers.get("content-type", "text/html")
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
