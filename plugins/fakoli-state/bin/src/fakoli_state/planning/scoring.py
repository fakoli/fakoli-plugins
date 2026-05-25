"""Rule-based six-dimension scoring engine — no LLM, no I/O.

Each dimension is scored 1-5 using pure heuristics derived from Task fields.
LLM augmentation is deferred to Phase 7 (planning.llm).

Dimensions:
    complexity          — how hard is this task to implement?
    parallelizability   — can it run in parallel with other tasks?
    context_load        — how much context does the agent need to load?
    blast_radius        — how wide is the potential impact of a mistake?
    review_risk         — how carefully must this be reviewed?
    agent_suitability   — how suitable is this for a smaller/cheaper model?

All dimensions clamp to [1, 5].  score_all() returns new Task instances via
model_copy(update=...) so the caller's objects are never mutated.
"""

from __future__ import annotations

import os
import re
from typing import NamedTuple

from fakoli_state.state.models import Score, Task

__all__ = [
    "score_task",
    "score_all",
]

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Files that touch shared infrastructure / config (blast_radius heuristic).
_SENSITIVE_FILE_RE = re.compile(
    r"(schema|migration|config\.|settings)", re.IGNORECASE
)

# Shared-infra path prefixes (blast_radius heuristic).
_SHARED_INFRA_PATH_RE = re.compile(r"\bsrc[\\/]", re.IGNORECASE)

# Public API surface files (blast_radius and review_risk heuristics).
_PUBLIC_API_FILE_RE = re.compile(
    r"(cli\.py|mcp_server\.py|__init__\.py)", re.IGNORECASE
)

# Complexity: keywords in description that indicate cross-cutting concern.
_COMPLEXITY_KEYWORDS_RE = re.compile(
    r"\b(refactor|redesign|migrate|migration|architecture)\b", re.IGNORECASE
)

# review_risk: security / auth / permission language in acceptance criteria.
_SECURITY_KEYWORDS_RE = re.compile(
    r"\b(security|auth|authentication|authoriz|permission)\b", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: int, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, value))


def _unique_dirs(files: list[str]) -> set[str]:
    """Return the set of parent directories for a list of file paths."""
    return {os.path.dirname(f) or "." for f in files}


# ---------------------------------------------------------------------------
# Per-dimension scorers — each returns (score, explanation_fragment)
# ---------------------------------------------------------------------------


class _Dim(NamedTuple):
    value: int
    explanation: str


def _score_complexity(task: Task) -> _Dim:
    base = 2
    reasons: list[str] = [f"base {base}"]
    files = task.likely_files
    nfiles = len(files)

    if nfiles >= 10:
        base = 4
        reasons = ["base 4 (>=10 files)"]
    elif nfiles >= 5:
        base = 4
        reasons = ["base 4 (>=5 files)"]

    word_count = len(task.description.split())
    if word_count >= 200:
        base += 1
        reasons.append("+1 (description >=200 words)")

    if _COMPLEXITY_KEYWORDS_RE.search(task.description):
        base += 1
        reasons.append("+1 (refactor/redesign/migrate/architecture keyword)")

    return _Dim(_clamp(base), f"complexity: {_clamp(base)} ({', '.join(reasons)})")


def _score_parallelizability(task: Task) -> _Dim:
    ndeps = len(task.dependencies)
    # Count how many conflict groups this task appears in (the field is a list
    # of group IDs, not cross-task membership — proxy: len(conflict_groups)).
    ngroups = len(task.conflict_groups)

    if ngroups >= 2:
        value = 1
        explanation = "parallelizability: 1 (in >=2 conflict groups)"
    elif ndeps == 0:
        value = 4
        explanation = "parallelizability: 4 (no dependencies)"
    elif ndeps <= 2:
        value = 3
        explanation = f"parallelizability: 3 ({ndeps} dependencies)"
    else:
        value = 2
        explanation = f"parallelizability: 2 (>=3 dependencies: {ndeps})"

    return _Dim(_clamp(value), explanation)


def _score_context_load(task: Task) -> _Dim:
    files = task.likely_files
    nfiles = len(files)

    if nfiles == 0:
        value = 5
        explanation = "context_load: 5 (0 known files — agent must discover)"
    elif nfiles == 1:
        value = 2
        explanation = "context_load: 2 (1 file)"
    else:
        ndirs = len(_unique_dirs(files))
        if ndirs > 1:
            value = 4
            explanation = (
                f"context_load: 4 (files span {ndirs} directories)"
            )
        else:
            value = 3
            explanation = (
                f"context_load: 3 ({nfiles} files in 1 directory)"
            )

    return _Dim(_clamp(value), explanation)


def _score_blast_radius(task: Task) -> _Dim:
    base = 2
    reasons: list[str] = [f"base {base}"]
    files = task.likely_files

    # Check for sensitive files first — this sets base to 5.
    has_sensitive = any(_SENSITIVE_FILE_RE.search(f) for f in files)
    if has_sensitive:
        base = 5
        reasons = ["base 5 (schema/migration/config/settings file)"]

    # Check shared infra paths.
    has_shared_infra = any(_SHARED_INFRA_PATH_RE.search(f) for f in files)
    if has_shared_infra and base < 5:
        base += 1
        reasons.append("+1 (src/ shared infra path)")

    # Check public API surface.
    has_public_api = any(_PUBLIC_API_FILE_RE.search(f) for f in files)
    if has_public_api:
        base += 1
        reasons.append("+1 (public API surface: cli.py / mcp_server.py / __init__.py)")

    return _Dim(_clamp(base), f"blast_radius: {_clamp(base)} ({', '.join(reasons)})")


def _score_review_risk(task: Task) -> _Dim:
    base = 2
    reasons: list[str] = [f"base {base}"]
    files = task.likely_files
    criteria_text = " ".join(task.acceptance_criteria)

    if _SECURITY_KEYWORDS_RE.search(criteria_text):
        base = 5
        reasons = ["base 5 (security/auth/permission in acceptance criteria)"]

    has_schema = any(_SENSITIVE_FILE_RE.search(f) for f in files)
    if has_schema:
        base += 1
        reasons.append("+1 (schema or migration file)")

    has_public_api = any(_PUBLIC_API_FILE_RE.search(f) for f in files)
    if has_public_api:
        base += 1
        reasons.append("+1 (CLI/MCP public surface)")

    return _Dim(_clamp(base), f"review_risk: {_clamp(base)} ({', '.join(reasons)})")


def _score_agent_suitability(complexity: int, blast_radius: int) -> _Dim:
    raw = 6 - complexity
    reasons: list[str] = [f"6 - complexity({complexity}) = {raw}"]
    if blast_radius >= 4:
        raw = min(raw, 2)
        reasons.append(f"capped at 2 (blast_radius={blast_radius} >= 4)")
    value = _clamp(raw)
    return _Dim(value, f"agent_suitability: {value} ({', '.join(reasons)})")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_task(task: Task) -> Score:
    """Compute a Score for task using rule-based heuristics.

    Pure function — does not mutate task.  Returns a fully-populated Score.

    Args:
        task: A Task (typically with scores=Score() / all None).

    Returns:
        A Score with all six dimensions populated and an explanation string.
    """
    complexity_dim = _score_complexity(task)
    parallelizability_dim = _score_parallelizability(task)
    context_load_dim = _score_context_load(task)
    blast_radius_dim = _score_blast_radius(task)
    review_risk_dim = _score_review_risk(task)
    agent_suitability_dim = _score_agent_suitability(
        complexity_dim.value, blast_radius_dim.value
    )

    explanation = "\n".join([
        complexity_dim.explanation,
        parallelizability_dim.explanation,
        context_load_dim.explanation,
        blast_radius_dim.explanation,
        review_risk_dim.explanation,
        agent_suitability_dim.explanation,
    ])

    return Score(
        complexity=complexity_dim.value,
        parallelizability=parallelizability_dim.value,
        context_load=context_load_dim.value,
        blast_radius=blast_radius_dim.value,
        review_risk=review_risk_dim.value,
        agent_suitability=agent_suitability_dim.value,
        explanation=explanation,
    )


def score_all(tasks: list[Task]) -> list[Task]:
    """Score every task in the list, returning new Task instances.

    Args:
        tasks: A list of Task models (not mutated).

    Returns:
        A new list of Task instances with scores populated via model_copy.
    """
    return [
        task.model_copy(update={"scores": score_task(task)})
        for task in tasks
    ]
