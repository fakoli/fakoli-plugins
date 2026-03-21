"""Autospeak — automatic TTS on Stop hook events.

Manages toggle state and extracts spoken text from hook JSON.
"""

import json
import re
import sys
from pathlib import Path

TOGGLE_FILE = Path.home() / ".claude" / "fakoli-speak-autospeak.enabled"
MIN_CHARS = 100


def is_enabled() -> bool:
    return TOGGLE_FILE.exists()


def enable() -> None:
    TOGGLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOGGLE_FILE.write_text("1")


def disable() -> None:
    TOGGLE_FILE.unlink(missing_ok=True)


def strip_markdown(text: str) -> str:
    """Strip markdown formatting to produce speakable text."""
    # Remove code blocks (fenced)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)
    # Remove markdown links, keep text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove table rows (lines with |)
    text = re.sub(r"^\|.*\|$", "", text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    # Remove heading markers
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove blockquote markers
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    # Remove bullet markers
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    # Remove numbered list markers
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_text_from_hook(hook_json: dict) -> str | None:
    """Extract speakable text from a Stop hook JSON payload.

    Returns cleaned text or None if not enough content.
    """
    # Try common fields for the assistant's response
    text = None
    for key in ("result", "response", "content", "message"):
        if key in hook_json and isinstance(hook_json[key], str):
            text = hook_json[key]
            break

    if text is None:
        # Try nested structures
        if "transcript_messages" in hook_json:
            msgs = hook_json["transcript_messages"]
            if isinstance(msgs, list):
                # Get last assistant message
                for msg in reversed(msgs):
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            text = content
                            break

    if text is None:
        return None

    cleaned = strip_markdown(text)

    if len(cleaned) < MIN_CHARS:
        return None

    return cleaned


def process_hook_stdin() -> str | None:
    """Read hook JSON from stdin and extract text."""
    if sys.stdin.isatty():
        return None

    raw = sys.stdin.read()
    if not raw.strip():
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Maybe it's just plain text
        cleaned = strip_markdown(raw)
        return cleaned if len(cleaned) >= MIN_CHARS else None

    return extract_text_from_hook(data)
