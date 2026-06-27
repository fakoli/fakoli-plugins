#!/usr/bin/env python3
"""Estimate token counts for files and suggest sharding strategies.

Usage:
    python3 utils/estimate_tokens.py input.md
    python3 utils/estimate_tokens.py output/sections/ --budget 4000
    python3 utils/estimate_tokens.py output/sections/ --budget 4000 -o output/tokens.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def estimate_tokens(text: str) -> int:
    """Approximate token count: word_count * 1.3, rounded to nearest int."""
    return round(len(text.split()) * 1.3)


def gather_files(input_path: Path) -> list[Path]:
    """Return a sorted list of files to process."""
    if input_path.is_file():
        return [input_path]
    elif input_path.is_dir():
        return sorted(
            p
            for p in input_path.iterdir()
            if p.is_file() and p.suffix in (".md", ".txt", ".yaml", ".yml", ".json")
        )
    else:
        print(f"Error: {input_path} is not a file or directory.", file=sys.stderr)
        sys.exit(1)


def compute_file_tokens(files: list[Path]) -> list[dict[str, Any]]:
    """Compute token estimates for each file."""
    entries: list[dict[str, Any]] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        tokens = estimate_tokens(text)
        entries.append({"path": str(f.name), "tokens": tokens})
    return entries


def build_sharding_plan(file_entries: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    """Group files into shards that fit within the token budget.

    Uses a greedy first-fit approach: add files to the current shard until
    the budget would be exceeded, then start a new shard.
    """
    shards: list[dict[str, Any]] = []
    current_files: list[str] = []
    current_tokens: int = 0
    shard_num: int = 1

    for entry in file_entries:
        file_tokens = entry["tokens"]

        # If a single file exceeds the budget, it gets its own shard.
        if current_tokens + file_tokens > budget and current_files:
            shards.append(
                {
                    "shard": shard_num,
                    "files": current_files,
                    "tokens": current_tokens,
                }
            )
            shard_num += 1
            current_files = []
            current_tokens = 0

        current_files.append(entry["path"])
        current_tokens += file_tokens

    # Flush remaining.
    if current_files:
        shards.append(
            {
                "shard": shard_num,
                "files": current_files,
                "tokens": current_tokens,
            }
        )

    return shards


def format_table(
    file_entries: list[dict[str, Any]],
    total_tokens: int,
    sharding_plan: list[dict[str, Any]] | None = None,
) -> str:
    """Format results as a human-readable table for stdout."""
    lines: list[str] = []

    # File table.
    max_path_len = max((len(e["path"]) for e in file_entries), default=4)
    col_width = max(max_path_len, 4)
    lines.append(f"{'File':<{col_width}}  {'Tokens':>8}")
    lines.append(f"{'-' * col_width}  {'-' * 8}")
    for entry in file_entries:
        lines.append(f"{entry['path']:<{col_width}}  {entry['tokens']:>8}")
    lines.append(f"{'-' * col_width}  {'-' * 8}")
    lines.append(f"{'TOTAL':<{col_width}}  {total_tokens:>8}")
    lines.append("")

    # Sharding plan.
    if sharding_plan:
        lines.append("Sharding Plan:")
        lines.append("")
        for shard in sharding_plan:
            file_list = ", ".join(shard["files"])
            lines.append(f"  Shard {shard['shard']}: {shard['tokens']} tokens - [{file_list}]")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate token counts and suggest sharding strategies."
    )
    parser.add_argument("input", type=Path, help="Path to a file or directory of files")
    parser.add_argument(
        "--budget",
        type=int,
        default=None,
        help="Token budget per shard; triggers sharding plan output",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: human-readable table to stdout)",
    )
    args = parser.parse_args()

    files = gather_files(args.input)
    file_entries = compute_file_tokens(files)
    total_tokens = sum(e["tokens"] for e in file_entries)

    sharding_plan: list[dict[str, Any]] | None = None
    if args.budget is not None:
        sharding_plan = build_sharding_plan(file_entries, args.budget)

    if args.output:
        result: dict[str, Any] = {
            "files": file_entries,
            "total_tokens": total_tokens,
        }
        if sharding_plan is not None:
            result["sharding_plan"] = sharding_plan
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Token estimates written to {args.output}")
    else:
        print(format_table(file_entries, total_tokens, sharding_plan))


if __name__ == "__main__":
    main()
