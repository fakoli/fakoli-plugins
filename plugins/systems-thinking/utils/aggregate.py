#!/usr/bin/env python3
"""Merge structured findings from multiple worker output files into a single report.

Usage:
    python3 utils/aggregate.py output/findings/ -o output/aggregated.md
    python3 utils/aggregate.py output/findings/ -o output/aggregated.json --format json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Known heading categories to extract from Markdown files.
KNOWN_CATEGORIES: list[str] = [
    "findings",
    "caveats",
    "risks",
    "costs",
    "dependencies",
    "hidden risks",
    "assumptions",
    "unresolved questions",
    "warnings",
    "limitations",
    "impact areas",
]

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)")


def _normalize_category(text: str) -> str:
    """Normalize a heading to a known category or return it as-is."""
    lower = text.lower().strip()
    for cat in KNOWN_CATEGORIES:
        if cat in lower:
            return cat
    return lower


def extract_from_markdown(filepath: Path) -> dict[str, list[dict[str, Any]]]:
    """Extract findings grouped by category from a Markdown file."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()
    result: dict[str, list[dict[str, Any]]] = {}

    current_category: str | None = None
    current_items: list[str] = []

    def _flush() -> None:
        nonlocal current_category, current_items
        if current_category and current_items:
            content = "\n".join(current_items).strip()
            if content:
                result.setdefault(current_category, []).append(
                    {
                        "text": content,
                        "source": str(filepath.name),
                    }
                )
        current_items = []

    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            _flush()
            heading_text = match.group(2).strip()
            current_category = _normalize_category(heading_text)
            continue
        if current_category:
            # Collect bullet items and body text under the current heading.
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                # Each bullet is a separate finding.
                _flush()
                current_items.append(stripped[2:].strip())
            elif stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                _flush()
                # Strip leading number and dot.
                item_text = re.sub(r"^\d+\.\s*", "", stripped)
                current_items.append(item_text)
            elif stripped:
                current_items.append(stripped)

    _flush()
    return result


def extract_from_json(filepath: Path) -> dict[str, list[dict[str, Any]]]:
    """Extract findings from a JSON file."""
    data = json.loads(filepath.read_text(encoding="utf-8"))
    result: dict[str, list[dict[str, Any]]] = {}

    if isinstance(data, dict):
        for key, value in data.items():
            cat = _normalize_category(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        entry = {**item, "source": item.get("source", filepath.name)}
                        result.setdefault(cat, []).append(entry)
                    elif isinstance(item, str):
                        result.setdefault(cat, []).append(
                            {
                                "text": item,
                                "source": str(filepath.name),
                            }
                        )
            elif isinstance(value, str):
                result.setdefault(cat, []).append(
                    {
                        "text": value,
                        "source": str(filepath.name),
                    }
                )
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cat = _normalize_category(item.get("category", "uncategorized"))
                result.setdefault(cat, []).append(item)

    return result


def _dedup_key(entry: dict[str, Any]) -> str:
    """Create a deduplication key from an entry."""
    text = entry.get("text", "")
    source = entry.get("source", "")
    return f"{text}||{source}"


def merge_findings(
    all_findings: list[dict[str, list[dict[str, Any]]]],
) -> dict[str, list[dict[str, Any]]]:
    """Merge and deduplicate findings from multiple sources."""
    merged: dict[str, list[dict[str, Any]]] = {}
    seen_keys: dict[str, set[str]] = {}

    for findings in all_findings:
        for cat, entries in findings.items():
            if cat not in merged:
                merged[cat] = []
                seen_keys[cat] = set()
            for entry in entries:
                key = _dedup_key(entry)
                if key not in seen_keys[cat]:
                    seen_keys[cat].add(key)
                    merged[cat].append(entry)

    return merged


def _severity_sort_key(entry: dict[str, Any]) -> int:
    """Sort entries by severity (high first). Default to medium."""
    severity = str(entry.get("severity", "medium")).lower()
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(severity, 2)


def format_markdown(
    merged: dict[str, list[dict[str, Any]]],
    source_count: int,
) -> str:
    """Format merged findings as a Markdown report."""
    lines: list[str] = []
    total_findings = sum(len(v) for v in merged.values())

    lines.append("# Aggregated Findings")
    lines.append("")
    lines.append(f"**Sources:** {source_count}  ")
    lines.append(f"**Total findings:** {total_findings}  ")
    lines.append(f"**Categories:** {', '.join(sorted(merged.keys()))}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for cat in sorted(merged.keys()):
        entries = sorted(merged[cat], key=_severity_sort_key)
        lines.append(f"## {cat.replace('_', ' ').title()}")
        lines.append("")
        for entry in entries:
            text = entry.get("text", json.dumps(entry))
            source = entry.get("source", "unknown")
            severity = entry.get("severity", "")
            severity_tag = f" **[{severity}]**" if severity else ""
            lines.append(f"- {text}{severity_tag}  ")
            lines.append(f"  _(source: {source})_")
        lines.append("")

    return "\n".join(lines)


def format_json(
    merged: dict[str, list[dict[str, Any]]],
    source_count: int,
) -> str:
    """Format merged findings as JSON."""
    total_findings = sum(len(v) for v in merged.values())
    result = {
        "metadata": {
            "source_count": source_count,
            "total_findings": total_findings,
            "categories": sorted(merged.keys()),
        },
        "findings": merged,
    }
    return json.dumps(result, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge structured findings from multiple output files."
    )
    parser.add_argument("input", type=Path, help="Directory containing .md or .json finding files")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output file path")
    parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md)",
    )
    args = parser.parse_args()

    if not args.input.is_dir():
        print(f"Error: {args.input} is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Gather input files.
    files = sorted(p for p in args.input.iterdir() if p.is_file() and p.suffix in (".md", ".json"))
    if not files:
        print(f"Error: no .md or .json files found in {args.input}.", file=sys.stderr)
        sys.exit(1)

    # Extract findings from each file.
    all_findings: list[dict[str, list[dict[str, Any]]]] = []
    for f in files:
        if f.suffix == ".json":
            all_findings.append(extract_from_json(f))
        else:
            all_findings.append(extract_from_markdown(f))

    merged = merge_findings(all_findings)
    source_count = len(files)

    if args.format == "json":
        output_text = format_json(merged, source_count)
    else:
        output_text = format_markdown(merged, source_count)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text + "\n", encoding="utf-8")
    print(f"Aggregated {source_count} files into {args.output}")


if __name__ == "__main__":
    main()
