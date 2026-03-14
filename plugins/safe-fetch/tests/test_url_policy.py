"""Tests for URL policy — allowlist, blocklist, SSRF prevention."""

from __future__ import annotations

import pytest

from safe_fetch.url_policy import validate_url, check_url_safety, URLPolicyError


class TestSchemeValidation:
    def test_allows_https(self):
        # Will raise if DNS/SSRF check fails, but scheme is OK
        try:
            validate_url("https://example.com")
        except URLPolicyError as e:
            assert "scheme" not in str(e).lower()

    def test_allows_http(self):
        try:
            validate_url("http://example.com")
        except URLPolicyError as e:
            assert "scheme" not in str(e).lower()

    def test_blocks_ftp(self):
        with pytest.raises(URLPolicyError, match="Blocked scheme"):
            validate_url("ftp://example.com/file")

    def test_blocks_file(self):
        with pytest.raises(URLPolicyError, match="Blocked scheme"):
            validate_url("file:///etc/passwd")

    def test_blocks_javascript(self):
        with pytest.raises(URLPolicyError, match="Blocked scheme"):
            validate_url("javascript:alert(1)")

    def test_blocks_data(self):
        with pytest.raises(URLPolicyError, match="Blocked scheme"):
            validate_url("data:text/html,<h1>hi</h1>")


class TestSSRFPrevention:
    def test_blocks_localhost(self):
        with pytest.raises(URLPolicyError, match="SSRF"):
            validate_url("http://localhost/admin")

    def test_blocks_127_0_0_1(self):
        with pytest.raises(URLPolicyError, match="SSRF"):
            validate_url("http://127.0.0.1/admin")

    def test_blocks_private_10_x(self):
        with pytest.raises(URLPolicyError, match="SSRF"):
            validate_url("http://10.0.0.1/internal")

    def test_blocks_private_172_16(self):
        with pytest.raises(URLPolicyError, match="SSRF"):
            validate_url("http://172.16.0.1/internal")

    def test_blocks_private_192_168(self):
        with pytest.raises(URLPolicyError, match="SSRF"):
            validate_url("http://192.168.1.1/router")

    def test_blocks_aws_metadata(self):
        with pytest.raises(URLPolicyError, match="SSRF"):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_no_hostname(self):
        with pytest.raises(URLPolicyError, match="No hostname"):
            validate_url("http:///path")


class TestBlockedHosts:
    def test_blocks_metadata_google(self):
        with pytest.raises(URLPolicyError, match="Blocked host"):
            validate_url("http://metadata.google.internal/computeMetadata/v1/")


class TestAllowlist:
    def test_allowlist_permits_listed_domain(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_DOMAINS", "example.com,docs.python.org")
        # example.com should work (it resolves to a public IP)
        result = validate_url("https://example.com")
        assert result == "https://example.com"

    def test_allowlist_blocks_unlisted_domain(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_DOMAINS", "example.com")
        with pytest.raises(URLPolicyError, match="not in allowlist"):
            validate_url("https://evil.com")

    def test_allowlist_supports_subdomains(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_DOMAINS", "python.org")
        result = validate_url("https://docs.python.org/3/library/")
        assert "docs.python.org" in result

    def test_no_allowlist_allows_all_public(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_DOMAINS", raising=False)
        result = validate_url("https://example.com")
        assert result == "https://example.com"


class TestCheckUrlSafety:
    def test_safe_url(self):
        result = check_url_safety("https://example.com")
        assert result["safe"] is True

    def test_unsafe_url(self):
        result = check_url_safety("http://127.0.0.1/admin")
        assert result["safe"] is False
        assert "SSRF" in result["reason"]

    def test_bad_scheme(self):
        result = check_url_safety("ftp://example.com")
        assert result["safe"] is False
