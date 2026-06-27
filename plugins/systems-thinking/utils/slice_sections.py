#!/usr/bin/env python3
"""Split a Markdown document into individual section files based on an index.

Usage:
    python3 utils/slice_sections.py input.md --index output/index.json -o output/sections/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def slugify(text: str) -> str:
    """Convert a heading string into a filesystem-safe slug."""
    # Strip leading hashes and whitespace.
    clean = re.sub(r"^#+\s*", "", text)
    clean = clean.lower()
    clean = re.sub(r"[^a-z0-9]+", "-", clean)
    clean = clean.strip("-")
    return clean or "untitled"


def _flatten_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten nested sections into a depth-first ordered list."""
    result: list[dict[str, Any]] = []
    for sec in sections:
        result.append(sec)
        result.extend(_flatten_sections(sec.get("subsections", [])))
    return result


def slice_document(
    input_path: Path,
    index: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Slice the document into section files and return a manifest."""
    text = input_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    flat_sections = _flatten_sections(index["sections"])

    # Only slice at top-level boundaries (level 1 and 2) to keep files meaningful.
    # If there are no level-1 or level-2 sections, use whatever we have.
    top_level = [s for s in flat_sections if s["level"] <= 2]
    if not top_level:
        top_level = flat_sections

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_entries: list[dict[str, Any]] = []

    for idx, sec in enumerate(top_level):
        seq = f"{idx + 1:03d}"
        slug = slugify(sec["heading"])
        filename = f"{seq}-{slug}.md"
        filepath = output_dir / filename

        line_start = sec["line_start"]
        # Determine line_end: either the next top-level section or end of file.
        if idx + 1 < len(top_level):
            line_end = top_level[idx + 1]["line_start"] - 1
        else:
            line_end = len(lines)

        section_lines = lines[line_start - 1 : line_end]
        section_text = "\n".join(section_lines)
        token_estimate = sec.get("token_estimate", round(len(section_text.split()) * 1.3))

        header_comment = (
            f"<!-- source: {input_path.name} | "
            f"lines: {line_start}-{line_end} | "
            f"tokens: ~{token_estimate} -->"
        )
        content = f"{header_comment}\n\n{section_text}\n"
        filepath.write_text(content, encoding="utf-8")

        manifest_entries.append(
            {
                "file": filename,
                "heading": sec["heading"],
                "level": sec["level"],
                "line_start": line_start,
                "line_end": line_end,
                "token_estimate": token_estimate,
                "flags": sec.get("flags", []),
            }
        )

    manifest = {
        "source": input_path.name,
        "output_dir": str(output_dir),
        "section_count": len(manifest_entries),
        "sections": manifest_entries,
    }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a Markdown document into individual section files."
    )
    parser.add_argument("input", type=Path, help="Path to the Markdown file")
    parser.add_argument(
        "--index",
        type=Path,
        required=True,
        help="Path to the index JSON produced by index_doc.py",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output directory for section files",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: {args.input} is not a file.", file=sys.stderr)
        sys.exit(1)
    if not args.index.is_file():
        print(f"Error: {args.index} is not a file.", file=sys.stderr)
        sys.exit(1)

    index = json.loads(args.index.read_text(encoding="utf-8"))
    manifest = slice_document(args.input, index, args.output)

    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Sliced {manifest['section_count']} sections into {args.output}")
    print(f"Manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
