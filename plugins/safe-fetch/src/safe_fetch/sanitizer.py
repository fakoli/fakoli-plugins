"""Content sanitization pipeline — the core defense against prompt injection."""

from __future__ import annotations

import base64
import re
import unicodedata

from lxml import etree
from lxml.html import fromstring as html_fromstring, tostring as html_tostring


# ---------------------------------------------------------------------------
# Constants — all compiled once at import time
# ---------------------------------------------------------------------------

# Tags to strip entirely (content and all)
_STRIP_TAGS = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "applet",
        "form",
        "input",
        "textarea",
        "select",
        "button",
        "svg",  # Can contain foreignObject with arbitrary HTML
    }
)

# Single combined regex for hidden CSS (avoids looping 10 patterns per element)
_HIDDEN_CSS_RE = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?:[;\s]|$)"
    r"|font-size\s*:\s*0"
    r"|(?:height|width)\s*:\s*0"
    r"|position\s*:\s*absolute.*?(?:left|top)\s*:\s*-\d{4,}"
    r"|clip\s*:\s*rect\(0"
    r"|text-indent\s*:\s*-\d{4,}",
    re.I | re.S,
)

# CSS classes commonly used to hide injection content
_HIDDEN_CLASSES = frozenset(
    {
        "hidden",
        "invisible",
        "d-none",
        "visually-hidden",
        "sr-only",
        "screen-reader-text",
        "assistive-text",
        "offscreen",
        "clip-hide",
    }
)

# Fake LLM delimiters
_LLM_DELIMITERS = [
    "<|im_start|>",
    "<|im_end|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|endoftext|>",
    "<|pad|>",
    "[INST]",
    "[/INST]",
    "<<SYS>>",
    "<</SYS>>",
    "<|begin_of_text|>",
    "<|end_of_text|>",
    "<|start_header_id|>",
    "<|end_header_id|>",
]

# Pre-compiled regex for delimiter variants with whitespace
_LLM_DELIMITER_VARIANT_RE = re.compile(
    r"<\|\s*(?:im_start|im_end|system|user|assistant|endoftext|pad"
    r"|begin_of_text|end_of_text|start_header_id|end_header_id)\s*\|>",
    re.I,
)

# Zero-width and invisible Unicode — use str.translate for O(n) removal
_INVISIBLE_CHARS = frozenset(
    {
        "\u200b",  # Zero Width Space
        "\u200c",  # Zero Width Non-Joiner
        "\u200d",  # Zero Width Joiner
        "\ufeff",  # Zero Width No-Break Space (BOM)
        "\u00ad",  # Soft Hyphen
        "\u2060",  # Word Joiner
        "\u180e",  # Mongolian Vowel Separator
        "\u2061",  # Function Application
        "\u2062",  # Invisible Times
        "\u2063",  # Invisible Separator
        "\u2064",  # Invisible Plus
        "\u034f",  # Combining Grapheme Joiner
        "\u17b4",  # Khmer Vowel Inherent Aq
        "\u17b5",  # Khmer Vowel Inherent Aa
        "\u115f",  # Hangul Choseong Filler
        "\u1160",  # Hangul Jungseong Filler
        "\u3164",  # Hangul Filler
        "\uffa0",  # Halfwidth Hangul Filler
    }
)

# Bidi override characters
_BIDI_CHARS = frozenset(
    {chr(cp) for cp in range(0x202A, 0x202F)}
    | {chr(cp) for cp in range(0x2066, 0x206A)}
)

# Combined translate table: maps all invisible + bidi chars to None (deletion)
_STRIP_CHAR_TABLE = str.maketrans(
    {ord(c): None for c in _INVISIBLE_CHARS | _BIDI_CHARS}
)

# Unicode tag characters (U+E0000–U+E007F)
_TAG_CHAR_PATTERN = re.compile(r"[\U000E0000-\U000E007F]+")

# Markdown image exfiltration pattern
_MD_IMAGE_EXFIL = re.compile(
    r"!\[([^\]]*)\]\((https?://[^)]*[?&]"
    r"(?:data|secret|key|token|password|code|auth|session|cookie|api_key|apikey|access_token)"
    r"=[^)]*)\)",
    re.I,
)

# General markdown image pattern (for defanging)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")

# Base64 pattern (blocks of 50+ chars)
_BASE64_BLOCK = re.compile(r"(?:[A-Za-z0-9+/]{50,}={0,2})")

# Instruction-like patterns for detecting injected instructions
_INSTRUCTION_PATTERNS = [
    re.compile(
        r"(?:you are|you must|ignore previous|disregard|forget|override|new instructions?)",
        re.I,
    ),
    re.compile(r"(?:system prompt|as an ai|as a language model|do not mention)", re.I),
    re.compile(r"(?:execute|run|eval)\s*\(", re.I),
    re.compile(r"(?:curl|wget|fetch)\s+https?://", re.I),
]

# XPath expressions — compiled once, reused
_XPATH_COMMENT = etree.XPath("//comment()")
_XPATH_META = etree.XPath("//meta")


# ---------------------------------------------------------------------------
# HTML-level sanitization (Layer 4a — before extraction)
# ---------------------------------------------------------------------------


def sanitize_html(html_content: str) -> str:
    """Strip dangerous/hidden HTML elements before content extraction."""
    try:
        doc = html_fromstring(html_content)
    except Exception:
        return re.sub(r"<[^>]+>", "", html_content)

    _remove_dangerous_elements(doc)
    _remove_hidden_elements(doc)
    _strip_comments(doc)
    _clean_data_attributes(doc)
    _strip_meta_instructions(doc)

    return html_tostring(doc, encoding="unicode")


def _remove_dangerous_elements(doc: etree._Element) -> None:
    for tag in _STRIP_TAGS:
        for el in doc.xpath(f"//{tag}"):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)


def _remove_hidden_elements(doc: etree._Element) -> None:
    # Single pass: check both inline style and class
    to_remove = []
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue

        # Check inline style
        style = el.get("style")
        if style and _HIDDEN_CSS_RE.search(style):
            to_remove.append(el)
            continue

        # Check class
        class_attr = el.get("class")
        if class_attr:
            classes = set(class_attr.lower().split())
            if classes & _HIDDEN_CLASSES:
                to_remove.append(el)

    # Remove in reverse order to avoid parent-before-child issues
    for el in reversed(to_remove):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)


def _strip_comments(doc: etree._Element) -> None:
    for comment in _XPATH_COMMENT(doc):
        parent = comment.getparent()
        if parent is not None:
            parent.remove(comment)


def _clean_data_attributes(doc: etree._Element) -> None:
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        to_remove = [
            attr
            for attr, val in el.attrib.items()
            if attr.startswith("data-") and len(val) > 100
        ]
        for attr in to_remove:
            del el.attrib[attr]


def _strip_meta_instructions(doc: etree._Element) -> None:
    for meta in _XPATH_META(doc):
        content = meta.get("content", "")
        if any(pat.search(content) for pat in _INSTRUCTION_PATTERNS):
            parent = meta.getparent()
            if parent is not None:
                parent.remove(meta)


# ---------------------------------------------------------------------------
# Text-level sanitization (Layer 4b — after extraction)
# ---------------------------------------------------------------------------


def sanitize_text(text: str) -> str:
    """Apply text-level sanitization to extracted content."""
    text = unicodedata.normalize("NFKC", text)
    # Single str.translate call removes all invisible + bidi chars (O(n))
    text = text.translate(_STRIP_CHAR_TABLE)
    text = _TAG_CHAR_PATTERN.sub("", text)
    text = _strip_llm_delimiters(text)
    text = _neutralize_base64_payloads(text)
    text = _defang_exfiltration_urls(text)
    return text


def _strip_llm_delimiters(text: str) -> str:
    for delim in _LLM_DELIMITERS:
        text = text.replace(delim, "")
    text = _LLM_DELIMITER_VARIANT_RE.sub("", text)
    return text


def _neutralize_base64_payloads(text: str) -> str:
    def _check_b64(match: re.Match) -> str:
        b64_str = match.group(0)
        try:
            decoded = base64.b64decode(b64_str).decode("utf-8", errors="ignore")
            if any(pat.search(decoded) for pat in _INSTRUCTION_PATTERNS):
                return "[BASE64-PAYLOAD-REMOVED]"
        except Exception:
            pass
        return b64_str

    return _BASE64_BLOCK.sub(_check_b64, text)


def _defang_exfiltration_urls(text: str) -> str:
    text = _MD_IMAGE_EXFIL.sub(
        r"[Image link removed — potential exfiltration URL]", text
    )

    def _defang_md_image(match: re.Match) -> str:
        alt = match.group(1)
        url = match.group(2)
        if "?" in url and any(c in url.lower() for c in ("=", "%3d")):
            return f"[Image: {alt}](URL defanged — contained query parameters)"
        return match.group(0)

    return _MD_IMAGE.sub(_defang_md_image, text)


# ---------------------------------------------------------------------------
# Context framing (Layer 4c)
# ---------------------------------------------------------------------------


def frame_content(sanitized_content: str, source_url: str) -> str:
    """Wrap sanitized content with untrusted-data markers."""
    return (
        f"--- BEGIN FETCHED WEB CONTENT (untrusted, from: {source_url}) ---\n"
        f"{sanitized_content}\n"
        f"--- END FETCHED WEB CONTENT ---"
    )


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def sanitize_pipeline(raw_html: str, url: str) -> str:
    """Run the complete sanitization pipeline: HTML sanitize → extract → text sanitize → frame."""
    from .extractor import extract_content

    clean_html = sanitize_html(raw_html)
    extracted = extract_content(clean_html, url)
    sanitized = sanitize_text(extracted)
    return frame_content(sanitized, url)
