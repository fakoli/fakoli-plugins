"""URL validation, domain allowlist/blocklist, and SSRF prevention."""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse


# Cloud metadata endpoints commonly targeted in SSRF
_METADATA_IPS = frozenset(
    {
        "169.254.169.254",  # AWS / GCP / Azure
        "100.100.100.200",  # Alibaba Cloud
        "fd00:ec2::254",  # AWS IPv6
    }
)

_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
    }
)


def _load_domain_list(env_var: str) -> frozenset[str] | None:
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return None
    return frozenset(d.strip().lower() for d in raw.split(",") if d.strip())


def _get_allowed_domains() -> frozenset[str] | None:
    return _load_domain_list("ALLOWED_DOMAINS")


def _get_blocked_domains() -> frozenset[str]:
    extra = _load_domain_list("BLOCKED_DOMAINS") or frozenset()
    return _BLOCKED_HOSTS | extra


def _is_private_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # Can't parse → block
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or ip_str in _METADATA_IPS
    )


class URLPolicyError(Exception):
    pass


def validate_url(url: str) -> str:
    """Validate a URL against the security policy. Returns the normalized URL.

    Back-compatible wrapper around :func:`validate_and_resolve` for callers that
    only need the pass/fail decision (``check_url_safety``, tests). Code that
    actually connects should use :func:`validate_and_resolve` and pin the
    connection to the returned IP — see that function's docstring for why.
    """
    normalized, _ip = validate_and_resolve(url)
    return normalized


def validate_and_resolve(url: str) -> tuple[str, str]:
    """Validate a URL against the policy and return ``(normalized_url, pinned_ip)``.

    The second element is one of the addresses that ``getaddrinfo`` returned and
    that passed the private/reserved check. Callers MUST connect to *that* IP
    (with the original Host header and SNI preserved) rather than letting the
    HTTP client re-resolve the hostname.

    Why: validating the hostname and then handing the *hostname* to an HTTP
    client lets the client perform a second, independent DNS resolution at
    connect time. An attacker controlling DNS with a short TTL can answer with a
    public IP during validation and a private/metadata IP at connect — a
    DNS-rebinding TOCTOU that defeats the SSRF guard entirely. Returning the
    exact validated IP closes that gap: resolution happens once, here.
    """
    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        raise URLPolicyError(
            f"Blocked scheme: {parsed.scheme!r}. Only http/https allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise URLPolicyError("No hostname in URL.")

    hostname_lower = hostname.lower()

    # Blocked hosts
    blocked = _get_blocked_domains()
    if hostname_lower in blocked:
        raise URLPolicyError(f"Blocked host: {hostname_lower}")

    # Allowlist check
    allowed = _get_allowed_domains()
    if allowed is not None:
        # Check if hostname or any parent domain is in the allowlist
        parts = hostname_lower.split(".")
        match = False
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate in allowed:
                match = True
                break
        if not match:
            raise URLPolicyError(
                f"Domain {hostname_lower!r} not in allowlist. "
                f"Allowed: {', '.join(sorted(allowed))}"
            )

    # SSRF prevention: resolve once, require EVERY resolved address to be safe,
    # and keep the first safe address to pin the connection to.
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise URLPolicyError(f"Cannot resolve hostname: {hostname}")

    pinned_ip: str | None = None
    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip_str = sockaddr[0]
        if _is_private_ip(ip_str):
            raise URLPolicyError(
                f"SSRF blocked: {hostname} resolves to private/reserved IP {ip_str}"
            )
        if pinned_ip is None:
            pinned_ip = ip_str

    if pinned_ip is None:
        # getaddrinfo returned no usable address (empty result is rare but possible)
        raise URLPolicyError(f"Cannot resolve hostname to a usable address: {hostname}")

    return url, pinned_ip


def check_url_safety(url: str) -> dict:
    """Check URL safety without fetching. Returns a status dict."""
    try:
        validated = validate_url(url)
        return {
            "safe": True,
            "url": validated,
            "reason": "URL passes all policy checks.",
        }
    except URLPolicyError as e:
        return {"safe": False, "url": url, "reason": str(e)}
