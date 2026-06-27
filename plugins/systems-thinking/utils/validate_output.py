#!/usr/bin/env python3
"""Validate that an output file conforms to the output contracts.

Usage:
    python3 utils/validate_output.py output/report.md --contract "Hidden Risk Summary"
    python3 utils/validate_output.py output/report.md --contract "Decision Brief"

Exit code 0 if valid, 1 if not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Output contract definitions: contract name -> list of required sections.
# Each section is represented by keywords that should appear as headings or
# prominent text in the output.
OUTPUT_CONTRACTS: dict[str, list[str]] = {
    "Hidden Risk Summary": [
        "scope reviewed",
        "top hidden risks",
        "likely impact areas",
        "assumptions",
        "unresolved questions",
        "source anchors",
    ],
    "Complexity Heat Map": [
        "complexity area",
        "why it matters",
        "severity",
        "confidence",
        "source anchors",
    ],
    "Decision Brief": [
        "decision under review",
        "options considered",
        "evidence summary",
        "inferred concerns",
        "top risks",
        "recommended next checks",
        "unresolved questions",
    ],
    "Pattern Remix Draft": [
        "target outcome",
        "reusable prior patterns",
        "constraints",
        "proposed approach",
        "implementation steps",
        "known risks",
    ],
    "Context Packet": [
        "source name",
        "section / scope reviewed",
        "extracted findings",
        "caveats",
        "confidence / ambiguity notes",
        "source anchors",
    ],
}

# Alternate phrasings that should match a required section.
# Maps from canonical section name to a list of acceptable variations.
SECTION_ALIASES: dict[str, list[str]] = {
    "scope reviewed": ["scope reviewed", "scope"],
    "top hidden risks": ["top hidden risks", "hidden risks"],
    "likely impact areas": ["likely impact areas", "impact areas"],
    "source anchors": ["source anchors", "sources", "references"],
    "complexity area": ["complexity area", "complexity heat map", "heat map"],
    "why it matters": ["why it matters", "why this matters", "impact"],
    "decision under review": ["decision under review", "decision"],
    "options considered": ["options considered", "options", "alternatives"],
    "evidence summary": ["evidence summary", "evidence"],
    "inferred concerns": ["inferred concerns", "concerns"],
    "top risks": ["top risks", "risks"],
    "recommended next checks": [
        "recommended next checks",
        "next checks",
        "next steps",
        "recommended checks",
        "follow-up",
    ],
    "unresolved questions": ["unresolved questions", "open questions"],
    "target outcome": ["target outcome", "target", "outcome", "goal"],
    "reusable prior patterns": [
        "reusable prior patterns",
        "prior patterns",
        "reusable patterns",
    ],
    "constraints": ["constraints", "constraint"],
    "proposed approach": ["proposed approach", "approach"],
    "implementation steps": ["implementation steps", "steps", "implementation"],
    "known risks": ["known risks", "risks"],
    "source name": ["source name", "source"],
    "section / scope reviewed": [
        "section / scope reviewed",
        "scope reviewed",
        "section reviewed",
        "scope",
        "section",
    ],
    "extracted findings": ["extracted findings", "findings"],
    "caveats": ["caveats", "caveat"],
    "confidence / ambiguity notes": [
        "confidence / ambiguity notes",
        "confidence",
        "ambiguity",
        "confidence notes",
        "ambiguity notes",
    ],
}


def _check_section_present(section: str, text_lower: str) -> bool:
    """Check if a required section is present in the text.

    Looks for the section name (or any alias) as a Markdown heading or as a
    prominent keyword in the document.
    """
    aliases = SECTION_ALIASES.get(section, [section])
    for alias in aliases:
        # Check as heading: ## Alias or **Alias** or | Alias |
        heading_pattern = re.compile(
            r"(?:^#+\s*" + re.escape(alias) + r"|"
            r"\*\*" + re.escape(alias) + r"\*\*|"
            r"\|\s*" + re.escape(alias) + r"\s*\|)",
            re.IGNORECASE | re.MULTILINE,
        )
        if heading_pattern.search(text_lower):
            return True
        # Check as plain text keyword presence (less strict fallback).
        if alias in text_lower:
            return True
    return False


def validate(filepath: Path, contract_name: str) -> dict[str, Any]:
    """Validate a file against a named output contract."""
    if contract_name not in OUTPUT_CONTRACTS:
        available = ", ".join(sorted(OUTPUT_CONTRACTS.keys()))
        print(
            f"Error: unknown contract '{contract_name}'. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    required_sections = OUTPUT_CONTRACTS[contract_name]
    text = filepath.read_text(encoding="utf-8")
    text_lower = text.lower()

    found: list[str] = []
    missing: list[str] = []

    for section in required_sections:
        if _check_section_present(section, text_lower):
            found.append(section)
        else:
            missing.append(section)

    total = len(required_sections)
    score = round(len(found) / total, 2) if total > 0 else 1.0
    is_valid = len(missing) == 0

    return {
        "contract": contract_name,
        "file": str(filepath),
        "valid": is_valid,
        "score": score,
        "found": found,
        "missing": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate an output file against an output contract."
    )
    parser.add_argument("input", type=Path, help="Path to the output file to validate")
    parser.add_argument(
        "--contract",
        type=str,
        required=True,
        help="Name of the output contract to validate against",
    )
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

    result = validate(args.input, args.contract)
    output_json = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Validation report written to {args.output}")
    else:
        print(output_json)

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
