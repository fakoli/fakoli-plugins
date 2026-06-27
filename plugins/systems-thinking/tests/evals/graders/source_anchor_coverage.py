"""Grader that checks what percentage of findings have source references."""

import re
from pathlib import Path

# Patterns that indicate a finding has a source anchor
_SOURCE_PATTERNS = [
    re.compile(r"\bSource:", re.IGNORECASE),
    re.compile(r"\[from source\]", re.IGNORECASE),
    re.compile(r"\bSection:", re.IGNORECASE),
    re.compile(r"\bRef:", re.IGNORECASE),
    re.compile(r"\((?:see|from|per|ref)\b", re.IGNORECASE),
    re.compile(r"§\s*\w"),
    re.compile(r"\bAppendix\s+[A-Z]", re.IGNORECASE),
    re.compile(r"\b(?:see|per|ref)\s+Option\s+\d", re.IGNORECASE),
]

# Patterns that identify a finding/claim line (bullet point or table row with substance)
_FINDING_PATTERNS = [
    re.compile(r"^\s*[-*•]\s+\S"),
    re.compile(r"^\s*\d+\.\s+\S"),
    re.compile(r"^\|[^|]+\|"),
]


def grade_source_anchor_coverage(
    filepath: Path, config: dict | None = None
) -> dict:
    """Check what fraction of findings have source references.

    Args:
        filepath: Path to the file to inspect.
        config: Optional dict with ``min_coverage`` (float, default 0.5).

    Returns:
        A dict with ``pass``, ``score``, ``total_findings``,
        ``anchored_findings``, and ``unanchored_findings``.
    """
    config = config or {}
    min_coverage = config.get("min_coverage", 0.5)

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "pass": False,
            "score": 0.0,
            "total_findings": 0,
            "anchored_findings": 0,
            "unanchored_findings": [],
        }

    lines = content.splitlines()
    total_findings = 0
    anchored = 0
    unanchored: list[str] = []

    for i, line in enumerate(lines):
        is_finding = any(p.match(line) for p in _FINDING_PATTERNS)
        if not is_finding:
            continue

        total_findings += 1
        # Check current line and the next line for source anchors
        window = line
        if i + 1 < len(lines):
            window += " " + lines[i + 1]

        if any(p.search(window) for p in _SOURCE_PATTERNS):
            anchored += 1
        else:
            unanchored.append(line.strip()[:120])

    if total_findings == 0:
        return {
            "pass": False,
            "score": 0.0,
            "total_findings": 0,
            "anchored_findings": 0,
            "unanchored_findings": [],
        }

    score = anchored / total_findings

    return {
        "pass": score >= min_coverage,
        "score": score,
        "total_findings": total_findings,
        "anchored_findings": anchored,
        "unanchored_findings": unanchored[:10],  # Cap for readability
    }
