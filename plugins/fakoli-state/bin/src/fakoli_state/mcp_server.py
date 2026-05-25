"""FastMCP (stdio) server — 13 agent-facing tools for fakoli-state.

Each tool opens a fresh SqliteBackend against the current project's
.fakoli-state/state.db (resolved via cli._helpers._resolve_state_dir(Path.cwd())),
runs the operation, then closes. Agents may invoke from any cwd; the server
resolves state relative to the cwd at call time.

Stale-claim reaping runs at the top of every mutating tool (claim_task,
release_task, renew_claim, submit_progress, submit_completion_evidence,
update_task_status) per the Phase 6 spec. get_project_summary also reaps
per spec ("every MCP op").

Tool names match the spec exactly (2026-05-24-fakoli-state-v0.md §MCP Server).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------

mcp: FastMCP = FastMCP("fakoli-state")

# ---------------------------------------------------------------------------
# Return-type Pydantic models (what each tool returns)
# ---------------------------------------------------------------------------


class TaskCountsByStatus(BaseModel):
    """Task counts broken down by status for the project summary."""

    model_config = ConfigDict(extra="forbid")

    proposed: int = 0
    drafted: int = 0
    reviewed: int = 0
    ready: int = 0
    claimed: int = 0
    in_progress: int = 0
    blocked: int = 0
    needs_review: int = 0
    accepted: int = 0
    done: int = 0
    rejected: int = 0


class ProjectSummary(BaseModel):
    """Summary of project state returned by get_project_summary."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    project_name: str
    project_description: str
    prd_status: str | None
    task_counts: TaskCountsByStatus
    active_claim_count: int
    blocked_task_count: int
    ready_task_count: int


class ClaimResponse(BaseModel):
    """Claim details returned by claim_task."""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    claimed_by: str
    lease_expires_at: str
    branch: str | None
    worktree_path: str | None
    expected_files: list[str]


class ReleaseResponse(BaseModel):
    """Result of release_task."""

    model_config = ConfigDict(extra="forbid")

    released: bool
    claim_id: str


class RenewResponse(BaseModel):
    """Result of renew_claim."""

    model_config = ConfigDict(extra="forbid")

    lease_expires_at: str


class WorkPacketResponse(BaseModel):
    """Result of generate_work_packet."""

    model_config = ConfigDict(extra="forbid")

    format: str
    content: Any  # str for markdown, dict for json


class ProgressResponse(BaseModel):
    """Result of submit_progress."""

    model_config = ConfigDict(extra="forbid")

    recorded: bool


class EvidenceResponse(BaseModel):
    """Result of submit_completion_evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    task_status: str


class ConflictEntry(BaseModel):
    """A single conflict entry from check_conflicts."""

    model_config = ConfigDict(extra="forbid")

    file: str
    claim_id: str
    claimed_by: str
    task_id: str


class ConflictCheckResponse(BaseModel):
    """Result of check_conflicts."""

    model_config = ConfigDict(extra="forbid")

    conflicts: list[ConflictEntry]


class DependencyNode(BaseModel):
    """A node in the dependency graph."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: str
    priority: str
    feature_id: str


class DependencyEdge(BaseModel):
    """A directed edge in the dependency graph (from → to)."""

    model_config = ConfigDict(extra="forbid")

    from_task: str = Field(alias="from")
    to_task: str = Field(alias="to")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DependencyGraphResponse(BaseModel):
    """Result of get_dependency_graph."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    ready_to_claim: list[str]


class StatusUpdateResponse(BaseModel):
    """Result of update_task_status."""

    model_config = ConfigDict(extra="forbid")

    from_status: str
    to_status: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STATE_DIR_NAME = ".fakoli-state"

_PRIORITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

# Allowed transitions for update_task_status per spec:
# "Limited to drafted↔ready and blocked toggle"
_ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "drafted": {"ready"},
    "ready": {"drafted"},
    "in_progress": {"blocked"},
    "blocked": {"in_progress"},
    # spec also allows toggling blocked for claimed tasks
    "claimed": {"blocked"},
}


def _resolve_state_dir() -> Path:
    """Return the absolute path to .fakoli-state/ in the current working directory.

    Each MCP tool call resolves state relative to cwd at call time so agents
    can invoke from any project directory.
    """
    return Path.cwd().resolve() / _STATE_DIR_NAME


def _open_backend(state_dir: Path):  # type: ignore[return]
    """Open a fresh SqliteBackend for the given state_dir.

    Raises ToolError if the state directory does not exist (project not
    initialized). Caller must call backend.close() in a try/finally.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.sqlite import SqliteBackend

    if not state_dir.exists():
        raise ToolError(
            f"fakoli-state not initialized in {state_dir.parent}. "
            "Run `fakoli-state init` in your project root first.",
        )
    db_path = str(state_dir / "state.db")
    events_path = str(state_dir / "events.jsonl")
    backend = SqliteBackend(
        db_path=db_path,
        events_path=events_path,
        clock=SystemClock(),
    )
    backend.initialize()
    return backend


def _reap_stale(backend: Any) -> None:
    """Run the stale-claim detector; failures are best-effort (never block)."""
    try:
        from fakoli_state.claims.stale import detect_and_release_stale
        from fakoli_state.clock import SystemClock

        detect_and_release_stale(backend, SystemClock())
    except Exception:  # noqa: BLE001
        pass


def _find_active_claim_for_task(backend: Any, task_id: str) -> Any | None:
    """Return the active Claim for task_id, or None if none found."""
    for claim in backend.list_active_claims():
        if claim.task_id == task_id:
            return claim
    return None


# ---------------------------------------------------------------------------
# Tool 1: get_project_summary
# ---------------------------------------------------------------------------


@mcp.tool
def get_project_summary() -> ProjectSummary:
    """Return a summary of project state: project info, task counts by status,
    active claims, blocked count, and ready count.

    Stale claim reaping runs at the top of this call per spec.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        _reap_stale(backend)

        project = backend.get_project()
        if project is None:
            raise ToolError(
                "Project not found — run `fakoli-state init` to initialize.",
            )

        prd = backend.get_prd()
        all_tasks = backend.list_tasks()
        active_claims = backend.list_active_claims()

        counts = TaskCountsByStatus()
        blocked_count = 0
        ready_count = 0
        for task in all_tasks:
            status_val = task.status.value
            if hasattr(counts, status_val):
                setattr(counts, status_val, getattr(counts, status_val) + 1)
            if status_val == "blocked":
                blocked_count += 1
            if status_val == "ready":
                ready_count += 1

        return ProjectSummary(
            project_id=project.id,
            project_name=project.name,
            project_description=project.description,
            prd_status=prd.status.value if prd is not None else None,
            task_counts=counts,
            active_claim_count=len(active_claims),
            blocked_task_count=blocked_count,
            ready_task_count=ready_count,
        )
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 2: list_tasks
# ---------------------------------------------------------------------------


@mcp.tool
def list_tasks(
    status: str | None = None,
    feature_id: str | None = None,
    claimed_by: str | None = None,
) -> list[dict[str, Any]]:
    """Return tasks filtered by status, feature_id, and/or claimed_by.

    status and feature_id are pushed to SQL. claimed_by is an in-memory
    filter applied after retrieval (joins active claims).
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        tasks = backend.list_tasks(status=status, feature_id=feature_id)

        if claimed_by is not None:
            # Cross-reference active claims to filter by actor.
            active_claims = backend.list_active_claims()
            claimed_task_ids = {
                c.task_id for c in active_claims if c.claimed_by == claimed_by
            }
            tasks = [t for t in tasks if t.id in claimed_task_ids]

        import json

        return [json.loads(t.model_dump_json()) for t in tasks]
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 3: get_task
# ---------------------------------------------------------------------------


@mcp.tool
def get_task(task_id: str) -> dict[str, Any]:
    """Return the Task with the given ID.

    Raises a structured ToolError if the task is not found.
    """
    import json

    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        task = backend.get_task(task_id)
        if task is None:
            raise ToolError(
                f"Task '{task_id}' not found.",
            )
        return json.loads(task.model_dump_json())
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 4: get_next_task
# ---------------------------------------------------------------------------


@mcp.tool
def get_next_task(actor: str | None = None) -> dict[str, Any] | None:
    """Return the highest-priority ready task with no overlapping active claim.

    Priority ordering (per spec): HIGH > MEDIUM > LOW (critical treated as
    higher than high). Tiebreak: agent_suitability score desc, then id asc.

    Returns null if no claimable task is available.
    """
    import json

    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        _reap_stale(backend)

        ready_tasks = backend.list_tasks(status="ready")
        if not ready_tasks:
            return None

        active_claims = backend.list_active_claims()
        claimed_task_ids: set[str] = {c.task_id for c in active_claims}

        # Build done set for dependency checking.
        all_tasks = backend.list_tasks()
        done_task_ids: set[str] = {
            t.id for t in all_tasks if t.status.value == "done"
        }

        # Build active conflict groups.
        active_conflict_groups: set[str] = set()
        for t in all_tasks:
            if t.id in claimed_task_ids:
                for cg_id in t.conflict_groups:
                    active_conflict_groups.add(cg_id)

        candidates = []
        for task in ready_tasks:
            if task.id in claimed_task_ids:
                continue
            if any(dep_id not in done_task_ids for dep_id in task.dependencies):
                continue
            if any(cg_id in active_conflict_groups for cg_id in task.conflict_groups):
                continue
            candidates.append(task)

        if not candidates:
            return None

        def _sort_key(t: Any) -> tuple[int, int, str]:
            # Priority: higher rank = higher priority = sort first (negate).
            priority_rank = _PRIORITY_ORDER.get(t.priority.value, 0)
            # agent_suitability: higher = better = sort first (negate).
            suitability = (
                t.scores.agent_suitability
                if t.scores.agent_suitability is not None
                else 0
            )
            return (-priority_rank, -suitability, t.id)

        candidates.sort(key=_sort_key)
        best = candidates[0]
        return json.loads(best.model_dump_json())
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 5: claim_task
# ---------------------------------------------------------------------------


@mcp.tool
def claim_task(
    task_id: str,
    claimed_by: str,
    expected_files: list[str] | None = None,
    lease_duration_seconds: int = 900,
) -> ClaimResponse:
    """Acquire an exclusive lease on task_id for claimed_by.

    Gate: PRD must not be in 'draft' status — raises ToolError if it is.

    Delegates to ClaimManager.acquire_claim (ClaimManager.claim in the engine).
    Stale-claim reaping runs first.

    lease_duration_seconds controls the lease length (default 900 = 15 min).
    The ClaimManager uses minutes; we convert.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        from fakoli_state.claims.manager import ClaimError, ClaimManager
        from fakoli_state.clock import SystemClock

        _reap_stale(backend)

        # PRD gate: refuse if PRD is draft.
        prd = backend.get_prd()
        if prd is None or prd.status.value == "draft":
            prd_status = prd.status.value if prd is not None else "missing"
            raise ToolError(
                f"Cannot claim task '{task_id}': PRD is in '{prd_status}' status. "
                "The PRD must be reviewed or approved before tasks can be claimed.",
            )

        lease_minutes = max(1, lease_duration_seconds // 60)
        manager = ClaimManager(
            backend,
            SystemClock(),
            actor=claimed_by,
            default_lease_minutes=lease_minutes,
        )

        files = expected_files or []

        try:
            result = manager.claim(task_id, expected_files=files)
        except ClaimError as exc:
            raise ToolError(str(exc)) from exc

        claim = result.claim
        return ClaimResponse(
            id=claim.id,
            task_id=claim.task_id,
            claimed_by=claim.claimed_by,
            lease_expires_at=claim.lease_expires_at.isoformat(),
            branch=claim.branch,
            worktree_path=claim.worktree_path,
            expected_files=claim.expected_files,
        )
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 6: release_task
# ---------------------------------------------------------------------------


@mcp.tool
def release_task(
    task_id: str,
    actor: str,
    reason: str | None = None,
) -> ReleaseResponse:
    """Release the active claim on task_id held by actor.

    Stale-claim reaping runs first. Returns the claim_id that was released.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        from fakoli_state.claims.manager import ClaimError, ClaimManager
        from fakoli_state.clock import SystemClock

        _reap_stale(backend)

        active_claim = _find_active_claim_for_task(backend, task_id)
        if active_claim is None:
            raise ToolError(
                f"No active claim found for task '{task_id}'. "
                "The task may already be released or was never claimed.",
            )

        manager = ClaimManager(
            backend,
            SystemClock(),
            actor=actor,
        )

        try:
            manager.release(active_claim.id, reason=reason)
        except ClaimError as exc:
            raise ToolError(str(exc)) from exc

        return ReleaseResponse(released=True, claim_id=active_claim.id)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 7: renew_claim
# ---------------------------------------------------------------------------


@mcp.tool
def renew_claim(
    task_id: str,
    actor: str,
    extend_seconds: int = 900,
) -> RenewResponse:
    """Extend the lease on the active claim for task_id.

    Stale-claim reaping runs first.
    extend_seconds controls how far the lease is extended (default 900 = 15 min).
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        from fakoli_state.claims.manager import ClaimError, ClaimManager
        from fakoli_state.clock import SystemClock

        _reap_stale(backend)

        active_claim = _find_active_claim_for_task(backend, task_id)
        if active_claim is None:
            raise ToolError(
                f"No active claim found for task '{task_id}'. "
                "The task may have been released or its lease may have expired.",
            )

        lease_minutes = max(1, extend_seconds // 60)
        manager = ClaimManager(
            backend,
            SystemClock(),
            actor=actor,
            default_lease_minutes=lease_minutes,
        )

        try:
            updated_claim = manager.renew(active_claim.id)
        except ClaimError as exc:
            raise ToolError(str(exc)) from exc

        return RenewResponse(
            lease_expires_at=updated_claim.lease_expires_at.isoformat()
        )
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 8: generate_work_packet
# ---------------------------------------------------------------------------


@mcp.tool
def generate_work_packet(
    task_id: str,
    format: Literal["markdown", "json"] = "markdown",
) -> WorkPacketResponse:
    """Render a work packet for task_id in markdown or JSON format.

    Delegates to context.packets.render_packet. Returns the rendered content
    (str for markdown, dict for json) plus the format name.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        from fakoli_state.context.packets import render_packet
        from fakoli_state.state.models import Task

        task = backend.get_task(task_id)
        if task is None:
            raise ToolError(f"Task '{task_id}' not found.")

        feature = backend.get_feature(task.feature_id)

        dependencies_completed: list[Task] = []
        dependencies_open: list[Task] = []
        for dep_id in task.dependencies:
            dep = backend.get_task(dep_id)
            if dep is None:
                continue
            if dep.status.value == "done":
                dependencies_completed.append(dep)
            else:
                dependencies_open.append(dep)

        active_claim = _find_active_claim_for_task(backend, task_id)

        packet = render_packet(
            task,
            feature=feature,
            dependencies_completed=dependencies_completed,
            dependencies_open=dependencies_open,
            related_decisions=None,
            active_claim=active_claim,
        )

        if format == "json":
            return WorkPacketResponse(format="json", content=packet.json_data)
        return WorkPacketResponse(format="markdown", content=packet.markdown)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 9: submit_progress
# ---------------------------------------------------------------------------


@mcp.tool
def submit_progress(
    task_id: str,
    actor: str,
    notes: str,
) -> ProgressResponse:
    """Record an in-progress status note for task_id.

    Emits a 'progress.noted' audit event but does NOT change task status.
    The JSONL row is the audit record.

    Stale-claim reaping runs first.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        from fakoli_state.clock import SystemClock
        from fakoli_state.state.backend import PENDING_EVENT_ID
        from fakoli_state.state.models import Event

        _reap_stale(backend)

        task = backend.get_task(task_id)
        if task is None:
            raise ToolError(f"Task '{task_id}' not found.")

        clock = SystemClock()
        now = clock.now()

        event = Event(
            id=PENDING_EVENT_ID,
            timestamp=now,
            actor=actor,
            action="progress.noted",
            target_kind="task",
            target_id=task_id,
            payload_json={
                "task_id": task_id,
                "actor": actor,
                "notes": notes,
                "noted_at": now.isoformat(),
            },
        )
        backend.apply_event(event)
        return ProgressResponse(recorded=True)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 10: submit_completion_evidence
# ---------------------------------------------------------------------------


@mcp.tool
def submit_completion_evidence(
    task_id: str,
    actor: str,
    commands_run: list[str],
    files_changed: list[str],
    output_excerpt: str | None = None,
    pr_url: str | None = None,
    commit_sha: str | None = None,
) -> EvidenceResponse:
    """Submit completion evidence for task_id.

    Mirrors `fakoli-state submit` from the CLI. Requires an active claim.
    Emits evidence.submitted event which auto-releases the claim and
    transitions the task to needs_review.

    Stale-claim reaping runs first.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        from fakoli_state.clock import SystemClock
        from fakoli_state.state.backend import PENDING_EVENT_ID
        from fakoli_state.state.models import Event

        _reap_stale(backend)

        task = backend.get_task(task_id)
        if task is None:
            raise ToolError(f"Task '{task_id}' not found.")

        active_claim = _find_active_claim_for_task(backend, task_id)
        if active_claim is None:
            raise ToolError(
                f"No active claim found for task '{task_id}'. "
                "Claim the task first before submitting evidence.",
            )

        evidence_id = "EV" + uuid.uuid4().hex[:8].upper()
        clock = SystemClock()
        now = clock.now()

        event = Event(
            id=PENDING_EVENT_ID,
            timestamp=now,
            actor=actor,
            action="evidence.submitted",
            target_kind="task",
            target_id=task_id,
            payload_json={
                "task_id": task_id,
                "claim_id": active_claim.id,
                "submitted_by": actor,
                "evidence_id": evidence_id,
                "commands_run": commands_run,
                "files_changed": files_changed,
                "output_excerpt": output_excerpt,
                "pr_url": pr_url,
                "commit_sha": commit_sha,
                "screenshots": [],
                "known_limitations": None,
            },
        )

        from fakoli_state.state.backend import TransactionAborted

        try:
            backend.apply_event(event)
        except TransactionAborted as exc:
            raise ToolError(str(exc)) from exc

        fresh_task = backend.get_task(task_id)
        task_status = fresh_task.status.value if fresh_task is not None else "needs_review"

        return EvidenceResponse(evidence_id=evidence_id, task_status=task_status)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 11: check_conflicts
# ---------------------------------------------------------------------------


@mcp.tool
def check_conflicts(
    task_id: str,
    proposed_files: list[str],
) -> ConflictCheckResponse:
    """Cross-reference proposed_files against active claims (excluding task_id's own claim).

    Returns a list of conflict entries — one per overlapping file per claim.
    An empty conflicts list means no conflicts were detected.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        proposed_set = set(proposed_files)
        active_claims = backend.list_active_claims()

        conflicts: list[ConflictEntry] = []
        for claim in active_claims:
            # Skip this task's own claim.
            if claim.task_id == task_id:
                continue
            overlap = proposed_set & set(claim.expected_files)
            for file in sorted(overlap):
                conflicts.append(
                    ConflictEntry(
                        file=file,
                        claim_id=claim.id,
                        claimed_by=claim.claimed_by,
                        task_id=claim.task_id,
                    )
                )

        return ConflictCheckResponse(conflicts=conflicts)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 12: get_dependency_graph
# ---------------------------------------------------------------------------


@mcp.tool
def get_dependency_graph(
    scope: Literal["all", "feature", "task"] = "all",
    target_id: str | None = None,
) -> DependencyGraphResponse:
    """Return the task dependency graph with nodes, edges, and ready_to_claim set.

    scope='all': entire project.
    scope='feature': all tasks in the given feature (target_id required).
    scope='task': the given task plus its transitive dependencies (target_id required).

    ready_to_claim is the list of task IDs that are in 'ready' status, have
    all dependencies done, and have no active claim.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        all_tasks = backend.list_tasks()
        task_map = {t.id: t for t in all_tasks}
        active_claims = backend.list_active_claims()
        claimed_task_ids = {c.task_id for c in active_claims}
        done_task_ids = {t.id for t in all_tasks if t.status.value == "done"}

        # Determine which tasks are in scope.
        if scope == "all":
            scoped_tasks = all_tasks
        elif scope == "feature":
            if target_id is None:
                raise ToolError(
                    "target_id is required when scope='feature'."
                )
            scoped_tasks = [t for t in all_tasks if t.feature_id == target_id]
        elif scope == "task":
            if target_id is None:
                raise ToolError(
                    "target_id is required when scope='task'."
                )
            # Collect the target task plus all its transitive dependencies.
            visited: set[str] = set()
            queue = [target_id]
            while queue:
                tid = queue.pop()
                if tid in visited:
                    continue
                visited.add(tid)
                t = task_map.get(tid)
                if t is None:
                    continue
                for dep_id in t.dependencies:
                    if dep_id not in visited:
                        queue.append(dep_id)
            scoped_tasks = [task_map[tid] for tid in visited if tid in task_map]
        else:
            scoped_tasks = all_tasks

        scoped_ids = {t.id for t in scoped_tasks}

        nodes = [
            DependencyNode(
                id=t.id,
                title=t.title,
                status=t.status.value,
                priority=t.priority.value,
                feature_id=t.feature_id,
            )
            for t in scoped_tasks
        ]

        # Edges: dependency relationships within scope.
        edges = []
        for t in scoped_tasks:
            for dep_id in t.dependencies:
                if dep_id in scoped_ids:
                    edges.append(
                        DependencyEdge(
                            **{"from": dep_id, "to": t.id}
                        )
                    )

        # ready_to_claim: ready tasks with all deps done and no active claim.
        ready_to_claim = []
        for t in scoped_tasks:
            if t.status.value != "ready":
                continue
            if t.id in claimed_task_ids:
                continue
            if any(dep_id not in done_task_ids for dep_id in t.dependencies):
                continue
            ready_to_claim.append(t.id)

        return DependencyGraphResponse(
            nodes=nodes,
            edges=edges,
            ready_to_claim=sorted(ready_to_claim),
        )
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Tool 13: update_task_status
# ---------------------------------------------------------------------------


@mcp.tool
def update_task_status(
    task_id: str,
    to_status: Literal["drafted", "ready", "blocked", "in_progress"],
    actor: str,
    reason: str | None = None,
) -> StatusUpdateResponse:
    """Transition task_id to a new status.

    Allowed transitions per spec:
    - drafted ↔ ready
    - in_progress / claimed → blocked
    - blocked → in_progress

    Any other transition returns a structured ToolError.

    Stale-claim reaping runs first.
    """
    state_dir = _resolve_state_dir()
    backend = _open_backend(state_dir)
    try:
        from fakoli_state.clock import SystemClock
        from fakoli_state.state.backend import PENDING_EVENT_ID, TransactionAborted
        from fakoli_state.state.models import Event

        _reap_stale(backend)

        task = backend.get_task(task_id)
        if task is None:
            raise ToolError(f"Task '{task_id}' not found.")

        from_status = task.status.value
        allowed_targets = _ALLOWED_STATUS_TRANSITIONS.get(from_status, set())

        if to_status not in allowed_targets:
            raise ToolError(
                f"Cannot transition task '{task_id}' from '{from_status}' to '{to_status}'. "
                f"Allowed targets from '{from_status}': {sorted(allowed_targets) or 'none'}. "
                "This tool supports only: drafted↔ready and blocked toggle.",
            )

        clock = SystemClock()
        now = clock.now()

        event = Event(
            id=PENDING_EVENT_ID,
            timestamp=now,
            actor=actor,
            action="task.status_changed",
            target_kind="task",
            target_id=task_id,
            payload_json={
                "task_id": task_id,
                "from": from_status,
                "to": to_status,
                "reason": reason,
            },
        )

        try:
            backend.apply_event(event)
        except TransactionAborted as exc:
            raise ToolError(str(exc)) from exc

        return StatusUpdateResponse(from_status=from_status, to_status=to_status)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
