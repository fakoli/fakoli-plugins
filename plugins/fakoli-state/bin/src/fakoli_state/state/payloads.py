"""Per-action Pydantic v2 payload models for _apply_mutation dispatch.

Each model corresponds to exactly one event action.  ``extra='forbid'`` is set
on every model so that unknown keys raise ``ValidationError`` at the point of
dispatch — before any handler body executes.  This centralises payload validation
that was previously scattered across 17 handler bodies as ad-hoc ``payload.get``
lookups.

Handlers receive the validated typed model instead of the raw ``dict[str, Any]``.
They access fields via attribute access (``payload.project_id``) rather than
``payload.get("project_id")``.

The ``Any`` type is kept for list-of-dict fields (e.g. ``requirements``,
``subtasks``) because those sub-dicts are themselves validated by Pydantic models
inside the handler bodies (``Requirement.model_validate``, ``Task.model_validate``).
Constraining them here would duplicate that validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreatedPayload(BaseModel):
    """Payload for 'project.created' — maps directly to the Project model."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    created_at: str
    updated_at: str


class StateInitializedPayload(BaseModel):
    """Payload for 'state.initialized' — no required fields (audit-only seed event)."""

    model_config = ConfigDict(extra="forbid")


class PrdParsedPayload(BaseModel):
    """Payload for 'prd.parsed'."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    status: str = "draft"
    summary: str = ""
    goals: list[Any] = []
    non_goals: list[Any] = []
    requirements: list[Any] = []
    acceptance_criteria: list[Any] = []
    risks: list[Any] = []
    open_questions: list[Any] = []


class PrdReviewedPayload(BaseModel):
    """Payload for 'prd.reviewed'."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    reviewer: str
    notes: str | None = None


class PrdApprovedPayload(BaseModel):
    """Payload for 'prd.approved'."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    approver: str


class FeatureCreatedPayload(BaseModel):
    """Payload for 'feature.created' — forwarded to Feature.model_validate."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str = ""
    status: str = "proposed"
    requirements: list[Any] = []
    tasks: list[Any] = []


class TaskCreatedPayload(BaseModel):
    """Payload for 'task.created' — forwarded to Task.model_validate.

    Sub-field validation (scores, verification, etc.) is delegated to
    Task.model_validate inside the handler.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    feature_id: str
    title: str
    description: str = ""
    status: str = "proposed"
    priority: str = "medium"
    dependencies: list[Any] = []
    conflict_groups: list[Any] = []
    scores: dict[str, Any] | None = None
    acceptance_criteria: list[Any] = []
    implementation_notes: list[Any] = []
    verification: dict[str, Any] | None = None
    likely_files: list[Any] = []
    parent_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""


class TaskScoredPayload(BaseModel):
    """Payload for 'task.scored'."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    scores: dict[str, Any]
    explanation: str | None = None


class TaskExpandedPayload(BaseModel):
    """Payload for 'task.expanded'."""

    model_config = ConfigDict(extra="forbid")

    parent_task_id: str
    subtasks: list[Any]


class TaskStatusChangedPayload(BaseModel):
    """Payload for 'task.status_changed'.

    The JSON keys ``from`` and ``to`` are Python keywords so they are mapped
    via ``Field(alias=...)`` to ``from_status`` and ``to_status``.
    ``populate_by_name=True`` lets callers also use the Python names directly
    (useful in tests).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    task_id: str
    from_status: str = Field(alias="from")
    to_status: str = Field(alias="to")
    reason: str | None = None


class ClaimCreatedPayload(BaseModel):
    """Payload for 'claim.created'."""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    claimed_by: str
    claim_type: str
    status: str
    created_at: str
    lease_expires_at: str
    last_heartbeat_at: str
    branch: str | None = None
    worktree_path: str | None = None
    expected_files: list[Any] = []
    # Optional terminal-state fields — present when reading back a Claim
    # model that has already been released/staled (e.g. in replay scenarios
    # where the full Claim dict is passed as the event payload).
    released_at: str | None = None
    release_reason: str | None = None


class ClaimReleasedPayload(BaseModel):
    """Payload for 'claim.released'."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    released_by: str
    release_reason: str | None = None
    force: bool = False
    # Audit timestamp emitted by ClaimManager.release()
    released_at: str | None = None


class ClaimRenewedPayload(BaseModel):
    """Payload for 'claim.renewed'."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    lease_expires_at: str
    last_heartbeat_at: str
    # Audit field emitted by ClaimManager.renew()
    renewed_by: str | None = None


class ClaimStalePayload(BaseModel):
    """Payload for 'claim.stale'.

    All fields sent by stale.py (the stale detector) are listed here.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    detected_at: str
    reason: str
    # Additional fields sent by the stale detector (stale.py)
    task_id: str | None = None
    expired_at: str | None = None
    actor: str | None = None


class EvidenceSubmittedPayload(BaseModel):
    """Payload for 'evidence.submitted'."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    claim_id: str
    submitted_by: str
    evidence_id: str
    commands_run: list[Any] = []
    files_changed: list[Any] = []
    output_excerpt: str | None = None
    pr_url: str | None = None
    commit_sha: str | None = None
    screenshots: list[Any] = []
    known_limitations: str | None = None


class TaskAppliedPayload(BaseModel):
    """Payload for 'task.applied'."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    reviewer: str
    decision: str
    notes: str | None = None


class FileChangedPayload(BaseModel):
    """Payload for 'file_changed' — audit-trail-only event.

    The handler is a no-op.  This model exists to make the dispatch table
    uniform and to validate that the payload shape is known.

    Known fields come from both the CLI hook (hooks.py) and the bash hook
    (hooks/record-file-change.sh).  All fields are optional because older
    JSONL records may omit some of them.
    """

    model_config = ConfigDict(extra="forbid")

    file: str | None = None
    tool: str | None = None
    actor: str | None = None
    changed_at: str | None = None
    # Bash hook uses these keys instead of the CLI hook convention:
    entity_type: str | None = None
    entity_id: str | None = None
    source: str | None = None


class ProgressNotedPayload(BaseModel):
    """Payload for 'progress.noted' — audit-trail-only event emitted by the MCP
    submit_progress tool (Phase 6).

    The handler is a no-op: the JSONL row is the audit record.  No SQLite
    mutation is performed — task status does not change.  This model exists to
    keep the dispatch table uniform and to enforce the known field schema via
    extra='forbid'.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: str
    actor: str
    notes: str
    noted_at: str


__all__ = [
    "ClaimCreatedPayload",
    "ClaimReleasedPayload",
    "ClaimRenewedPayload",
    "ClaimStalePayload",
    "EvidenceSubmittedPayload",
    "FeatureCreatedPayload",
    "FileChangedPayload",
    "PrdApprovedPayload",
    "PrdParsedPayload",
    "PrdReviewedPayload",
    "ProgressNotedPayload",
    "ProjectCreatedPayload",
    "StateInitializedPayload",
    "TaskAppliedPayload",
    "TaskCreatedPayload",
    "TaskExpandedPayload",
    "TaskScoredPayload",
    "TaskStatusChangedPayload",
]
