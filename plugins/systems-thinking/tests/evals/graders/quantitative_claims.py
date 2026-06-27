"""Grader that checks for specific quantitative claims in the output."""

import re
from pathlib import Path


def grade_quantitative_claims(
    filepath: Path, config: dict | None = None
) -> dict:
    """Check that required quantitative claims appear in the output.

    Args:
        filepath: Path to the file to inspect.
        config: Dict with ``claims`` — a list of dicts each containing
                ``pattern`` (regex string) and ``description`` (human label).

    Returns:
        A dict with ``pass``, ``score``, ``found``, ``missing``, and ``details``.
    """
    config = config or {}
    claims = config.get("claims", [])

    if not claims:
        return {"pass": True, "score": 1.0, "found": [], "missing": [], "details": []}

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "pass": False,
            "score": 0.0,
            "found": [],
            "missing": [c.get("description", c["pattern"]) for c in claims],
            "details": [],
        }

    found: list[str] = []
    missing: list[str] = []
    details: list[dict] = []

    for claim in claims:
        pattern = claim["pattern"]
        description = claim.get("description", pattern)
        try:
            match = re.search(pattern, content, re.IGNORECASE)
        except re.error:
            missing.append(description)
            details.append({"description": description, "found": False, "error": "invalid regex"})
            continue

        if match:
            found.append(description)
            details.append({"description": description, "found": True, "matched": match.group(0)})
        else:
            missing.append(description)
            details.append({"description": description, "found": False})

    score = len(found) / len(claims)

    return {
        "pass": score == 1.0,
        "score": score,
        "found": found,
        "missing": missing,
        "details": details,
    }
