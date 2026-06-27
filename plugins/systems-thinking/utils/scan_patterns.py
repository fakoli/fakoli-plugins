#!/usr/bin/env python3
"""Regex scanner that finds known patterns in documents without an LLM.

Usage:
    python3 utils/scan_patterns.py input.md -o output/patterns.json
    python3 utils/scan_patterns.py output/sections/ -o output/patterns.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Pattern definitions: category -> list of compiled regex patterns.
PATTERN_DEFS: dict[str, list[re.Pattern[str]]] = {
    "quotas": [
        re.compile(
            r"\b\d[\d,]*\.?\d*\s*"
            r"(?:limit|maximum|max|quota|cap|"
            r"per\s+second|per\s+minute|per\s+hour|per\s+day|"
            r"requests?\s*/\s*s|req/s|rps|qps)\b",
            re.IGNORECASE,
        ),
    ],
    "pricing": [
        re.compile(r"\$\d[\d,]*\.?\d*", re.IGNORECASE),
        re.compile(
            r"\b(?:per\s+GB|per\s+hour|per\s+month|per\s+request|per\s+unit|"
            r"per\s+vCPU|per\s+core)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:free\s+tier|standard\s+tier|premium\s+tier|enterprise\s+tier|"
            r"pay[\s-]as[\s-]you[\s-]go)\b",
            re.IGNORECASE,
        ),
    ],
    "warnings": [
        re.compile(
            r"\b(?:not\s+supported|not\s+available|not\s+recommended|"
            r"not\s+compatible|does\s+not\s+support|cannot|limitation)\b",
            re.IGNORECASE,
        ),
    ],
    "preview_beta": [
        re.compile(
            r"\b(?:preview|beta|experimental|early\s+access|"
            r"not\s+yet\s+GA|subject\s+to\s+change)\b",
            re.IGNORECASE,
        ),
    ],
    "deprecation": [
        re.compile(
            r"\b(?:deprecated|end\s+of\s+life|EOL|sunset|"
            r"will\s+be\s+removed|no\s+longer\s+supported)\b",
            re.IGNORECASE,
        ),
    ],
    "sla_exclusions": [
        re.compile(
            r"\b(?:excludes|not\s+covered|outside\s+SLA|"
            r"best\s+effort|no\s+guarantee)\b",
            re.IGNORECASE,
        ),
    ],
}


def scan_file(filepath: Path) -> list[dict[str, Any]]:
    """Scan a single file and return all matches."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()
    matches: list[dict[str, Any]] = []

    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        for category, patterns in PATTERN_DEFS.items():
            for pattern in patterns:
                if pattern.search(stripped):
                    matches.append(
                        {
                            "category": category,
                            "line": line_num,
                            "text": stripped,
                            "file": str(filepath),
                        }
                    )
                    # Only match each category once per line.
                    break

    return matches


def scan_input(input_path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Scan a file or directory and return (source_label, matches)."""
    all_matches: list[dict[str, Any]] = []

    if input_path.is_file():
        all_matches = scan_file(input_path)
        source = str(input_path)
    elif input_path.is_dir():
        files = sorted(
            p
            for p in input_path.rglob("*")
            if p.is_file() and p.suffix in (".md", ".txt", ".yaml", ".yml", ".json")
        )
        for f in files:
            all_matches.extend(scan_file(f))
        source = str(input_path)
    else:
        print(f"Error: {input_path} is not a file or directory.", file=sys.stderr)
        sys.exit(1)

    return source, all_matches


def build_report(source: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the structured JSON report from raw matches."""
    by_category: dict[str, list[dict[str, Any]]] = {}
    for m in matches:
        cat = m["category"]
        entry = {"line": m["line"], "text": m["text"], "file": m["file"]}
        by_category.setdefault(cat, []).append(entry)

    summary: dict[str, int] = {}
    for cat in PATTERN_DEFS:
        summary[cat] = len(by_category.get(cat, []))

    return {
        "source": source,
        "total_matches": len(matches),
        "by_category": by_category,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan documents for known patterns (quotas, pricing, warnings, etc.)."
    )
    parser.add_argument(
        "input", type=Path, help="Path to a Markdown file or directory of files to scan"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    args = parser.parse_args()

    source, matches = scan_input(args.input)
    report = build_report(source, matches)
    output_json = json.dumps(report, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Pattern scan written to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
