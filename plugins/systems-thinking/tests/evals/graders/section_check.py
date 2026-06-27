"""Grader that checks if a file contains required sections or headings."""

from pathlib import Path


def grade_sections(
    filepath: Path,
    required_sections: list[str],
    case_sensitive: bool = False,
) -> dict:
    """Check that a file contains all required section headings or keywords.

    Searches the file content line-by-line for each required section string.
    A section is considered found if any line contains the section string
    as a substring.

    Args:
        filepath: Path to the file to inspect.
        required_sections: List of section heading strings or keywords to find.
        case_sensitive: If False (default), comparisons are case-insensitive.

    Returns:
        A dict with:
            - "pass": True if all required sections were found.
            - "score": Fraction of sections found (0.0 to 1.0).
            - "missing": List of section strings not found.
            - "found": List of section strings that were found.
    """
    if not required_sections:
        return {"pass": True, "score": 1.0, "missing": [], "found": []}

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "pass": False,
            "score": 0.0,
            "missing": list(required_sections),
            "found": [],
        }

    lines = content.splitlines()
    if not case_sensitive:
        lines_lower = [line.lower() for line in lines]

    found: list[str] = []
    missing: list[str] = []

    for section in required_sections:
        needle = section if case_sensitive else section.lower()
        search_lines = lines if case_sensitive else lines_lower
        if any(needle in line for line in search_lines):
            found.append(section)
        else:
            missing.append(section)

    score = len(found) / len(required_sections)

    return {
        "pass": score == 1.0,
        "score": score,
        "missing": missing,
        "found": found,
    }
