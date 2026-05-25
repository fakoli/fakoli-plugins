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


class SyncMappingUpsertedPayload(BaseModel):
    """Payload for 'sync_mapping.upserted' — Phase 8 external-system sync.

    Mirrors the SyncMapping model (state/models.py). The handler INSERTs a new
    row or, on (task_id, external_system) conflict, UPDATEs the existing row.

    Field-by-field mirror of :class:`fakoli_state.state.models.SyncMapping`.
    When a new field is added to ``SyncMapping`` it MUST be added here too —
    ``apply_sync_mapping`` constructs this payload from the canonical model
    and any mismatch surfaces at the call site (extra='forbid' on this model).
    """

    model_config = ConfigDict(extra="forbid")

    task_id: str
    external_system: str
    external_id: str
    external_url: str | None = None
    last_synced_at: str
    sync_state: str = "in_sync"
    conflict_resolution_strategy: str = "prompt"
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class SyncMappingDeletedPayload(BaseModel):
    """Payload for 'sync_mapping.deleted' — Phase 8 external-system sync.

    Composite-key delete: removes all sync_mappings rows for ``task_id``
    (across every external_system). If you need per-system deletion supply
    ``external_system`` as well; when None, every mapping for the task is
    removed.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: str
    external_system: str | None = None


# ---------------------------------------------------------------------------
# Phase 8 Wave 3 — sync.* audit events (Task 6 / cli/sync.py)
# ---------------------------------------------------------------------------
#
# Every push / pull / conflict / batch operation emits a `sync.*` action
# whose handler is an audit-only no-op (like `file_changed` and
# `progress.noted`).  The JSONL row IS the audit record; no SQLite mutation
# is performed by these events themselves.  The actual mapping persistence
# happens via the existing `sync_mapping.upserted` event, kept separate so
# replay-from-empty can reconstruct mappings without depending on `sync.*`.
#
# A single generic payload model is used for every `sync.*` action because
# the fields they audit overlap completely (provider id, optional task /
# external id, success / failure detail).  `extra="forbid"` still rejects
# unknown keys; the open shape is on the typed string fields, not the
# field set.


class SyncAuditPayload(BaseModel):
    """Generic payload for every `sync.*` audit-only event.

    Fields
    ------
    provider_id:
        Registry key of the provider involved (e.g. ``"github_issues"``).
        ``None`` for the bare-reconciliation events that span all providers.
    task_id:
        Local task id (e.g. ``"T001"``) when the event scopes to a single
        task; ``None`` for batch / reconciliation level events.
    external_id:
        Provider-native id (e.g. GitHub issue number) when known; absent
        on first-push events that haven't yet learned the remote id.
    strategy:
        :class:`fakoli_state.state.models.ConflictResolutionStrategy`
        value as a string when this is a conflict event; ``None`` otherwise.
    resolution:
        Free-form short description of how the conflict was resolved
        (``"local_wins_deferred"``, ``"remote_wins_deferred"``,
        ``"prompt_defaulted_to_local"``, ``"prompt_chose_local"``,
        ``"prompt_chose_remote"``, ``"prompt_skipped"``,
        ``"manual_merge_file_written"``).
    exception_type, exception_message:
        Populated on `sync.*.failed` events. Both ``None`` on success.
    direction:
        ``"push"`` or ``"pull"``; redundant with the action prefix but
        cheap to include and trivially queryable from JSONL.
    audit_note:
        Optional free-form short note (e.g. ``"watch loop iteration 3"``).
    """

    model_config = ConfigDict(extra="forbid")

    provider_id: str | None = None
    task_id: str | None = None
    external_id: str | None = None
    strategy: str | None = None
    resolution: str | None = None
    exception_type: str | None = None
    exception_message: str | None = None
    direction: str | None = None
    audit_note: str | None = None


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
    "SyncAuditPayload",
    "SyncMappingDeletedPayload",
    "SyncMappingUpsertedPayload",
    "TaskAppliedPayload",
    "TaskCreatedPayload",
    "TaskExpandedPayload",
    "TaskScoredPayload",
    "TaskStatusChangedPayload",
]
