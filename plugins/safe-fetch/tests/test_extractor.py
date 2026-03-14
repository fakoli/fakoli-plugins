"""Tests for content extraction quality."""

from __future__ import annotations

from safe_fetch.extractor import (
    extract_content,
    extract_by_content_type,
    extract_pdf,
    estimate_tokens,
    truncate_to_tokens,
)


class TestHTMLExtraction:
    def test_extracts_paragraph_text(self):
        html = "<html><body><p>Hello world, this is a test paragraph.</p></body></html>"
        result = extract_content(html)
        assert "Hello world" in result

    def test_extracts_headings(self):
        html = "<html><body><h1>Main Title</h1><p>Content here.</p></body></html>"
        result = extract_content(html)
        assert "Main Title" in result or "Content here" in result

    def test_extracts_lists(self):
        html = "<html><body><ul><li>Item one</li><li>Item two</li></ul></body></html>"
        result = extract_content(html)
        assert "Item one" in result or "Item two" in result

    def test_fallback_on_minimal_html(self):
        html = "<p>Just a paragraph</p>"
        result = extract_content(html)
        assert "paragraph" in result.lower() or "Just" in result


class TestContentTypeRouting:
    def test_json_pretty_prints(self):
        body = '{"key":"value","nested":{"a":1}}'
        result = extract_by_content_type(body, "application/json")
        assert '"key": "value"' in result  # Pretty-printed

    def test_plain_text_passthrough(self):
        body = "This is plain text content."
        result = extract_by_content_type(body, "text/plain")
        assert result == body

    def test_html_extracts(self):
        body = "<html><body><p>HTML content here.</p></body></html>"
        result = extract_by_content_type(body, "text/html; charset=utf-8")
        assert "HTML content" in result

    def test_handles_bytes(self):
        body = b"Byte content"
        result = extract_by_content_type(body, "text/plain")
        assert "Byte content" in result

    def test_handles_json_bytes(self):
        body = b'{"hello": "world"}'
        result = extract_by_content_type(body, "application/json")
        assert "hello" in result
        assert "world" in result

    def test_pdf_content_type_routing(self):
        # A minimal invalid PDF should return an error message, not crash
        result = extract_by_content_type(b"not a real pdf", "application/pdf")
        assert "PDF" in result or "extract" in result.lower()


class TestPDFExtraction:
    def test_invalid_pdf_returns_error(self):
        result = extract_pdf(b"not a pdf")
        assert "PDF" in result

    def test_empty_bytes_returns_error(self):
        result = extract_pdf(b"")
        assert "PDF" in result or "No extractable" in result


class TestTokenEstimation:
    def test_estimate_tokens(self):
        text = "Hello world"  # 11 chars
        tokens = estimate_tokens(text)
        assert tokens == 2  # 11 // 4

    def test_estimate_empty(self):
        assert estimate_tokens("") == 0


class TestTokenTruncation:
    def test_short_text_unchanged(self):
        text = "Short text"
        result = truncate_to_tokens(text, 1000)
        assert result == text

    def test_long_text_truncated(self):
        text = "Word " * 10000  # ~50000 chars
        result = truncate_to_tokens(text, 100)
        assert len(result) < len(text)
        assert "truncated" in result.lower()

    def test_truncation_at_sentence_boundary(self):
        # Build text that exceeds 100 tokens (~400 chars)
        text = "This is a sentence. " * 50  # 1000 chars = ~250 tokens
        result = truncate_to_tokens(text, 100)
        assert result.rstrip().endswith("tokens]") or result.rstrip().endswith(".")
        assert len(result) < len(text)

    def test_truncation_preserves_message(self):
        text = "A" * 2000
        result = truncate_to_tokens(text, 100)
        assert "~100 tokens" in result
