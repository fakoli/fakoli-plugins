"""Rule-based six-dimension scoring engine — no LLM, no I/O.

Each dimension is scored 1-5 using pure heuristics derived from Task fields.
Optional LLM augmentation (Phase 7 Wave 2) is additive: if a provider is
supplied, an LLM-written one-paragraph trade-off summary is appended to the
``Score.explanation`` field.  The rule-based scores themselves are NEVER
modified by the LLM — augmentation is enrichment only.

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

import json
import os
import re
import sys
from typing import TYPE_CHECKING, NamedTuple

from fakoli_state.state.models import Score, Task

if TYPE_CHECKING:
    from fakoli_state.planning.llm import LLMProvider

__all__ = [
    "score_task",
    "score_all",
]

# ---------------------------------------------------------------------------
# LLM augmentation constants
# ---------------------------------------------------------------------------

_SCORE_EXPLAIN_SYSTEM_PROMPT = (
    "You are a senior engineer scoring a task on six dimensions. "
    "Given the rule-based scores and the task body, write 1-3 sentences "
    "explaining the trade-offs. Be concrete and terse — no marketing language."
)
_SCORE_EXPLAIN_MAX_TOKENS = 300

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


def score_task(
    task: Task,
    *,
    provider: LLMProvider | None = None,
) -> Score:
    """Compute a Score for task using rule-based heuristics.

    Pure function — does not mutate task.  Returns a fully-populated Score.

    When ``provider`` is supplied, the rule-based ``explanation`` is *augmented*
    with a 1-3 sentence trade-off summary written by the LLM.  The numeric
    scores themselves are never touched by the LLM (additive enrichment only).
    If the LLM call fails (``LLMProviderError``), a warning is written to
    stderr and the deterministic-only explanation is returned unchanged.

    Args:
        task: A Task (typically with scores=Score() / all None).
        provider: Optional LLM provider for explanation enrichment.

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

    rule_explanation = "\n".join([
        complexity_dim.explanation,
        parallelizability_dim.explanation,
        context_load_dim.explanation,
        blast_radius_dim.explanation,
        review_risk_dim.explanation,
        agent_suitability_dim.explanation,
    ])

    score = Score(
        complexity=complexity_dim.value,
        parallelizability=parallelizability_dim.value,
        context_load=context_load_dim.value,
        blast_radius=blast_radius_dim.value,
        review_risk=review_risk_dim.value,
        agent_suitability=agent_suitability_dim.value,
        explanation=rule_explanation,
    )

    if provider is not None:
        augmented = _augment_explanation(task, score, provider)
        if augmented is not None:
            score = score.model_copy(
                update={"explanation": rule_explanation + "\n\n" + augmented}
            )

    return score


def score_all(
    tasks: list[Task],
    *,
    provider: LLMProvider | None = None,
) -> list[Task]:
    """Score every task in the list, returning new Task instances.

    Args:
        tasks: A list of Task models (not mutated).
        provider: Optional LLM provider passed through to ``score_task``.

    Returns:
        A new list of Task instances with scores populated via model_copy.
    """
    return [
        task.model_copy(update={"scores": score_task(task, provider=provider)})
        for task in tasks
    ]


# ---------------------------------------------------------------------------
# LLM augmentation helper — local to keep dependency direction one-way.
# ---------------------------------------------------------------------------


def _augment_explanation(
    task: Task,
    score: Score,
    provider: LLMProvider,
) -> str | None:
    """Call the provider to produce a 1-3 sentence trade-off summary.

    Returns the LLM-written paragraph on success, or ``None`` if the call
    failed (a warning is printed to stderr in that case).  Never raises.
    """
    # Local import: keeps the optional LLM dep from leaking into the import
    # graph of callers that never set provider=.
    from fakoli_state.planning.llm import LLMProviderError

    user_payload = json.dumps(
        {
            "task_id": task.id,
            "title": task.title,
            "description": task.description,
            "likely_files": task.likely_files,
            "dependencies": task.dependencies,
            "scores": {
                "complexity": score.complexity,
                "parallelizability": score.parallelizability,
                "context_load": score.context_load,
                "blast_radius": score.blast_radius,
                "review_risk": score.review_risk,
                "agent_suitability": score.agent_suitability,
            },
        },
        sort_keys=True,
    )

    try:
        response = provider.generate(
            system=_SCORE_EXPLAIN_SYSTEM_PROMPT,
            user=user_payload,
            max_tokens=_SCORE_EXPLAIN_MAX_TOKENS,
        )
    except LLMProviderError as exc:
        print(
            f"warning: LLM augmentation of {task.id} score explanation failed "
            f"({exc}); falling back to rule-based explanation only.",
            file=sys.stderr,
        )
        return None
    except Exception as exc:  # noqa: BLE001 — Phase 7 contract: LLM never aborts
        # Non-conforming custom provider raised something other than
        # LLMProviderError. Treat as fall-back to preserve the deterministic
        # baseline rather than abort the entire score batch.
        print(
            f"warning: LLM augmentation of {task.id} raised non-conforming "
            f"{type(exc).__name__}: {exc}; falling back to rule-based only.",
            file=sys.stderr,
        )
        return None

    text = response.text.strip()
    if not text:
        return None
    return text
