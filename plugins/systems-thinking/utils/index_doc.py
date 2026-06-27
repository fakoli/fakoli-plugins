#!/usr/bin/env python3
"""Parse a Markdown document and produce a structural index. No LLM calls.

Usage:
    python3 utils/index_doc.py input.md -o output/index.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Keywords that flag a section as likely containing caveats.
CAVEAT_KEYWORDS: list[str] = [
    "limit",
    "quota",
    "restriction",
    "constraint",
    "caveat",
    "warning",
    "note",
    "sla",
    "pricing",
    "cost",
    "support",
    "availability",
    "preview",
    "beta",
    "deprecat",
    "exclude",
    "except",
]

# Keywords that flag a section as likely containing pricing information.
PRICING_KEYWORDS: list[str] = [
    "price",
    "pricing",
    "cost",
    "billing",
    "tier",
    "plan",
    "charge",
    "fee",
    "rate",
]

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)")


def estimate_tokens(text: str) -> int:
    """Approximate token count: word_count * 1.3, rounded to nearest int."""
    word_count = len(text.split())
    return round(word_count * 1.3)


def _matches_keywords(heading_text: str, keywords: list[str]) -> bool:
    """Check if a heading matches any keyword (case-insensitive substring)."""
    lower = heading_text.lower()
    return any(kw in lower for kw in keywords)


def _build_flags(heading_text: str) -> list[str]:
    """Return a list of flags applicable to a heading."""
    flags: list[str] = []
    if _matches_keywords(heading_text, CAVEAT_KEYWORDS):
        flags.append("caveat_likely")
    if _matches_keywords(heading_text, PRICING_KEYWORDS):
        flags.append("pricing_likely")
    return flags


def parse_sections(lines: list[str]) -> list[dict[str, Any]]:
    """Parse Markdown lines into a flat list of section dicts with line ranges."""
    sections: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            full_heading = f"{'#' * level} {heading_text}"
            sections.append(
                {
                    "heading": full_heading,
                    "level": level,
                    "line_start": i + 1,  # 1-indexed
                    "line_end": -1,  # filled in next pass
                    "content_lines": [],
                    "flags": _build_flags(heading_text),
                }
            )

    # Fill in line_end and collect content for each section.
    for idx, sec in enumerate(sections):
        if idx + 1 < len(sections):
            sec["line_end"] = sections[idx + 1]["line_start"] - 1
        else:
            sec["line_end"] = len(lines)
        start = sec["line_start"] - 1  # 0-indexed
        end = sec["line_end"]  # exclusive in slice
        sec["content_lines"] = lines[start:end]

    return sections


def nest_sections(flat: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a nested tree from a flat list of sections ordered by line number.

    Each section may contain a 'subsections' key with child sections.
    """
    root: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []

    for sec in flat:
        node = _section_to_output(sec)
        # Pop stack until we find a parent with a lower level.
        while stack and stack[-1]["level"] >= sec["level"]:
            stack.pop()
        if stack:
            stack[-1].setdefault("subsections", []).append(node)
        else:
            root.append(node)
        stack.append(node)

    return root


def _section_to_output(sec: dict[str, Any]) -> dict[str, Any]:
    """Convert an internal section dict to the output format."""
    content = "\n".join(sec["content_lines"])
    tokens = estimate_tokens(content)
    return {
        "heading": sec["heading"],
        "level": sec["level"],
        "line_start": sec["line_start"],
        "line_end": sec["line_end"],
        "token_estimate": tokens,
        "flags": sec["flags"],
        "subsections": [],
    }


def _collect_all_sections(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten nested sections into a list (for counting and flagging)."""
    result: list[dict[str, Any]] = []
    for node in nodes:
        result.append(node)
        result.extend(_collect_all_sections(node.get("subsections", [])))
    return result


def index_document(filepath: Path) -> dict[str, Any]:
    """Produce a structural index for a Markdown file."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    flat_sections = parse_sections(lines)
    nested = nest_sections(flat_sections)
    all_sections = _collect_all_sections(nested)

    total_tokens = estimate_tokens(text)
    max_section_tokens = max((s["token_estimate"] for s in all_sections), default=0)

    flagged: dict[str, list[str]] = {}
    for sec in all_sections:
        for flag in sec["flags"]:
            flagged.setdefault(flag, []).append(sec["heading"])

    return {
        "source": filepath.name,
        "total_tokens_estimate": total_tokens,
        "sections": nested,
        "flagged_sections": flagged,
        "section_count": len(all_sections),
        "max_section_tokens": max_section_tokens,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a Markdown document and produce a structural index."
    )
    parser.add_argument("input", type=Path, help="Path to the Markdown file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: {args.input} is not a file.", file=sys.stderr)
        sys.exit(1)

    result = index_document(args.input)
    output_json = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Index written to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
