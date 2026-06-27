"""Graders that ensure forbidden patterns or files are absent."""

import re
from pathlib import Path


def grade_no_forbidden_patterns(filepath: Path, forbidden_patterns: list[str]) -> dict:
    """Check that a file does NOT contain any forbidden patterns.

    Each pattern is treated as a regular expression and searched across every
    line of the file.

    Args:
        filepath: Path to the file to inspect.
        forbidden_patterns: List of regex pattern strings that must NOT appear.

    Returns:
        A dict with:
            - "pass": True if no forbidden patterns were found.
            - "violations": List of dicts with "pattern", "line_number", and
              "matched_text" for each violation.
    """
    if not forbidden_patterns:
        return {"pass": True, "violations": []}

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        # If the file doesn't exist, there are no forbidden patterns in it.
        return {"pass": True, "violations": []}

    compiled = []
    for pattern in forbidden_patterns:
        try:
            compiled.append((pattern, re.compile(pattern)))
        except re.error as exc:
            return {
                "pass": False,
                "violations": [
                    {
                        "pattern": pattern,
                        "line_number": 0,
                        "matched_text": f"Invalid regex: {exc}",
                    }
                ],
            }

    violations: list[dict] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for pattern_str, regex in compiled:
            match = regex.search(line)
            if match:
                violations.append(
                    {
                        "pattern": pattern_str,
                        "line_number": line_number,
                        "matched_text": match.group(0),
                    }
                )

    return {
        "pass": len(violations) == 0,
        "violations": violations,
    }


def grade_no_forbidden_files(workdir: Path, forbidden_files: list[str]) -> dict:
    """Check that forbidden files do NOT exist in the working directory.

    Args:
        workdir: The root directory to check relative to.
        forbidden_files: List of relative file paths that must NOT exist.

    Returns:
        A dict with:
            - "pass": True if none of the forbidden files exist.
            - "violations": List of relative paths that were found.
    """
    if not forbidden_files:
        return {"pass": True, "violations": []}

    violations: list[str] = []
    for rel_path in forbidden_files:
        full_path = workdir / rel_path
        if full_path.exists():
            violations.append(rel_path)

    return {
        "pass": len(violations) == 0,
        "violations": violations,
    }
