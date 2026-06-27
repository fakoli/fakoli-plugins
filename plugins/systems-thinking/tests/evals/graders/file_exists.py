"""Grader that checks if expected files exist in a target directory."""

from pathlib import Path


def grade_files_exist(workdir: Path, expected_files: list[str]) -> dict:
    """Check that all expected files exist relative to the working directory.

    Args:
        workdir: The root directory to check files relative to.
        expected_files: List of relative file paths expected to exist.

    Returns:
        A dict with:
            - "pass": True if all files were found.
            - "score": Fraction of files found (0.0 to 1.0).
            - "details": List of dicts with "file" and "found" keys.
    """
    if not expected_files:
        return {"pass": True, "score": 1.0, "details": []}

    details: list[dict] = []
    found_count = 0

    for rel_path in expected_files:
        full_path = workdir / rel_path
        exists = full_path.exists()
        details.append({"file": rel_path, "found": exists})
        if exists:
            found_count += 1

    score = found_count / len(expected_files)

    return {
        "pass": score == 1.0,
        "score": score,
        "details": details,
    }
