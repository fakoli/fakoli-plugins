"""Content extraction — converts HTML/PDF/JSON to clean markdown."""

from __future__ import annotations

import json
import re

import trafilatura


def extract_content(html: str, url: str | None = None) -> str:
    """Extract main content from HTML, returning clean markdown."""
    result = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        favor_precision=True,
        include_links=True,
        include_tables=True,
        include_images=False,  # Don't include images to reduce exfil surface
        no_fallback=False,
    )
    if result and result.strip():
        return result.strip()

    # Fallback: strip tags and return raw text
    return _strip_tags_fallback(html)


def extract_pdf(data: bytes) -> str:
    """Extract text from a PDF using PyMuPDF."""
    try:
        import pymupdf
    except ImportError:
        return "(PDF extraction unavailable — pymupdf not installed)"

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages.append(f"## Page {i + 1}\n\n{text.strip()}")
        doc.close()
        return "\n\n".join(pages) if pages else "(No extractable text in PDF)"
    except Exception as e:
        return f"(PDF extraction failed: {e})"


def extract_by_content_type(
    body: str | bytes, content_type: str, url: str | None = None
) -> str:
    """Route extraction based on content type."""
    ct = content_type.lower().split(";")[0].strip()

    if ct in ("application/json", "text/json"):
        return _extract_json(body)
    elif ct.startswith("text/plain"):
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return body
    elif ct == "application/pdf":
        if isinstance(body, str):
            body = body.encode("utf-8")
        return extract_pdf(body)
    elif ct.startswith("text/html") or ct.startswith("application/xhtml"):
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return extract_content(body, url)
    else:
        # Unknown type — try HTML extraction, fall back to raw text
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        result = extract_content(body, url)
        if result:
            return result
        return body


def _extract_json(body: str | bytes) -> str:
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(body)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return body


def _strip_tags_fallback(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else "(No extractable content)"


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately max_tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to break at a paragraph or sentence boundary
    last_para = truncated.rfind("\n\n")
    if last_para > max_chars * 0.8:
        truncated = truncated[:last_para]
    else:
        last_sentence = truncated.rfind(". ")
        if last_sentence > max_chars * 0.8:
            truncated = truncated[: last_sentence + 1]
    return truncated + f"\n\n[Content truncated at ~{max_tokens} tokens]"
