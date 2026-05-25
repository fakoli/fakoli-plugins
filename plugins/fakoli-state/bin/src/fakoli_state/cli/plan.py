"""plan, score, expand, review tasks, list, show commands (Phase 3)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from fakoli_state.cli._helpers import (
    _PRD_FILENAME,
    _open_backend,
    _require_state_dir,
    _resolve_state_dir,
    _scores_complete,
)
from fakoli_state.state.backend import PENDING_EVENT_ID

if TYPE_CHECKING:
    pass

# review sub-app — registered in __init__.py as app.add_typer(review_app, name="review")
review_app = typer.Typer(
    name="review",
    help="Review lifecycle commands: tasks.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# plan subcommand
# ---------------------------------------------------------------------------


def plan(
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Generate features and tasks from the parsed PRD.

    Re-reads prd.md, emits feature.created and task.created events for each
    feature and task found.  Then runs dependency and conflict-group inference
    and promotes all tasks from proposed to drafted.

    Idempotent: running plan twice will not duplicate tasks (INSERT OR REPLACE
    semantics in the SQLite backend handle deduplication by task ID).
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.planning.inference import infer_all
    from fakoli_state.planning.template import parse_prd
    from fakoli_state.state.models import Event

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    prd_path = state_dir / _PRD_FILENAME
    if not prd_path.exists():
        typer.echo(
            f"Error: PRD file not found at {prd_path}. "
            "Author your PRD first, then run `fakoli-state prd parse`.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        markdown = prd_path.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: cannot read {prd_path}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    result = parse_prd(markdown, prd_id="prd")

    # Non-fatal parse errors are surfaced as warnings during plan.
    if result.errors:
        for err in result.errors:
            typer.echo(
                f"  Warning [{err.section}:{err.line}]: {err.message}",
                err=True,
            )

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()

        # Emit feature.created for each feature.
        for feature in result.features:
            now = clock.now()
            feature_data = feature.model_dump(mode="json")
            event = Event(
                id=PENDING_EVENT_ID,
                timestamp=now,
                actor="fakoli-state-cli",
                action="feature.created",
                target_kind="feature",
                target_id=feature.id,
                payload_json=feature_data,
            )
            backend.apply_event(event)

        # Emit task.created for each task (status proposed at creation time).
        for task in result.tasks:
            now = clock.now()
            task_data = task.model_dump(mode="json")
            event = Event(
                id=PENDING_EVENT_ID,
                timestamp=now,
                actor="fakoli-state-cli",
                action="task.created",
                target_kind="task",
                target_id=task.id,
                payload_json=task_data,
            )
            backend.apply_event(event)

        # Run inference on the parsed tasks (before they are stored with updated
        # deps/conflict groups — we upsert them via task.created events again).
        inference_result = infer_all(result.tasks)

        # Re-upsert tasks with inferred dependencies and conflict groups,
        # then promote proposed → drafted.
        for inferred_task in inference_result.tasks:
            now = clock.now()
            # Upsert with full updated fields.
            task_data = inferred_task.model_dump(mode="json")
            upsert_event = Event(
                id=PENDING_EVENT_ID,
                timestamp=now,
                actor="fakoli-state-cli",
                action="task.created",
                target_kind="task",
                target_id=inferred_task.id,
                payload_json=task_data,
            )
            backend.apply_event(upsert_event)

            # Promote proposed → drafted, but ONLY if the task is currently
            # at 'proposed'. On re-plan, existing tasks may have advanced
            # past 'drafted' (Phase 4+: claimed, in_progress, etc.) and
            # emitting a status_changed for those would error or worse
            # silently regress them. The task.created upsert above does NOT
            # touch status (Greptile PR #38 fix), so existing-task status
            # is preserved; we only need to promote fresh proposed tasks.
            current = backend.get_task(inferred_task.id)
            if current is not None and current.status.value == "proposed":
                now = clock.now()
                status_event = Event(
                    id=PENDING_EVENT_ID,
                    timestamp=now,
                    actor="fakoli-state-cli",
                    action="task.status_changed",
                    target_kind="task",
                    target_id=inferred_task.id,
                    payload_json={
                        "task_id": inferred_task.id,
                        "from": "proposed",
                        "to": "drafted",
                        "reason": "plan: initial draft after inference",
                    },
                )
                backend.apply_event(status_event)
    finally:
        backend.close()

    typer.echo(
        f"Planned {len(result.features)} features, "
        f"{len(result.tasks)} tasks."
    )
    if inference_result.conflict_groups:
        typer.echo(
            f"Detected {len(inference_result.conflict_groups)} conflict group(s)."
        )


# ---------------------------------------------------------------------------
# score subcommand
# ---------------------------------------------------------------------------


def score(
    task_id: str | None = typer.Argument(  # noqa: B008
        None,
        help="Task ID to score. Omit to score all tasks lacking complete scores.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Score tasks across six dimensions using rule-based heuristics.

    Without TASK_ID: scores all tasks whose scores are incomplete.
    With TASK_ID: scores that single task.

    Emits a task.scored event per task and prints a summary table.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.planning.scoring import score_task
    from fakoli_state.state.models import Event

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()

        if task_id is not None:
            task = backend.get_task(task_id)
            if task is None:
                typer.echo(
                    f"Error: task '{task_id}' not found.",
                    err=True,
                )
                raise typer.Exit(code=1)
            tasks_to_score = [task]
        else:
            all_tasks = backend.list_tasks()
            tasks_to_score = [
                t for t in all_tasks if not _scores_complete(t)
            ]

        if not tasks_to_score:
            typer.echo("No tasks require scoring.")
            return

        scored_tasks = []
        for task in tasks_to_score:
            computed_score = score_task(task)
            now = clock.now()
            score_payload: dict[str, object] = {
                "task_id": task.id,
                "scores": {
                    "complexity": computed_score.complexity,
                    "parallelizability": computed_score.parallelizability,
                    "context_load": computed_score.context_load,
                    "blast_radius": computed_score.blast_radius,
                    "review_risk": computed_score.review_risk,
                    "agent_suitability": computed_score.agent_suitability,
                },
                "explanation": computed_score.explanation,
            }

            event = Event(
                id=PENDING_EVENT_ID,
                timestamp=now,
                actor="fakoli-state-cli",
                action="task.scored",
                target_kind="task",
                target_id=task.id,
                payload_json=score_payload,
            )
            backend.apply_event(event)
            scored_tasks.append((task, computed_score))
    finally:
        backend.close()

    # Print summary table.
    header = (
        f"{'TaskID':<12} "
        f"{'Complexity':>10} "
        f"{'Parallel':>8} "
        f"{'CtxLoad':>7} "
        f"{'Blast':>5} "
        f"{'Review':>6} "
        f"{'Agent':>5}"
    )
    typer.echo(header)
    typer.echo("-" * len(header))
    for task, s in scored_tasks:
        typer.echo(
            f"{task.id:<12} "
            f"{str(s.complexity):>10} "
            f"{str(s.parallelizability):>8} "
            f"{str(s.context_load):>7} "
            f"{str(s.blast_radius):>5} "
            f"{str(s.review_risk):>6} "
            f"{str(s.agent_suitability):>5}"
        )
    typer.echo(f"\nScored {len(scored_tasks)} task(s).")


# ---------------------------------------------------------------------------
# expand subcommand
# ---------------------------------------------------------------------------


def expand(
    task_id: str = typer.Argument(..., help="Task ID to expand into subtasks."),  # noqa: B008
    use_llm: bool = typer.Option(  # noqa: B008
        False,
        "--use-llm",
        help="Use LLM augmentation to generate subtasks (Phase 7 feature).",
    ),
) -> None:
    """Expand a task into subtasks (Phase 7 LLM feature — not yet available).

    Without --use-llm this command refuses with a clear error.  Deterministic
    expansion requires manual subtask authoring in prd.md as T001.1, T001.2 entries.
    """
    if not use_llm:
        typer.echo(
            "Error: expand requires --use-llm (Phase 7) OR manual subtask authoring "
            f"in prd.md as {task_id}.1, {task_id}.2 entries.",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(
        "Error: --use-llm is not yet implemented (Phase 7).",
        err=True,
    )
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# review tasks subcommand
# ---------------------------------------------------------------------------


@review_app.command("tasks")
def review_tasks(
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Promote tasks through the review lifecycle.

    Attempts to promote drafted → reviewed → ready for each eligible task.
    Gate for drafted → reviewed: acceptance_criteria non-empty AND
    verification.commands non-empty.

    Prints a summary of how many tasks were promoted and how many were blocked
    by gates (with reasons).
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.models import Event
    from fakoli_state.state.transitions import (
        TransitionError,
        task_drafted_to_reviewed,
        task_reviewed_to_ready,
    )

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()
        all_tasks = backend.list_tasks()

        drafted_tasks = [t for t in all_tasks if t.status.value == "drafted"]
        reviewed_tasks = [t for t in all_tasks if t.status.value == "reviewed"]

        promoted_to_reviewed: list[str] = []
        promoted_to_ready: list[str] = []
        blocked: list[tuple[str, str]] = []  # (task_id, reason)

        # drafted → reviewed
        for task in drafted_tasks:
            now = clock.now()
            try:
                task_drafted_to_reviewed(task, now)
            except TransitionError as exc:
                blocked.append((task.id, exc.message))
                continue

            event = Event(
                id=PENDING_EVENT_ID,
                timestamp=now,
                actor="fakoli-state-cli",
                action="task.status_changed",
                target_kind="task",
                target_id=task.id,
                payload_json={
                    "task_id": task.id,
                    "from": "drafted",
                    "to": "reviewed",
                    "reason": "review tasks: gate passed",
                },
            )
            backend.apply_event(event)
            promoted_to_reviewed.append(task.id)

        # reviewed → ready (includes tasks that just moved to reviewed above)
        # Re-query to get current state after the drafted → reviewed promotions.
        all_tasks_now = backend.list_tasks()
        newly_reviewed = [
            t for t in all_tasks_now
            if t.status.value == "reviewed"
            and (t.id in promoted_to_reviewed or t.id in [rt.id for rt in reviewed_tasks])
        ]

        for task in newly_reviewed:
            now = clock.now()
            try:
                task_reviewed_to_ready(task, now)
            except TransitionError as exc:
                blocked.append((task.id, exc.message))
                continue

            event = Event(
                id=PENDING_EVENT_ID,
                timestamp=now,
                actor="fakoli-state-cli",
                action="task.status_changed",
                target_kind="task",
                target_id=task.id,
                payload_json={
                    "task_id": task.id,
                    "from": "reviewed",
                    "to": "ready",
                    "reason": "review tasks: promoted to ready",
                },
            )
            backend.apply_event(event)
            promoted_to_ready.append(task.id)
    finally:
        backend.close()

    total_promoted = len(promoted_to_reviewed) + len(promoted_to_ready)
    typer.echo(f"Promoted {len(promoted_to_reviewed)} task(s) to reviewed.")
    typer.echo(f"Promoted {len(promoted_to_ready)} task(s) to ready.")
    if blocked:
        typer.echo(f"\nBlocked {len(blocked)} task(s):")
        for tid, reason in blocked:
            typer.echo(f"  {tid}: {reason}")
    else:
        typer.echo(f"\n{total_promoted} total promotion(s). No tasks blocked.")


# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------


def list_tasks(
    status: str | None = typer.Option(  # noqa: B008
        None,
        "--status",
        help="Filter by task status (e.g. ready, drafted, reviewed).",
    ),
    feature: str | None = typer.Option(  # noqa: B008
        None,
        "--feature",
        help="Filter by feature ID (e.g. F001).",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """List tasks with optional status and feature filters.

    Prints a table: TaskID | Title | Status | Priority | Score | Feature.
    """
    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        tasks = backend.list_tasks(status=status, feature_id=feature)
    finally:
        backend.close()

    if not tasks:
        filters = []
        if status:
            filters.append(f"status={status}")
        if feature:
            filters.append(f"feature={feature}")
        filter_str = " (" + ", ".join(filters) + ")" if filters else ""
        typer.echo(f"No tasks found{filter_str}.")
        return

    # Column widths.
    id_w = max(len("TaskID"), max(len(t.id) for t in tasks))
    title_w = min(40, max(len("Title"), max(len(t.title) for t in tasks)))
    status_w = max(len("Status"), max(len(t.status.value) for t in tasks))
    priority_w = max(len("Priority"), max(len(t.priority.value) for t in tasks))
    feature_w = max(len("Feature"), max(len(t.feature_id) for t in tasks))

    header = (
        f"{'TaskID':<{id_w}}  "
        f"{'Title':<{title_w}}  "
        f"{'Status':<{status_w}}  "
        f"{'Priority':<{priority_w}}  "
        f"{'Score':>13}  "
        f"{'Feature':<{feature_w}}"
    )
    typer.echo(header)
    typer.echo("-" * len(header))

    for task in tasks:
        title_display = task.title[:title_w]
        complexity = task.scores.complexity
        agent_suit = task.scores.agent_suitability
        score_str = (
            f"{complexity}/{agent_suit}"
            if complexity is not None and agent_suit is not None
            else "unscored"
        )
        typer.echo(
            f"{task.id:<{id_w}}  "
            f"{title_display:<{title_w}}  "
            f"{task.status.value:<{status_w}}  "
            f"{task.priority.value:<{priority_w}}  "
            f"{score_str:>13}  "
            f"{task.feature_id:<{feature_w}}"
        )

    typer.echo(f"\n{len(tasks)} task(s) listed.")


# ---------------------------------------------------------------------------
# show subcommand
# ---------------------------------------------------------------------------


def show(
    task_id: str = typer.Argument(..., help="Task ID to display (e.g. T001)."),  # noqa: B008
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Print full task detail in human-readable multi-section format.

    Displays: title, feature, status, priority, scores breakdown (all six
    dimensions + explanation), dependencies, conflict groups, acceptance
    criteria, verification commands, likely files, claim (if any), and
    recent events.
    """
    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        task = backend.get_task(task_id)
        if task is None:
            typer.echo(f"Error: task '{task_id}' not found.", err=True)
            raise typer.Exit(code=1)

        # Fetch active claims for this task.
        active_claims = backend.list_active_claims()
        task_claims = [c for c in active_claims if c.task_id == task.id]

        # Fetch recent events for this task via the Backend protocol.
        recent_events = backend.list_events(target_id=task.id, target_kind="task", limit=10)
    finally:
        backend.close()

    def _section(title: str) -> None:
        typer.echo(f"\n{title}")
        typer.echo("-" * len(title))

    typer.echo(f"Task {task.id}: {task.title}")
    typer.echo(f"Feature:  {task.feature_id}")
    typer.echo(f"Status:   {task.status.value}")
    typer.echo(f"Priority: {task.priority.value}")

    _section("Scores")
    s = task.scores
    if _scores_complete(task):
        typer.echo(f"  complexity:         {s.complexity}")
        typer.echo(f"  parallelizability:  {s.parallelizability}")
        typer.echo(f"  context_load:       {s.context_load}")
        typer.echo(f"  blast_radius:       {s.blast_radius}")
        typer.echo(f"  review_risk:        {s.review_risk}")
        typer.echo(f"  agent_suitability:  {s.agent_suitability}")
        if s.explanation:
            indented = s.explanation.replace("\n", "\n    ")
            typer.echo(f"\n  Explanation:\n    {indented}")
    else:
        typer.echo("  (not yet scored — run `fakoli-state score`)")

    _section("Dependencies")
    if task.dependencies:
        for dep_id in task.dependencies:
            typer.echo(f"  {dep_id}")
    else:
        typer.echo("  (none)")

    _section("Conflict Groups")
    if task.conflict_groups:
        for cg_id in task.conflict_groups:
            typer.echo(f"  {cg_id}")
    else:
        typer.echo("  (none)")

    _section("Acceptance Criteria")
    if task.acceptance_criteria:
        for criterion in task.acceptance_criteria:
            typer.echo(f"  - {criterion}")
    else:
        typer.echo("  (none — required before review)")

    _section("Verification Commands")
    if task.verification.commands:
        for cmd in task.verification.commands:
            typer.echo(f"  $ {cmd}")
    else:
        typer.echo("  (none — required before review)")

    _section("Likely Files")
    if task.likely_files:
        for f in task.likely_files:
            typer.echo(f"  {f}")
    else:
        typer.echo("  (none specified)")

    _section("Active Claims")
    if task_claims:
        for claim in task_claims:
            typer.echo(f"  {claim.id}: claimed by '{claim.claimed_by}' "
                       f"(expires {claim.lease_expires_at.isoformat()})")
    else:
        typer.echo("  (none)")

    _section("Recent Events")
    if recent_events:
        for ev_action, ev_ts in recent_events:
            typer.echo(f"  [{ev_ts}] {ev_action}")
    else:
        typer.echo("  (none)")
