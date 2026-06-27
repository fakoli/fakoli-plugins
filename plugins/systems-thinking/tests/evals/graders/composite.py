"""Composite grader that aggregates results from multiple sub-graders."""


def grade_composite(results: list[dict]) -> dict:
    """Aggregate multiple grader results into a single composite result.

    Each result dict must have at least a "pass" key (bool). A "score" key
    (float) is used if present; otherwise a passing result is scored as 1.0
    and a failing result as 0.0.

    Args:
        results: List of grader result dicts to aggregate.

    Returns:
        A dict with:
            - "pass": True only if every sub-grader passed.
            - "score": Average score across all sub-graders (0.0 to 1.0).
            - "total_checks": Number of sub-grader results.
            - "passed_checks": Number of sub-graders that passed.
            - "failed": List of sub-grader result dicts that did not pass.
    """
    if not results:
        return {
            "pass": True,
            "score": 1.0,
            "total_checks": 0,
            "passed_checks": 0,
            "failed": [],
        }

    total = len(results)
    passed = 0
    failed: list[dict] = []
    score_sum = 0.0

    for result in results:
        sub_score = result.get("score", 1.0 if result.get("pass", False) else 0.0)
        score_sum += sub_score

        if result.get("pass", False):
            passed += 1
        else:
            failed.append(result)

    avg_score = score_sum / total

    return {
        "pass": passed == total,
        "score": avg_score,
        "total_checks": total,
        "passed_checks": passed,
        "failed": failed,
    }
