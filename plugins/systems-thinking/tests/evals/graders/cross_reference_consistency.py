"""Grader that checks cross-reference consistency between output sections."""

import re
from pathlib import Path

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
# Words to ignore when extracting terms (too common to be meaningful)
_STOP_WORDS = frozenset(
    "the a an and or but in on of to for with by at from is are was were "
    "be been has have had not no this that these those it its can will may "
    "should must also very more most each all any some such as if when than".split()
)


def _extract_sections(content: str) -> dict[str, str]:
    """Parse Markdown content into heading -> body text mapping."""
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = match.group(1).strip().lower()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines)

    return sections


def _extract_terms(text: str) -> set[str]:
    """Extract significant terms from text (2+ char, not stop words)."""
    words = re.findall(r"\b[a-zA-Z][\w-]{2,}\b", text.lower())
    return {w for w in words if w not in _STOP_WORDS}


def grade_cross_reference_consistency(
    filepath: Path, config: dict | None = None
) -> dict:
    """Check that risk/finding terms appear across related sections.

    Args:
        filepath: Path to the file to inspect.
        config: Dict with ``sections_to_cross_check`` (list of heading
                substring pairs) and ``min_overlap`` (float, default 0.3).

    Returns:
        A dict with ``pass``, ``score``, ``overlapping_terms``,
        and ``isolated_terms``.
    """
    config = config or {}
    section_pairs = config.get("sections_to_cross_check", [])
    min_overlap = config.get("min_overlap", 0.3)

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "pass": False,
            "score": 0.0,
            "overlapping_terms": [],
            "isolated_terms": [],
        }

    sections = _extract_sections(content)

    if not section_pairs:
        # Default: check all section pairs
        headings = list(sections.keys())
        if len(headings) >= 2:
            section_pairs = [[headings[0], headings[-1]]]
        else:
            return {"pass": True, "score": 1.0, "overlapping_terms": [], "isolated_terms": []}

    total_overlap = 0.0
    pair_count = 0
    all_overlapping: list[str] = []
    all_isolated: list[str] = []

    for pair in section_pairs:
        if len(pair) != 2:
            continue

        needle_a, needle_b = pair[0].lower(), pair[1].lower()

        # Find matching sections by substring
        text_a = ""
        text_b = ""
        for heading, body in sections.items():
            if needle_a in heading:
                text_a += body + "\n"
            if needle_b in heading:
                text_b += body + "\n"

        if not text_a or not text_b:
            continue

        terms_a = _extract_terms(text_a)
        terms_b = _extract_terms(text_b)

        if not terms_a:
            continue

        overlap = terms_a & terms_b
        isolated = terms_a - terms_b

        overlap_ratio = len(overlap) / len(terms_a) if terms_a else 0.0
        total_overlap += overlap_ratio
        pair_count += 1

        all_overlapping.extend(sorted(overlap)[:5])
        all_isolated.extend(sorted(isolated)[:5])

    if pair_count == 0:
        return {
            "pass": False,
            "score": 0.0,
            "overlapping_terms": [],
            "isolated_terms": [],
            "error": "No configured section pairs were found in the output",
        }

    avg_overlap = total_overlap / pair_count

    return {
        "pass": avg_overlap >= min_overlap,
        "score": min(avg_overlap / min_overlap, 1.0) if min_overlap > 0 else 1.0,
        "overlapping_terms": all_overlapping[:15],
        "isolated_terms": all_isolated[:15],
    }
