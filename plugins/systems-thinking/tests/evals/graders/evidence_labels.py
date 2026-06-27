"""Grader that checks for evidence/inference label separation in output."""

import re
from pathlib import Path

_SOURCE_LABEL_PATTERNS = [
    re.compile(r"\bEvidence:", re.IGNORECASE),
    re.compile(r"\[from source\]", re.IGNORECASE),
    re.compile(r"\[confirmed\]", re.IGNORECASE),
    re.compile(r"\[documented\]", re.IGNORECASE),
    re.compile(r"\bSource:", re.IGNORECASE),
]

_INFERRED_LABEL_PATTERNS = [
    re.compile(r"\[Inferred\]", re.IGNORECASE),
    re.compile(r"\binferred\b", re.IGNORECASE),
    re.compile(r"\[estimated\]", re.IGNORECASE),
    re.compile(r"\[assumed\]", re.IGNORECASE),
    re.compile(r"\bassumption\b", re.IGNORECASE),
]


def grade_evidence_labels(filepath: Path, config: dict | None = None) -> dict:
    """Check that output contains evidence and inference labels.

    Args:
        filepath: Path to the file to inspect.
        config: Optional dict with ``min_source_labels`` (int, default 3)
                and ``min_inferred_labels`` (int, default 1).

    Returns:
        A dict with ``pass``, ``score``, ``source_label_count``,
        and ``inferred_label_count``.
    """
    config = config or {}
    min_source = config.get("min_source_labels", 3)
    min_inferred = config.get("min_inferred_labels", 1)

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "pass": False,
            "score": 0.0,
            "source_label_count": 0,
            "inferred_label_count": 0,
        }

    source_count = sum(
        len(p.findall(content)) for p in _SOURCE_LABEL_PATTERNS
    )
    inferred_count = sum(
        len(p.findall(content)) for p in _INFERRED_LABEL_PATTERNS
    )

    source_ok = source_count >= min_source
    inferred_ok = inferred_count >= min_inferred
    passed = source_ok and inferred_ok

    # Score: average of two ratios (capped at 1.0 each)
    source_score = min(source_count / max(min_source, 1), 1.0)
    inferred_score = min(inferred_count / max(min_inferred, 1), 1.0)
    score = (source_score + inferred_score) / 2.0

    return {
        "pass": passed,
        "score": score,
        "source_label_count": source_count,
        "inferred_label_count": inferred_count,
    }
