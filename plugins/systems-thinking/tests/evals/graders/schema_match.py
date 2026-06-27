"""Graders that validate file structure against JSON schema or Markdown heading hierarchy."""

import json
import re
from pathlib import Path

try:
    import jsonschema

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


def grade_json_schema(filepath: Path, schema: dict) -> dict:
    """Validate a JSON file against a JSON schema.

    Requires the ``jsonschema`` package. If it is not installed, the grader
    returns a failing result with a descriptive error.

    Args:
        filepath: Path to the JSON file to validate.
        schema: A JSON Schema dict to validate against.

    Returns:
        A dict with:
            - "pass": True if validation succeeded.
            - "errors": List of validation error message strings.
    """
    if not _HAS_JSONSCHEMA:
        return {
            "pass": False,
            "errors": ["jsonschema package is not installed; run: pip install jsonschema"],
        }

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"pass": False, "errors": [f"File not found: {filepath}"]}

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return {"pass": False, "errors": [f"Invalid JSON: {exc}"]}

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    error_messages = [
        f"{'.'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in errors
    ]

    return {
        "pass": len(error_messages) == 0,
        "errors": error_messages,
    }


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def grade_markdown_structure(filepath: Path, required_headings: list[str]) -> dict:
    """Check that a Markdown file has the required heading hierarchy.

    Extracts all Markdown headings (lines starting with ``#``) and checks
    that each required heading string appears as a substring of at least one
    heading (case-insensitive).

    Args:
        filepath: Path to the Markdown file.
        required_headings: List of heading text strings expected to appear.

    Returns:
        A dict with:
            - "pass": True if all required headings were found.
            - "score": Fraction of headings found (0.0 to 1.0).
            - "missing_headings": List of heading strings not found.
            - "found_headings": List of heading strings that were found.
    """
    if not required_headings:
        return {
            "pass": True,
            "score": 1.0,
            "missing_headings": [],
            "found_headings": [],
        }

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "pass": False,
            "score": 0.0,
            "missing_headings": list(required_headings),
            "found_headings": [],
        }

    # Extract all heading texts from the document
    heading_texts: list[str] = []
    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            heading_texts.append(match.group(2).lower())

    found_headings: list[str] = []
    missing_headings: list[str] = []

    for required in required_headings:
        needle = required.lower()
        if any(needle in heading for heading in heading_texts):
            found_headings.append(required)
        else:
            missing_headings.append(required)

    score = len(found_headings) / len(required_headings)

    return {
        "pass": score == 1.0,
        "score": score,
        "missing_headings": missing_headings,
        "found_headings": found_headings,
    }
