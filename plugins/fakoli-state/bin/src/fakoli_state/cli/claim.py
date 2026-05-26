"""claim, release, renew, next commands (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import typer

from fakoli_state.cli._helpers import (
    _open_backend,
    _reap_stale_claims,
    _require_state_dir,
    _resolve_state_dir,
)

# ---------------------------------------------------------------------------
# claim subcommand
# ---------------------------------------------------------------------------


def claim(
    task_id: str = typer.Argument(..., help="Task ID to claim (e.g. T001)."),  # noqa: B008
    worktree: bool = typer.Option(  # noqa: B008
        False,
        "--worktree",
        help="Also create a git worktree at ../wt-<task_id>/.",
    ),
    force: bool = typer.Option(  # noqa: B008
        False,
        "--force",
        help=(
            "Override file-conflict warnings (overlapping likely_files with "
            "an active claim) AND silence v1.16.0 dependency warnings "
            "(undone task.dependencies). The claim itself proceeds either "
            "way for the dependency check; --force only silences the "
            "noise."
        ),
    ),
    actor: str | None = typer.Option(  # noqa: B008
        None,
        "--actor",
        help="Claim actor; defaults to $USER or 'agent'.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Acquire an exclusive lease on TASK_ID and create an agent/<task>-<slug> branch."""
    import os

    from fakoli_state.claims.manager import ClaimError, ClaimManager, ConflictWarning
    from fakoli_state.clock import SystemClock
    from fakoli_state.git_ops.branch import create_branch_for_task
    from fakoli_state.git_ops.worktree import create_worktree_for_task

    resolved_actor = actor or os.environ.get("USER") or "agent"
    resolved_cwd = cwd.resolve() if cwd is not None else Path.cwd().resolve()
    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()

        # Reap stale claims before doing anything.
        _reap_stale_claims(backend)

        manager = ClaimManager(backend, clock, actor=resolved_actor)

        # Gate: task must exist.
        task = backend.get_task(task_id)
        if task is None:
            typer.echo(f"Error: task '{task_id}' not found.", err=True)
            raise typer.Exit(code=1)

        # Pre-claim conflict check (file overlap + group).  Fetch expected_files
        # from likely_files — the manager uses these for overlap detection.
        expected_files = list(task.likely_files) if task.likely_files else []
        conflicts: list[ConflictWarning] = manager.check_conflicts(task_id, expected_files)
        if conflicts and not force:
            typer.echo(
                f"Warning: task '{task_id}' has file conflicts with active claims:",
                err=True,
            )
            for c in conflicts:
                typer.echo(
                    f"  Claim {c.other_claim_id} by '{c.other_actor}': "
                    f"overlapping files: {c.overlapping_files}",
                    err=True,
                )
            typer.echo(
                "Pass --force to override and claim anyway.",
                err=True,
            )
            raise typer.Exit(code=1)

        # Dependency check (v1.16.0). Soft gate: warn when one or more of
        # task.dependencies are not yet `done`, but proceed with the claim.
        # The user's stacked-PR workflow (claim T002 while T001 is still
        # in_progress and merge them together) is legitimate; we just want
        # them to KNOW the deps aren't done so the choice is informed.
        # --force silences the warning. Mirrors the conflict-check pattern
        # one above but with warn-only semantics.
        if task.dependencies and not force:
            undone_deps: list[tuple[str, str]] = []  # (dep_id, status)
            for dep_id in task.dependencies:
                dep = backend.get_task(dep_id)
                if dep is None:
                    undone_deps.append((dep_id, "not-found"))
                elif dep.status.value != "done":
                    undone_deps.append((dep_id, dep.status.value))
            if undone_deps:
                typer.echo(
                    f"Warning: task '{task_id}' has "
                    f"{len(undone_deps)} dependency(ies) that are not yet "
                    "`done`. Claiming anyway, but the work may be "
                    "blocked or need rebasing once the deps land:",
                    err=True,
                )
                for dep_id, dep_status in undone_deps:
                    typer.echo(
                        f"  - {dep_id} ({dep_status})",
                        err=True,
                    )
                typer.echo(
                    "Pass --force to silence this warning, OR claim the "
                    "dependencies first, OR plan a stacked-branch workflow.",
                    err=True,
                )

        try:
            result = manager.claim(task_id, expected_files=expected_files, force=force)
        except ClaimError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        # Git branch creation — non-blocking; warnings go to stderr.
        # v1.15.0: branch_prefix is host-project-configurable so claims
        # respect `feature/` / `fix/` conventions instead of forcing
        # `agent/` everywhere. Falls back silently to the default when
        # config.yaml is missing (e.g. ad-hoc test runs).
        branch_prefix = "agent"
        config_path = state_dir / "config.yaml"
        if config_path.exists():
            try:
                from fakoli_state.config import load_config
                cfg = load_config(config_path)
                branch_prefix = cfg.branch_prefix
            except (OSError, ValueError) as exc:
                # Config-load failure should NOT block a claim — fall back
                # to the default prefix and let the user fix config.yaml
                # at their leisure. BUT surface the failure to stderr so
                # the user sees why the branch ended up `agent/...` when
                # they thought they had set `branch_prefix: feature`.
                # Silent fallbacks on configuration are exactly the bug
                # class v1.15.0 was supposed to fix (critic SHOULD FIX
                # from PR #63 review).
                typer.echo(
                    f"Warning: config.yaml load failed ({exc.__class__.__name__}: "
                    f"{exc}); using default branch_prefix='agent'.",
                    err=True,
                )

        branch_result = create_branch_for_task(
            task_id,
            task.title,
            cwd=resolved_cwd,
            branch_prefix=branch_prefix,
        )
        if branch_result.created and branch_result.reason:
            typer.echo(f"Warning (branch): {branch_result.reason}", err=True)
        elif not branch_result.created:
            typer.echo(
                f"Warning: git branch not created — {branch_result.reason}",
                err=True,
            )

        # Optional worktree creation.
        worktree_path: str | None = None
        if worktree:
            if branch_result.created and branch_result.branch:
                wt_result = create_worktree_for_task(
                    task_id,
                    branch_result.branch,
                    cwd=resolved_cwd,
                )
                if wt_result.created:
                    worktree_path = wt_result.path
                else:
                    typer.echo(
                        f"Warning: worktree not created — {wt_result.reason}",
                        err=True,
                    )
            else:
                typer.echo(
                    "Warning: --worktree skipped because no branch was created.",
                    err=True,
                )

        claim_obj = result.claim
    finally:
        backend.close()

    # Confirmation output.
    typer.echo(f"Claimed task '{task_id}' as '{resolved_actor}'.")
    typer.echo(f"  Claim ID:    {claim_obj.id}")
    typer.echo(f"  Lease until: {claim_obj.lease_expires_at.isoformat()}")
    if branch_result.created and branch_result.branch:
        typer.echo(f"  Branch:      {branch_result.branch}")
    if worktree_path:
        typer.echo(f"  Worktree:    {worktree_path}")
    typer.echo("")
    typer.echo(
        f"Run `fakoli-state renew {claim_obj.id}` to extend the lease before it expires."
    )


# ---------------------------------------------------------------------------
# release subcommand
# ---------------------------------------------------------------------------


def release(
    claim_id: str = typer.Argument(..., help="Claim ID to release (e.g. C001)."),  # noqa: B008
    force: bool = typer.Option(  # noqa: B008
        False,
        "--force",
        help="Force release even if the claim belongs to another actor.",
    ),
    reason: str | None = typer.Option(  # noqa: B008
        None,
        "--reason",
        help="Human-readable reason for the release.",
    ),
    actor: str | None = typer.Option(  # noqa: B008
        None,
        "--actor",
        help="Actor identity; defaults to $USER or 'agent'.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Release a claim by CLAIM_ID, returning the task to 'ready'."""
    import os

    from fakoli_state.claims.manager import ClaimError, ClaimManager
    from fakoli_state.clock import SystemClock

    resolved_actor = actor or os.environ.get("USER") or "agent"
    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()
        _reap_stale_claims(backend)

        manager = ClaimManager(backend, clock, actor=resolved_actor)
        try:
            manager.release(claim_id, force=force, reason=reason)
        except ClaimError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    finally:
        backend.close()

    typer.echo(f"Released claim '{claim_id}'.")
    if reason:
        typer.echo(f"  Reason: {reason}")


# ---------------------------------------------------------------------------
# renew subcommand
# ---------------------------------------------------------------------------


def renew(
    claim_id: str = typer.Argument(..., help="Claim ID to renew (e.g. C001)."),  # noqa: B008
    actor: str | None = typer.Option(  # noqa: B008
        None,
        "--actor",
        help="Actor identity; defaults to $USER or 'agent'.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Extend the lease heartbeat on CLAIM_ID."""
    import os

    from fakoli_state.claims.manager import ClaimError, ClaimManager
    from fakoli_state.clock import SystemClock

    resolved_actor = actor or os.environ.get("USER") or "agent"
    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()
        _reap_stale_claims(backend)

        manager = ClaimManager(backend, clock, actor=resolved_actor)
        try:
            updated = manager.renew(claim_id)
        except ClaimError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    finally:
        backend.close()

    typer.echo(f"Renewed claim '{claim_id}'.")
    typer.echo(f"  New lease until: {updated.lease_expires_at.isoformat()}")
    typer.echo(f"  Last heartbeat:  {updated.last_heartbeat_at.isoformat()}")


# ---------------------------------------------------------------------------
# next subcommand
# ---------------------------------------------------------------------------


def next(  # noqa: A001
    actor: str | None = typer.Option(  # noqa: B008
        None,
        "--actor",
        help="Actor identity; defaults to $USER or 'agent'.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Pick the highest-priority claimable task without claiming it.

    Prints the recommended task ID and title.  Run `fakoli-state claim TASK_ID`
    to acquire the lease after reviewing the recommendation.
    """
    import os

    from fakoli_state.claims.manager import ClaimManager
    from fakoli_state.clock import SystemClock

    resolved_actor = actor or os.environ.get("USER") or "agent"
    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()
        _reap_stale_claims(backend)

        manager = ClaimManager(backend, clock, actor=resolved_actor)
        task = manager.next_claimable()
    finally:
        backend.close()

    if task is None:
        typer.echo("No claimable tasks available.")
        return

    typer.echo(f"Next recommended task: {task.id}")
    typer.echo(f"  Title:    {task.title}")
    typer.echo(f"  Priority: {task.priority.value}")
    if task.scores.complexity is not None:
        typer.echo(f"  Complexity: {task.scores.complexity}")
    typer.echo("")
    typer.echo(f"Run `fakoli-state claim {task.id}` to acquire the lease.")
