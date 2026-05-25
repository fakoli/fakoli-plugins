"""Deterministic PRD template parser — no LLM, no I/O.

Turns a structured markdown PRD into Pydantic models.  All parse failures are
collected into ``ParseResult.errors``; nothing is raised.  Silent fallback is
explicitly rejected: if the parser cannot produce a coherent result it adds a
``ParseError`` and returns a partial (or empty) result so the caller can surface
the issue to the user.

Expected PRD structure (must match docs/prd-template.md):

    # Project: <Name>

    ## Summary
    <paragraph>

    ## Goals
    - <goal>

    ## Non-Goals          (optional)
    - <non-goal>

    ## Requirements
    - R001: <text>        (IDs auto-assigned if absent)

    ## Acceptance Criteria  (optional)
    - <criterion>

    ## Risks              (optional)
    - <risk>

    ## Open Questions     (optional)
    - <question>

    ## Features           (optional)

    ### F001: <Title>
    **Requirements:** R001, R002
    <description>

    ## Tasks              (optional)

    ### T001: <Title>
    **Feature:** F001
    **Priority:** medium
    **Likely files:** path/to/foo.py
    **Acceptance criteria:**
    - <criterion>
    **Verification:**
    - `pytest ...`
    <description>
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import NamedTuple

from fakoli_state.state.models import (
    PRD,
    Feature,
    Requirement,
    Score,
    Task,
    TaskPriority,
    TaskStatus,
    Verification,
)

__all__ = [
    "ParseError",
    "ParseResult",
    "parse_prd",
]

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

_UTC = datetime.UTC


class ParseError(NamedTuple):
    """A single parse failure collected into ParseResult.errors."""

    section: str
    line: int
    message: str


@dataclass
class ParseResult:
    """Output of parse_prd — always returned, never raised."""

    prd: PRD
    requirements: list[Requirement]
    features: list[Feature]
    tasks: list[Task]
    errors: list[ParseError]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Matches the bolded field lines in Feature / Task blocks.
# e.g. "**Requirements:** R001, R002" or "**Feature:** F001"
# Note: the colon may appear inside the bold markers (**Field:**) or outside.
# group(1) captures the field name (may include trailing colon).
# group(2) captures the value after the delimiter.
_FIELD_RE = re.compile(r"^\*\*([^*]+?)\*\*\s*:?\s*(.*)")

# Matches "### PREFIX: Title" or "### PREFIX Title" (colon optional for tolerance).
_H3_RE = re.compile(r"^###\s+(\S+?):?\s+(.*)")

# Matches a bullet list item starting with "- ".
_BULLET_RE = re.compile(r"^-\s+(.*)")

# ID patterns: R001, F001, T001 (case-insensitive for tolerance).
_REQ_ID_RE = re.compile(r"^(R\d+)\s*:?\s*(.*)", re.IGNORECASE)
_FEAT_ID_RE = re.compile(r"^(F\d{3,})", re.IGNORECASE)
_TASK_ID_RE = re.compile(r"^(T\d{3,})", re.IGNORECASE)


def _strip_html_comments(text: str) -> str:
    """Remove <!-- ... --> comments (may span multiple lines)."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _auto_id(prefix: str, index: int) -> str:
    """Produce R001, F001, T001 style IDs."""
    return f"{prefix}{index:03d}"


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------


def _split_sections(lines: list[str]) -> dict[str, tuple[int, list[str]]]:
    """Split the document on ## headings.

    Returns a dict mapping normalised section name → (start_line, body_lines).
    The special key "__project__" holds the # Project heading line.
    """
    sections: dict[str, tuple[int, list[str]]] = {}
    current_name: str | None = None
    current_start: int = 0
    current_body: list[str] = []

    for lineno, raw in enumerate(lines, start=1):
        if raw.startswith("# ") and not raw.startswith("## "):
            # Top-level heading — project title.
            if current_name is not None:
                sections[current_name] = (current_start, current_body)
            current_name = "__project__"
            current_start = lineno
            current_body = [raw]
        elif raw.startswith("## "):
            if current_name is not None:
                sections[current_name] = (current_start, current_body)
            heading = raw[3:].strip()
            current_name = heading.strip().lower().replace(" ", "_")
            current_start = lineno
            current_body = []
        else:
            if current_name is not None:
                current_body.append(raw)

    if current_name is not None:
        sections[current_name] = (current_start, current_body)

    return sections


# ---------------------------------------------------------------------------
# List extraction helpers
# ---------------------------------------------------------------------------


def _extract_bullet_list(body: list[str]) -> list[str]:
    """Return all bullet list items from a section body."""
    items: list[str] = []
    for line in body:
        m = _BULLET_RE.match(line.strip())
        if m:
            items.append(m.group(1).strip())
    return items


# ---------------------------------------------------------------------------
# Requirement parsing
# ---------------------------------------------------------------------------


def _parse_requirements(
    body: list[str],
    start_line: int,
    errors: list[ParseError],
) -> list[Requirement]:
    """Parse the ## Requirements section body into Requirement models.

    Items may be:
    - "- R001: text"  (explicit ID)
    - "- text"        (auto-assign ID)
    """
    reqs: list[Requirement] = []
    auto_index = 1

    for raw in body:
        line = raw.strip()
        if not line:
            continue
        m_bullet = _BULLET_RE.match(line)
        if not m_bullet:
            continue
        content = m_bullet.group(1).strip()
        m_id = _REQ_ID_RE.match(content)
        if m_id:
            req_id = m_id.group(1).upper()
            text = m_id.group(2).strip()
        else:
            req_id = _auto_id("R", auto_index)
            text = content

        auto_index += 1

        if not text:
            errors.append(
                ParseError(
                    section="requirements",
                    line=start_line,
                    message=f"Requirement '{req_id}' has empty text — skipped.",
                )
            )
            continue

        reqs.append(
            Requirement(
                id=req_id,
                prd_section="requirements",
                text=text,
            )
        )

    return reqs


# ---------------------------------------------------------------------------
# Feature parsing (within ## Features)
# ---------------------------------------------------------------------------


def _parse_h3_blocks(
    body: list[str],
    base_line: int,
) -> list[tuple[int, str, list[str]]]:
    """Split a section body on ### headings.

    Returns list of (line_number, heading_text, block_lines).
    """
    blocks: list[tuple[int, str, list[str]]] = []
    current_heading: str | None = None
    current_start: int = base_line
    current_lines: list[str] = []

    for offset, raw in enumerate(body, start=1):
        if raw.startswith("### "):
            if current_heading is not None:
                blocks.append((current_start, current_heading, current_lines))
            current_heading = raw[4:].strip()
            current_start = base_line + offset
            current_lines = []
        else:
            if current_heading is not None:
                current_lines.append(raw)

    if current_heading is not None:
        blocks.append((current_start, current_heading, current_lines))

    return blocks


def _parse_features(
    body: list[str],
    start_line: int,
    known_req_ids: set[str],
    errors: list[ParseError],
) -> list[Feature]:
    """Parse all ### FXxx: Title blocks within ## Features."""
    features: list[Feature] = []
    auto_index = 1
    blocks = _parse_h3_blocks(body, start_line)

    for block_line, heading, block_lines in blocks:
        m_h3 = _H3_RE.match(f"### {heading}")
        if m_h3:
            raw_id = m_h3.group(1)
            title = m_h3.group(2).strip()
            if _FEAT_ID_RE.match(raw_id):
                feat_id = raw_id.upper()
            else:
                # ID-looking prefix doesn't match pattern — treat whole heading as title.
                feat_id = _auto_id("F", auto_index)
                title = heading
        else:
            feat_id = _auto_id("F", auto_index)
            title = heading

        auto_index += 1

        # Parse field lines and description.
        req_ids: list[str] = []
        description_parts: list[str] = []
        i = 0
        while i < len(block_lines):
            raw = block_lines[i].strip()
            m_field = _FIELD_RE.match(raw)
            if m_field:
                # Strip trailing colon: **Field:** → key="field", **Field** → key="field".
                key = m_field.group(1).strip().lower().rstrip(":")
                val = m_field.group(2).strip()
                if key == "requirements":
                    req_ids = [r.strip().upper() for r in val.split(",") if r.strip()]
                # Other fields on features are ignored at parse time.
            elif raw:
                description_parts.append(raw)
            i += 1

        description = " ".join(description_parts).strip()

        # Validate referenced requirement IDs (warn, don't fail).
        for rid in req_ids:
            if rid not in known_req_ids:
                errors.append(
                    ParseError(
                        section="features",
                        line=block_line,
                        message=(
                            f"Feature '{feat_id}' references unknown "
                            f"requirement '{rid}' — included anyway."
                        ),
                    )
                )

        features.append(
            Feature(
                id=feat_id,
                title=title,
                description=description,
                requirements=req_ids,
            )
        )

    return features


# ---------------------------------------------------------------------------
# Task parsing (within ## Tasks)
# ---------------------------------------------------------------------------


def _parse_tasks(
    body: list[str],
    start_line: int,
    known_feat_ids: set[str],
    errors: list[ParseError],
) -> list[Task]:
    """Parse all ### TXxx: Title blocks within ## Tasks."""
    tasks: list[Task] = []
    auto_index = 1
    blocks = _parse_h3_blocks(body, start_line)
    now = datetime.datetime.now(_UTC)

    for block_line, heading, block_lines in blocks:
        m_h3 = _H3_RE.match(f"### {heading}")
        if m_h3:
            raw_id = m_h3.group(1)
            title = m_h3.group(2).strip()
            if _TASK_ID_RE.match(raw_id):
                task_id = raw_id.upper()
            else:
                task_id = _auto_id("T", auto_index)
                title = heading
        else:
            task_id = _auto_id("T", auto_index)
            title = heading

        auto_index += 1

        # Parse structured fields and description.
        feature_id: str = ""
        priority: TaskPriority = TaskPriority.medium
        likely_files: list[str] = []
        acceptance_criteria: list[str] = []
        verification_commands: list[str] = []
        description_parts: list[str] = []

        i = 0
        in_acceptance_criteria = False
        in_verification = False

        while i < len(block_lines):
            raw = block_lines[i]
            stripped = raw.strip()

            m_field = _FIELD_RE.match(stripped)
            if m_field:
                in_acceptance_criteria = False
                in_verification = False
                # Strip trailing colon from field name to normalise
                # "**Feature:**" and "**Feature**" to the same key.
                key = m_field.group(1).strip().lower().rstrip(":").replace(" ", "_")
                val = m_field.group(2).strip()

                if key == "feature":
                    feature_id = val.upper()
                elif key == "priority":
                    try:
                        priority = TaskPriority(val.lower())
                    except ValueError:
                        errors.append(
                            ParseError(
                                section="tasks",
                                line=block_line,
                                message=(
                                    f"Task '{task_id}' has unknown priority "
                                    f"'{val}' — defaulting to 'medium'."
                                ),
                            )
                        )
                elif key == "likely_files":
                    likely_files = [f.strip() for f in val.split(",") if f.strip()]
                elif key == "acceptance_criteria":
                    in_acceptance_criteria = True
                    if val:
                        acceptance_criteria.append(val)
                elif key == "verification":
                    in_verification = True
                    if val:
                        verification_commands.append(val.strip("`"))
            elif stripped.startswith("- ") and in_acceptance_criteria:
                m = _BULLET_RE.match(stripped)
                if m:
                    acceptance_criteria.append(m.group(1).strip())
            elif stripped.startswith("- ") and in_verification:
                m = _BULLET_RE.match(stripped)
                if m:
                    verification_commands.append(m.group(1).strip().strip("`"))
            elif stripped.startswith("- "):
                # Bullet not under a known field — treat as description.
                in_acceptance_criteria = False
                in_verification = False
                description_parts.append(stripped)
            elif stripped:
                in_acceptance_criteria = False
                in_verification = False
                description_parts.append(stripped)

            i += 1

        description = " ".join(description_parts).strip()

        if not feature_id:
            errors.append(
                ParseError(
                    section="tasks",
                    line=block_line,
                    message=(
                        f"Task '{task_id}' has no **Feature:** field — "
                        "feature_id will be empty."
                    ),
                )
            )

        if feature_id and feature_id not in known_feat_ids:
            errors.append(
                ParseError(
                    section="tasks",
                    line=block_line,
                    message=(
                        f"Task '{task_id}' references unknown feature "
                        f"'{feature_id}' — included anyway."
                    ),
                )
            )

        tasks.append(
            Task(
                id=task_id,
                feature_id=feature_id,
                title=title,
                description=description,
                status=TaskStatus.proposed,
                priority=priority,
                scores=Score(),
                acceptance_criteria=acceptance_criteria,
                verification=Verification(commands=verification_commands),
                likely_files=likely_files,
                created_at=now,
                updated_at=now,
            )
        )

    return tasks


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_prd(markdown: str, *, prd_id: str = "prd") -> ParseResult:
    """Parse a structured markdown PRD into Pydantic models.

    Args:
        markdown: The full PRD markdown source.
        prd_id:   An optional identifier for the PRD (used in error messages).

    Returns:
        A ParseResult containing the parsed PRD, Requirements, Features, and
        Tasks, plus any ParseError instances.  Never raises.

    Design:
        - Errors are surfaced in ParseResult.errors, never swallowed.
        - Missing optional sections produce empty lists.
        - Missing required sections (# Project, ## Summary, ## Goals,
          ## Requirements) produce ParseError entries.
        - IDs are auto-assigned when absent.
        - HTML comments are stripped before parsing.
    """
    # prd_id is reserved for future multi-PRD setups; not used in v0 (single
    # PRD per project). Acknowledge to silence linters without breaking the
    # API contract callers might rely on.
    _ = prd_id

    errors: list[ParseError] = []

    # --- Pre-processing --------------------------------------------------
    cleaned = _strip_html_comments(markdown)
    lines = cleaned.splitlines()

    sections = _split_sections(lines)

    # --- Required: # Project heading ------------------------------------
    # The project name lives in the heading but is not stored on PRD (which has
    # no name field).  We validate its presence and emit an error if absent.
    proj_block = sections.get("__project__")
    if proj_block is None:
        errors.append(
            ParseError(
                section="# Project",
                line=0,
                message="Missing required '# Project: <Name>' heading.",
            )
        )
    else:
        proj_line = proj_block[1][0] if proj_block[1] else ""
        if not re.match(r"^#\s+\S", proj_line.strip()):
            errors.append(
                ParseError(
                    section="# Project",
                    line=proj_block[0],
                    message=(
                        "Could not extract project name from heading "
                        f"'{proj_line.strip()}'."
                    ),
                )
            )

    # --- Required: ## Summary -------------------------------------------
    summary = ""
    summary_block = sections.get("summary")
    if summary_block is None:
        errors.append(
            ParseError(
                section="## Summary",
                line=0,
                message="Missing required '## Summary' section.",
            )
        )
    else:
        summary = " ".join(
            line.strip()
            for line in summary_block[1]
            if line.strip()
        ).strip()

    # --- Required: ## Goals ---------------------------------------------
    goals: list[str] = []
    goals_block = sections.get("goals")
    if goals_block is None:
        errors.append(
            ParseError(
                section="## Goals",
                line=0,
                message="Missing required '## Goals' section.",
            )
        )
    else:
        goals = _extract_bullet_list(goals_block[1])

    # --- Optional: ## Non-Goals -----------------------------------------
    non_goals: list[str] = []
    non_goals_block = sections.get("non-goals") or sections.get("non_goals")
    if non_goals_block is not None:
        non_goals = _extract_bullet_list(non_goals_block[1])

    # --- Required: ## Requirements --------------------------------------
    requirements: list[Requirement] = []
    req_block = sections.get("requirements")
    if req_block is None:
        errors.append(
            ParseError(
                section="## Requirements",
                line=0,
                message="Missing required '## Requirements' section.",
            )
        )
    else:
        requirements = _parse_requirements(
            req_block[1], req_block[0], errors
        )

    known_req_ids = {r.id for r in requirements}

    # --- Optional: ## Acceptance Criteria --------------------------------
    acceptance_criteria: list[str] = []
    ac_block = sections.get("acceptance_criteria")
    if ac_block is not None:
        acceptance_criteria = _extract_bullet_list(ac_block[1])

    # --- Optional: ## Risks ---------------------------------------------
    risks: list[str] = []
    risks_block = sections.get("risks")
    if risks_block is not None:
        risks = _extract_bullet_list(risks_block[1])

    # --- Optional: ## Open Questions ------------------------------------
    open_questions: list[str] = []
    oq_block = sections.get("open_questions")
    if oq_block is not None:
        open_questions = _extract_bullet_list(oq_block[1])

    # --- Build PRD model ------------------------------------------------
    prd = PRD(
        summary=summary,
        goals=goals,
        non_goals=non_goals,
        requirements=[r.id for r in requirements],
        acceptance_criteria=acceptance_criteria,
        risks=risks,
        open_questions=open_questions,
    )

    # --- Optional: ## Features ------------------------------------------
    features: list[Feature] = []
    feat_block = sections.get("features")
    if feat_block is not None:
        features = _parse_features(
            feat_block[1], feat_block[0], known_req_ids, errors
        )

    known_feat_ids = {f.id for f in features}

    # --- Optional: ## Tasks ---------------------------------------------
    tasks: list[Task] = []
    task_block = sections.get("tasks")
    if task_block is not None:
        tasks = _parse_tasks(
            task_block[1], task_block[0], known_feat_ids, errors
        )

    # --- Link task IDs back onto their Features -------------------------
    for task in tasks:
        for feat in features:
            if feat.id == task.feature_id and task.id not in feat.tasks:
                feat.tasks.append(task.id)

    return ParseResult(
        prd=prd,
        requirements=requirements,
        features=features,
        tasks=tasks,
        errors=errors,
    )
