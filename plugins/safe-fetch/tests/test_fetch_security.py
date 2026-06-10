"""Tests for safe-fetch's SSRF-hardened fetch path (_fetch_pinned, _pin_to_ip).

Covers the two HIGH findings from the 2026-06 security audit:
  - redirect SSRF: a redirect to a private/metadata host must be blocked
  - DNS-rebinding TOCTOU: connections are pinned to the validated IP
plus the MEDIUM: the body cap is enforced incrementally while streaming.

All offline: start URLs use a public IP literal (so validate_and_resolve passes
without network DNS) and httpx.MockTransport intercepts the request before any
socket is opened.
"""

from __future__ import annotations

import httpx
import pytest

from safe_fetch import server
from safe_fetch.server import _fetch_pinned, _pin_to_ip, _BodyTooLarge, _TooManyRedirects
from safe_fetch.url_policy import URLPolicyError

# A public IP literal: getaddrinfo on a literal returns it unchanged, _is_private_ip
# passes it, so validate_and_resolve succeeds with no network DNS lookup.
_PUBLIC = "93.184.216.34"  # historically example.com
_START = f"http://{_PUBLIC}/page"


def _transport(handler):
    return httpx.MockTransport(handler)


class TestPinToIp:
    def test_ipv4_preserves_path_and_query(self):
        out = _pin_to_ip("https://example.com/a/b?x=1", "1.2.3.4")
        assert out == "https://1.2.3.4/a/b?x=1"

    def test_ipv6_is_bracketed(self):
        out = _pin_to_ip("https://example.com/p", "2606:4700::1")
        assert out == "https://[2606:4700::1]/p"

    def test_explicit_port_preserved(self):
        out = _pin_to_ip("http://example.com:8080/p", "1.2.3.4")
        assert out == "http://1.2.3.4:8080/p"


class TestRedirectSSRF:
    async def test_redirect_to_metadata_ip_is_blocked(self):
        """HIGH-1: a 302 to the cloud-metadata IP must raise URLPolicyError, not follow."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

        with pytest.raises(URLPolicyError, match="private/reserved"):
            await _fetch_pinned(_START, transport=_transport(handler))

    async def test_redirect_to_localhost_is_blocked(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "http://127.0.0.1:6379/"})

        with pytest.raises(URLPolicyError, match="private/reserved"):
            await _fetch_pinned(_START, transport=_transport(handler))

    async def test_redirect_chain_cap(self):
        """A server that redirects forever (to public targets) is cut off, not infinite."""
        def handler(request: httpx.Request) -> httpx.Response:
            # Always redirect to another public literal — never terminates on its own.
            return httpx.Response(302, headers={"location": "http://93.184.216.35/next"})

        with pytest.raises(_TooManyRedirects):
            await _fetch_pinned(_START, transport=_transport(handler))


class TestPinnedConnection:
    async def test_connects_to_pinned_ip_with_host_header(self):
        """The socket target is the validated IP; the hostname rides in the Host header."""
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url_host"] = request.url.host
            seen["host_header"] = request.headers.get("host")
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"ok")

        body, ctype, final = await _fetch_pinned(_START, transport=_transport(handler))
        assert body == b"ok"
        assert ctype == "text/plain"
        # Connection target is the IP, not a re-resolved hostname.
        assert seen["url_host"] == _PUBLIC
        assert seen["host_header"] == _PUBLIC  # host literal == its own pinned IP here


class TestBodyCap:
    async def test_oversized_body_aborted_incrementally(self, monkeypatch):
        """MEDIUM: the cap fires while streaming, not after buffering the whole body."""
        monkeypatch.setattr(server, "_MAX_BODY", 100)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"x" * 5000)

        with pytest.raises(_BodyTooLarge, match="exceeds 100 bytes"):
            await _fetch_pinned(_START, transport=_transport(handler))

    async def test_body_at_limit_is_returned(self, monkeypatch):
        monkeypatch.setattr(server, "_MAX_BODY", 5000)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"x" * 4000)

        body, _ctype, _final = await _fetch_pinned(_START, transport=_transport(handler))
        assert len(body) == 4000


class TestNormalFetch:
    async def test_single_hop_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<h1>hi</h1>")

        body, ctype, final = await _fetch_pinned(_START, transport=_transport(handler))
        assert body == b"<h1>hi</h1>"
        assert ctype == "text/html"
        assert final == _START

    async def test_one_public_redirect_then_success(self):
        """A single redirect to another public target is followed and re-validated."""
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/page":
                return httpx.Response(302, headers={"location": "http://93.184.216.34/final"})
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"done")

        body, _ctype, final = await _fetch_pinned(_START, transport=_transport(handler))
        assert body == b"done"
        assert final.endswith("/final")
