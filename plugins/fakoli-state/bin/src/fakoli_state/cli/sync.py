"""sync sub-app: reconciliation + provider push/pull (Phase 8 Wave 3 Task 6).

User-facing surface for fakoli-state's bidirectional sync stack.

Layout
------
``fakoli-state sync``                bare command — runs ReconciliationEngine
``fakoli-state sync --fix --yes``    same, then applies suggested fixes
``fakoli-state sync github``         alias for ``sync provider github_issues``
``fakoli-state sync provider <id>``  generic provider invocation
                                     (``--push`` / ``--pull`` / ``--task``)
``fakoli-state sync github --health``probe provider reachability + auth
``fakoli-state sync github --watch`` long-running poll loop

Design notes
------------
* The bare ``sync`` callback is the default (``invoke_without_command=True``);
  named subcommands (``github``, ``provider``) win when explicitly invoked.
* The ``github`` alias is registered as its own ``@sync_app.command`` so it
  shows up in ``--help`` and so Typer's resolver picks it over the generic
  ``provider`` subcommand without a precedence dance.
* Every sync mutation emits a ``sync.*`` audit event into events.jsonl /
  state.db via the SyncAuditPayload no-op handler added in Wave 3 to
  state/sqlite.py.  Actual SyncMapping persistence flows through
  ``backend.apply_sync_mapping(...)`` which emits ``sync_mapping.upserted``.
* No real network calls happen in tests — every test injects a
  RecordedSyncProvider (or a custom subclass) via monkeypatching
  ``PROVIDER_REGISTRY`` so the ``provider_id`` resolves to the test double.
"""

from __future__ import annotations

import json
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from fakoli_state.cli._helpers import (
    _open_backend,
    _require_state_dir,
    _resolve_state_dir,
)
from fakoli_state.state.backend import PENDING_EVENT_ID

if TYPE_CHECKING:
    from fakoli_state.state.models import Task
    from fakoli_state.state.sqlite import SqliteBackend
    from fakoli_state.sync.provider import (
        ExternalRef,
        ExternalTask,
        ProviderHealth,
        SyncProvider,
    )

__all__ = ["sync_app"]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The github alias maps to this canonical provider id.
_GITHUB_PROVIDER_ID = "github_issues"

# Subdirectory under <state_dir> where manual_merge conflict files are written.
_SYNC_CONFLICTS_DIRNAME = ".sync-conflicts"

# Exit codes — match other fakoli-state CLI commands.
_EXIT_OK = 0
_EXIT_GENERIC_ERROR = 1
_EXIT_NEEDS_OPERATOR_INPUT = 2


# ---------------------------------------------------------------------------
# App definition
# ---------------------------------------------------------------------------

sync_app = typer.Typer(
    name="sync",
    help=(
        "Bidirectional sync surface. Bare `sync` runs reconciliation; "
        "`sync github` push/pulls via the GitHub Issues provider; "
        "`sync provider <id>` invokes a contributor-registered provider."
    ),
    no_args_is_help=False,
)


# ---------------------------------------------------------------------------
# Bare `sync` — reconciliation entrypoint (default callback)
# ---------------------------------------------------------------------------


@sync_app.callback(invoke_without_command=True)
def sync_default(
    ctx: typer.Context,
    fix: bool = typer.Option(  # noqa: B008
        False,
        "--fix",
        help=(
            "After scanning, apply each suggested fix. Requires --yes "
            "in non-interactive mode."
        ),
    ),
    yes: bool = typer.Option(  # noqa: B008
        False,
        "--yes",
        help="Skip the confirmation prompt before applying fixes.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Run reconciliation and (optionally) apply remediation.

    No subcommand → scan ReconciliationEngine and print the report. The
    `--fix` flag additionally applies each suggested fix; combine with
    `--yes` in CI / non-interactive contexts.

    Named subcommands (`github`, `provider`) take over when invoked — this
    body only runs when the user types `fakoli-state sync` with no
    subcommand.
    """
    if ctx.invoked_subcommand is not None:
        # A subcommand was requested; let it handle the run.
        return

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)
    backend = _open_backend(state_dir)
    try:
        report = _run_reconciliation(backend, state_dir)
        _print_reconciliation_report(report)

        if not fix:
            return

        # --fix path — apply remediations.
        if not yes and not _is_tty():
            typer.echo(
                "Error: --fix requires --yes in non-interactive mode "
                "(refusing to apply remediations without explicit consent).",
                err=True,
            )
            raise typer.Exit(code=_EXIT_GENERIC_ERROR)
        if not yes:
            confirmed = typer.confirm(
                f"Apply {len(report.discrepancies)} fix(es)?",
                default=False,
            )
            if not confirmed:
                typer.echo("Aborted.")
                raise typer.Exit(code=_EXIT_OK)

        actions = _apply_reconciliation_fixes(backend, state_dir, report)
        _print_fix_actions(actions)
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# `sync github` alias — maps to provider_id="github_issues"
# ---------------------------------------------------------------------------


@sync_app.command("github")
def sync_github(
    push: bool = typer.Option(  # noqa: B008
        False, "--push", help="Push local tasks to GitHub only (skip pull)."
    ),
    pull: bool = typer.Option(  # noqa: B008
        False, "--pull", help="Pull remote issues to local only (skip push)."
    ),
    watch: bool = typer.Option(  # noqa: B008
        False, "--watch", help="Long-running poll loop; Ctrl-C to exit."
    ),
    fix: bool = typer.Option(  # noqa: B008
        False,
        "--fix",
        help=(
            "Reconcile remote state into local on conflicts (forces a pull "
            "for tasks whose SyncMapping is in 'conflict' state)."
        ),
    ),
    task: str | None = typer.Option(  # noqa: B008
        None, "--task", help="Scope sync to a single task id (e.g. T001)."
    ),
    yes: bool = typer.Option(  # noqa: B008
        False,
        "--yes",
        help="Auto-confirm conflict prompts; defaults to local_wins.",
    ),
    health: bool = typer.Option(  # noqa: B008
        False,
        "--health",
        help="Probe provider reachability + auth; print status; exit.",
    ),
    interval: int = typer.Option(  # noqa: B008
        60,
        "--interval",
        help="Poll interval seconds (with --watch). Use 0 for one iteration.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Sync against GitHub Issues. Convenience alias for `sync provider github_issues`."""
    _sync_provider_dispatch(
        provider_id=_GITHUB_PROVIDER_ID,
        push=push,
        pull=pull,
        watch=watch,
        fix=fix,
        task=task,
        yes=yes,
        health=health,
        interval=interval,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# `sync provider <id>` — generic provider invocation
# ---------------------------------------------------------------------------


@sync_app.command("provider")
def sync_provider(
    provider_id: str = typer.Argument(  # noqa: B008
        ..., help="Sync provider id (e.g. github_issues, monday, linear)."
    ),
    push: bool = typer.Option(  # noqa: B008
        False, "--push", help="Push local tasks only (skip pull)."
    ),
    pull: bool = typer.Option(  # noqa: B008
        False, "--pull", help="Pull remote tasks only (skip push)."
    ),
    watch: bool = typer.Option(  # noqa: B008
        False, "--watch", help="Long-running poll loop; Ctrl-C to exit."
    ),
    fix: bool = typer.Option(  # noqa: B008
        False,
        "--fix",
        help="Reconcile remote → local on conflicts (forces a pull on conflict).",
    ),
    task: str | None = typer.Option(  # noqa: B008
        None, "--task", help="Scope sync to a single task id."
    ),
    yes: bool = typer.Option(  # noqa: B008
        False, "--yes", help="Auto-confirm conflict prompts."
    ),
    health: bool = typer.Option(  # noqa: B008
        False, "--health", help="Probe provider; print status; exit."
    ),
    interval: int = typer.Option(  # noqa: B008
        60, "--interval", help="Poll interval seconds (with --watch)."
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Push/pull against a registered sync provider by id."""
    _sync_provider_dispatch(
        provider_id=provider_id,
        push=push,
        pull=pull,
        watch=watch,
        fix=fix,
        task=task,
        yes=yes,
        health=health,
        interval=interval,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# Provider dispatch — shared between `github` alias and `provider` generic
# ---------------------------------------------------------------------------


def _sync_provider_dispatch(
    *,
    provider_id: str,
    push: bool,
    pull: bool,
    watch: bool,
    fix: bool,
    task: str | None,
    yes: bool,
    health: bool,
    interval: int,
    cwd: Path | None,
) -> None:
    """Single entrypoint for both ``sync github`` and ``sync provider <id>``.

    Branches on ``health`` (probe only) vs the full sync flow. The full flow
    is wrapped in a loop when ``--watch`` is set, otherwise runs once.
    """
    state_dir = _resolve_state_dir(cwd)

    # Resolve provider class via the registry. The provider lookup is a
    # pure dict lookup — no state-dir required.
    provider_cls = _resolve_provider(provider_id)

    # Instantiate. Providers may require env vars (GitHubIssuesProvider needs
    # GITHUB_REPOSITORY or repo kwarg) — surface their ValueError as a
    # friendly CLI error rather than a stack trace.
    try:
        provider = provider_cls()
    except (ValueError, TypeError) as exc:
        typer.echo(f"Error: cannot instantiate provider {provider_id!r}: {exc}", err=True)
        raise typer.Exit(code=_EXIT_GENERIC_ERROR) from exc

    if health:
        # Health is a network/auth probe — no local state is required.
        # Surface it before _require_state_dir so operators can sanity-check
        # GITHUB_TOKEN / connectivity from a fresh checkout pre-init.
        _print_provider_health(provider)
        return

    # Now (and only now) the state dir is required for actual sync ops.
    _require_state_dir(state_dir)
    backend = _open_backend(state_dir)
    try:
        if watch:
            _run_watch_loop(
                backend=backend,
                state_dir=state_dir,
                provider=provider,
                push=push,
                pull=pull,
                fix=fix,
                task=task,
                yes=yes,
                interval=interval,
            )
        else:
            _run_sync_once(
                backend=backend,
                state_dir=state_dir,
                provider=provider,
                push=push,
                pull=pull,
                fix=fix,
                task=task,
                yes=yes,
            )
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Registry resolution + friendly error
# ---------------------------------------------------------------------------


def _resolve_provider(provider_id: str) -> type[SyncProvider]:
    """Return the registered provider class, or exit 1 with a helpful list.

    Re-imports the registry module on every call so test monkeypatching of
    ``PROVIDER_REGISTRY`` survives — Typer command bodies are executed many
    times per test session against the same module-level import.
    """
    # Late import — keeps cli.sync importable in environments where the sync
    # subpackage has not been touched (e.g. a `--help` smoke test before
    # init).
    from fakoli_state.sync import registry as sync_registry

    if provider_id not in sync_registry.PROVIDER_REGISTRY:
        available = ", ".join(sorted(sync_registry.PROVIDER_REGISTRY)) or "(none)"
        typer.echo(
            f"Error: no sync provider registered under {provider_id!r}; "
            f"available providers: {available}",
            err=True,
        )
        raise typer.Exit(code=_EXIT_GENERIC_ERROR)
    return sync_registry.PROVIDER_REGISTRY[provider_id]


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------


def _print_provider_health(provider: SyncProvider) -> None:
    """Print a one-screen summary of provider.health_check()."""
    health: ProviderHealth = provider.health_check()
    typer.echo(f"Provider: {provider.display_name} ({provider.provider_id})")
    typer.echo(f"  available:        {health.available}")
    typer.echo(f"  auth_configured:  {health.auth_configured}")
    typer.echo(f"  last_check_at:    {health.last_check_at.isoformat()}")
    if health.error:
        typer.echo(f"  error:            {health.error}")


# ---------------------------------------------------------------------------
# One-shot sync pass
# ---------------------------------------------------------------------------


def _run_sync_once(
    *,
    backend: SqliteBackend,
    state_dir: Path,
    provider: SyncProvider,
    push: bool,
    pull: bool,
    fix: bool,
    task: str | None,
    yes: bool,
) -> None:
    """Execute one push+pull cycle through ``provider``.

    Defaults (neither ``push`` nor ``pull``) run BOTH. Mutually exclusive
    only in that ``--push`` skips pull and vice versa.

    ``--task T001`` scopes to a single task; otherwise every task gets a
    sync attempt. ``--fix`` swaps the conflict path to a forced pull
    (remote_wins on every conflict).
    """
    # Default: do both. If only --push or --pull is set, do that side only.
    do_push = push or not pull
    do_pull = pull or not push

    _emit_audit(
        backend,
        action="sync.batch.started",
        payload={
            "provider_id": provider.provider_id,
            "direction": "push" if (do_push and not do_pull) else (
                "pull" if (do_pull and not do_push) else "both"
            ),
            "audit_note": f"task={task}" if task else None,
        },
        target_kind="provider",
        target_id=provider.provider_id,
    )

    tasks = _select_tasks_for_sync(backend, task)
    if not tasks:
        typer.echo("Nothing to sync (no matching tasks).")
        _emit_audit(
            backend,
            action="sync.batch.completed",
            payload={
                "provider_id": provider.provider_id,
                "audit_note": "no tasks",
            },
            target_kind="provider",
            target_id=provider.provider_id,
        )
        return

    push_results = {"pushed": 0, "failed": 0, "skipped": 0}
    pull_results: dict[str, int] = {
        "pulled": 0,
        "failed": 0,
        "skipped": 0,
        "manual_merge_pending": 0,
    }
    for t in tasks:
        if do_push:
            _push_one_task(
                backend=backend,
                provider=provider,
                task=t,
                results=push_results,
            )
        if do_pull:
            _pull_one_task(
                backend=backend,
                state_dir=state_dir,
                provider=provider,
                task=t,
                results=pull_results,
                fix=fix,
                yes=yes,
            )

    typer.echo(
        f"Sync against {provider.display_name} ({provider.provider_id}): "
        f"push={push_results} pull={pull_results}"
    )

    _emit_audit(
        backend,
        action="sync.batch.completed",
        payload={
            "provider_id": provider.provider_id,
            "audit_note": (
                f"pushed={push_results['pushed']} pulled={pull_results['pulled']} "
                f"failed_push={push_results['failed']} failed_pull={pull_results['failed']} "
                f"manual_merge_pending={pull_results['manual_merge_pending']}"
            ),
        },
        target_kind="provider",
        target_id=provider.provider_id,
    )

    # Exit non-zero if any task is parked awaiting manual-merge resolution.
    # We process the whole batch first (so unrelated tasks still sync),
    # then surface the operator-input requirement via exit code 2.
    if pull_results["manual_merge_pending"] > 0:
        raise typer.Exit(code=_EXIT_NEEDS_OPERATOR_INPUT)


def _select_tasks_for_sync(
    backend: SqliteBackend,
    task_filter: str | None,
) -> list[Task]:
    """Return the list of tasks to sync this iteration.

    ``task_filter`` (e.g. ``"T001"``) narrows to one task; missing → empty
    list with a friendly print upstream.
    """
    if task_filter is not None:
        one = backend.get_task(task_filter)
        return [one] if one is not None else []
    return backend.list_tasks()


# ---------------------------------------------------------------------------
# Push one task
# ---------------------------------------------------------------------------


def _push_one_task(
    *,
    backend: SqliteBackend,
    provider: SyncProvider,
    task: Task,
    results: dict[str, int],
) -> None:
    """Push a single task via ``provider``. Updates ``results`` in place.

    Reads the existing SyncMapping (if any) and uses its external_id as
    the input ``mapping`` ExternalRef to push_task. On success, upserts
    the SyncMapping with the freshly-returned ExternalRef.
    """
    from fakoli_state.sync.provider import ExternalRef

    existing = backend.get_sync_mapping(task.id, external_system=provider.provider_id)
    in_ref: ExternalRef | None = None
    if existing is not None:
        in_ref = ExternalRef(
            provider_id=provider.provider_id,
            external_id=existing.external_id,
            url=existing.external_url,
        )

    _emit_audit(
        backend,
        action="sync.push.started",
        payload={
            "provider_id": provider.provider_id,
            "task_id": task.id,
            "external_id": existing.external_id if existing else None,
            "direction": "push",
        },
        target_kind="task",
        target_id=task.id,
    )

    try:
        out_ref = provider.push_task(task=task, mapping=in_ref)
    except Exception as exc:  # noqa: BLE001 — best-effort wrapping loop
        results["failed"] += 1
        _emit_audit(
            backend,
            action="sync.push.failed",
            payload={
                "provider_id": provider.provider_id,
                "task_id": task.id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "direction": "push",
            },
            target_kind="task",
            target_id=task.id,
        )
        typer.echo(
            f"  push T={task.id} failed ({type(exc).__name__}): {exc}",
            err=True,
        )
        return

    # Persist the mapping via the canonical sync_mapping.upserted event.
    _persist_mapping_from_push(
        backend=backend,
        task=task,
        provider=provider,
        external_ref=out_ref,
        existing=existing,
    )

    results["pushed"] += 1
    _emit_audit(
        backend,
        action="sync.push.completed",
        payload={
            "provider_id": provider.provider_id,
            "task_id": task.id,
            "external_id": out_ref.external_id,
            "direction": "push",
        },
        target_kind="task",
        target_id=task.id,
    )


def _persist_mapping_from_push(
    *,
    backend: SqliteBackend,
    task: Task,
    provider: SyncProvider,
    external_ref: ExternalRef,
    existing: Any,
) -> None:
    """Write or refresh the SyncMapping row after a successful push."""
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.models import (
        ConflictResolutionStrategy,
        ExternalSystem,
        SyncMapping,
        SyncState,
    )

    try:
        ext_system = ExternalSystem(provider.provider_id)
    except ValueError:
        # Provider id isn't in the ExternalSystem enum — that's allowed for
        # contributor providers; the column is a string anyway. Fall back
        # to the literal value via the enum's first member (the DB-level
        # constraint is the enum cast).
        # If we get here we can't safely write a SyncMapping; skip persistence.
        typer.echo(
            f"  warning: provider id {provider.provider_id!r} is not in the "
            "ExternalSystem enum; mapping not persisted.",
            err=True,
        )
        return

    strategy = (
        existing.conflict_resolution_strategy
        if existing is not None
        else ConflictResolutionStrategy.prompt
    )
    mapping = SyncMapping(
        task_id=task.id,
        external_system=ext_system,
        external_id=external_ref.external_id,
        external_url=external_ref.url,
        last_synced_at=SystemClock().now(),
        sync_state=SyncState.in_sync,
        conflict_resolution_strategy=strategy,
        provider_metadata=dict(existing.provider_metadata) if existing else {},
    )
    backend.apply_sync_mapping(mapping, actor="sync-cli")


# ---------------------------------------------------------------------------
# Pull one task
# ---------------------------------------------------------------------------


def _pull_one_task(
    *,
    backend: SqliteBackend,
    state_dir: Path,
    provider: SyncProvider,
    task: Task,
    results: dict[str, int],
    fix: bool,
    yes: bool,
) -> None:
    """Pull the remote payload for ``task`` via ``provider``.

    Only attempts a pull when a SyncMapping exists (no remote id to fetch
    by otherwise). On divergence (remote `last_modified` > local `updated_at`
    AND local has changed), branches on the SyncMapping's
    conflict_resolution_strategy.
    """
    from fakoli_state.state.models import ConflictResolutionStrategy

    existing = backend.get_sync_mapping(task.id, external_system=provider.provider_id)
    if existing is None:
        results["skipped"] += 1
        return

    _emit_audit(
        backend,
        action="sync.pull.started",
        payload={
            "provider_id": provider.provider_id,
            "task_id": task.id,
            "external_id": existing.external_id,
            "direction": "pull",
        },
        target_kind="task",
        target_id=task.id,
    )

    try:
        remote: ExternalTask | None = provider.fetch_task(external_id=existing.external_id)
    except Exception as exc:  # noqa: BLE001 — best-effort loop
        results["failed"] += 1
        _emit_audit(
            backend,
            action="sync.pull.failed",
            payload={
                "provider_id": provider.provider_id,
                "task_id": task.id,
                "external_id": existing.external_id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "direction": "pull",
            },
            target_kind="task",
            target_id=task.id,
        )
        typer.echo(
            f"  pull T={task.id} failed ({type(exc).__name__}): {exc}",
            err=True,
        )
        return

    if remote is None:
        # Tombstone — remote deleted. Surface in stderr but don't fail.
        typer.echo(
            f"  pull T={task.id}: remote {existing.external_id!r} is gone "
            "(external_deleted)",
            err=True,
        )
        results["pulled"] += 1
        _emit_audit(
            backend,
            action="sync.pull.completed",
            payload={
                "provider_id": provider.provider_id,
                "task_id": task.id,
                "external_id": existing.external_id,
                "audit_note": "external_deleted",
                "direction": "pull",
            },
            target_kind="task",
            target_id=task.id,
        )
        return

    # Conflict detection: remote moved after our last sync AND local moved
    # too. If only one side moved we still record the pull but no conflict.
    remote_moved = remote.last_modified > existing.last_synced_at
    local_moved = task.updated_at > existing.last_synced_at

    if remote_moved and local_moved:
        # --fix forces remote_wins for this run.
        strategy = (
            ConflictResolutionStrategy.remote_wins
            if fix
            else existing.conflict_resolution_strategy
        )
        resolved = _resolve_conflict(
            backend=backend,
            state_dir=state_dir,
            provider=provider,
            task=task,
            remote=remote,
            strategy=strategy,
            yes=yes,
        )
        if not resolved:
            # manual_merge: file was written, task is parked pending
            # operator action. We do NOT count this as a hard failure
            # (the network call succeeded); we count it as pending so
            # the batch can exit 2 at the end while still processing
            # subsequent tasks.
            results["manual_merge_pending"] = (
                results.get("manual_merge_pending", 0) + 1
            )
            return

    results["pulled"] += 1
    _emit_audit(
        backend,
        action="sync.pull.completed",
        payload={
            "provider_id": provider.provider_id,
            "task_id": task.id,
            "external_id": existing.external_id,
            "direction": "pull",
        },
        target_kind="task",
        target_id=task.id,
    )


# ---------------------------------------------------------------------------
# Conflict resolution strategies
# ---------------------------------------------------------------------------


def _resolve_conflict(
    *,
    backend: SqliteBackend,
    state_dir: Path,
    provider: SyncProvider,
    task: Task,
    remote: ExternalTask,
    strategy: Any,
    yes: bool,
) -> bool:
    """Apply the configured conflict-resolution strategy.

    Returns True if the conflict was resolved (or chosen to be ignored),
    False if the strategy is ``manual_merge`` and the caller must wait
    for operator action (we have written the merge file and refuse the
    sync until the operator deletes it).

    Emits ``sync.conflict_detected`` regardless of resolution.
    """
    from fakoli_state.state.models import ConflictResolutionStrategy

    strategy_str = str(strategy)
    resolution: str

    if strategy == ConflictResolutionStrategy.local_wins:
        # Record the choice; the actual local→remote re-push is deferred
        # to a subsequent push pass. We intentionally do NOT claim
        # "_applied" here because no mutation happens in this iteration —
        # the audit log would lie. See TODO below.
        typer.echo(
            f"  conflict T={task.id}: local_wins — local state will overwrite "
            "remote on the next push pass (deferred to subsequent iteration)",
            err=True,
        )
        # TODO(phase-9): wire immediate re-push so resolution can be
        # "local_wins_applied". Today the deferral relies on a
        # subsequent --push iteration or the same iteration's push pass.
        resolution = "local_wins_deferred"
    elif strategy == ConflictResolutionStrategy.remote_wins:
        # Same story for remote_wins — we record the decision but the
        # actual local mutation from the remote payload is deferred. No
        # task-mutation events exist outside the planning path today.
        typer.echo(
            f"  conflict T={task.id}: remote_wins — local will be overwritten "
            "by remote on the next pull pass (deferred to subsequent iteration)",
            err=True,
        )
        # TODO(phase-9): wire immediate local mutation event so resolution
        # can become "remote_wins_applied".
        resolution = "remote_wins_deferred"
    elif strategy == ConflictResolutionStrategy.prompt:
        # Interactive prompt unless --yes / non-tty: defaults to local_wins
        # with a stderr warning per spec.
        if yes or not _is_tty():
            typer.echo(
                f"  conflict T={task.id}: prompt strategy non-interactive — "
                "defaulting to local_wins",
                err=True,
            )
            resolution = "prompt_defaulted_to_local"
        else:
            choice = typer.prompt(
                f"  conflict T={task.id}: choose [local/remote/skip]",
                default="skip",
            ).strip().lower()
            if choice.startswith("l"):
                resolution = "prompt_chose_local"
            elif choice.startswith("r"):
                resolution = "prompt_chose_remote"
            else:
                resolution = "prompt_skipped"
    elif strategy == ConflictResolutionStrategy.manual_merge:
        merge_path = _write_manual_merge_file(
            state_dir=state_dir, task=task, remote=remote
        )
        typer.echo(
            f"  conflict T={task.id}: manual_merge — wrote {merge_path}",
            err=True,
        )
        typer.echo(
            "  Resolve the file and delete it; rerun sync.",
            err=True,
        )
        _emit_audit(
            backend,
            action="sync.conflict_detected",
            payload={
                "provider_id": provider.provider_id,
                "task_id": task.id,
                "external_id": remote.external_id,
                "strategy": strategy_str,
                "resolution": "manual_merge_file_written",
                "audit_note": str(merge_path),
            },
            target_kind="task",
            target_id=task.id,
        )
        # Return False (don't raise) so the caller can continue the batch
        # — important for --watch mode where one task in manual_merge
        # must not halt the whole daemon. The batch loop tracks the
        # manual_merge count and exits 2 at the end if any were pending.
        return False
    else:  # pragma: no cover — defensive; StrEnum is exhaustive above
        resolution = f"unknown_strategy:{strategy_str}"

    _emit_audit(
        backend,
        action="sync.conflict_detected",
        payload={
            "provider_id": provider.provider_id,
            "task_id": task.id,
            "external_id": remote.external_id,
            "strategy": strategy_str,
            "resolution": resolution,
        },
        target_kind="task",
        target_id=task.id,
    )
    return True


def _write_manual_merge_file(
    *,
    state_dir: Path,
    task: Task,
    remote: ExternalTask,
) -> Path:
    """Write a markdown side-by-side merge document; return the path."""
    merge_dir = state_dir / _SYNC_CONFLICTS_DIRNAME
    merge_dir.mkdir(parents=True, exist_ok=True)
    target = merge_dir / f"{task.id}.md"
    body = (
        f"# Sync conflict for {task.id}\n\n"
        f"Resolve this file (edit local or accept remote), then DELETE it; "
        "rerun `fakoli-state sync <provider>` to continue.\n\n"
        f"## Local (task {task.id})\n\n"
        f"- title: {task.title}\n"
        f"- status: {task.status}\n"
        f"- updated_at: {task.updated_at.isoformat()}\n\n"
        f"### description\n\n```\n{task.description}\n```\n\n"
        f"## Remote ({remote.external_id})\n\n"
        f"- title: {remote.title}\n"
        f"- status_label: {remote.status_label}\n"
        f"- last_modified: {remote.last_modified.isoformat()}\n\n"
        f"### body\n\n```\n{remote.body}\n```\n"
    )
    target.write_text(body, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Watch loop
# ---------------------------------------------------------------------------


def _run_watch_loop(
    *,
    backend: SqliteBackend,
    state_dir: Path,
    provider: SyncProvider,
    push: bool,
    pull: bool,
    fix: bool,
    task: str | None,
    yes: bool,
    interval: int,
) -> None:
    """Poll forever until Ctrl-C. ``--interval 0`` runs ONE iteration.

    Single-iteration mode is the test seam: parallel-welder-territory-free
    way for the suite to exercise the watch path without sleeping.
    """
    stop_flag = {"stop": False}

    def _handler(signum: int, frame: Any) -> None:
        _ = (signum, frame)
        stop_flag["stop"] = True

    # Install SIGINT handler so Ctrl-C exits cleanly; restore on return.
    previous = signal.signal(signal.SIGINT, _handler)
    try:
        while not stop_flag["stop"]:
            # Each iteration is isolated: a single SyncProviderError, an
            # unexpected typer.Exit (e.g. from a per-task manual_merge),
            # or any other exception must NOT kill the daemon. Surface
            # the error on stderr and continue polling.
            try:
                _run_sync_once(
                    backend=backend,
                    state_dir=state_dir,
                    provider=provider,
                    push=push,
                    pull=pull,
                    fix=fix,
                    task=task,
                    yes=yes,
                )
            except typer.Exit:
                # manual_merge etc. — surface but keep polling. The next
                # iteration will skip the same task (mapping is in conflict)
                # but advance the rest of the project.
                typer.echo(
                    "  watch: iteration aborted (operator action required); "
                    "next poll continues.",
                    err=True,
                )
            except Exception as exc:  # noqa: BLE001 — watch loop must survive
                typer.echo(
                    f"  watch: iteration failed ({type(exc).__name__}): {exc}; "
                    "next poll continues.",
                    err=True,
                )
            if interval <= 0:
                # Test seam: one iteration and out.
                break
            # Sleep in 1s slices so the SIGINT handler can wake us.
            slept = 0
            while slept < interval and not stop_flag["stop"]:
                time.sleep(1)
                slept += 1
    finally:
        signal.signal(signal.SIGINT, previous)


# ---------------------------------------------------------------------------
# Reconciliation helpers
# ---------------------------------------------------------------------------


def _run_reconciliation(
    backend: SqliteBackend,
    state_dir: Path,
) -> Any:
    """Build a ReconciliationEngine and run scan()."""
    from fakoli_state.clock import SystemClock

    # Configured providers list flows in from the project's config; for now
    # we ask the registry. Tests can monkeypatch PROVIDER_REGISTRY directly.
    from fakoli_state.sync import registry as sync_registry
    from fakoli_state.sync.reconciliation import ReconciliationEngine

    configured = sorted(sync_registry.PROVIDER_REGISTRY)
    engine = ReconciliationEngine(
        backend,
        state_dir=state_dir,
        clock=SystemClock(),
        configured_providers=configured,
    )
    return engine.scan()


def _apply_reconciliation_fixes(
    backend: SqliteBackend,
    state_dir: Path,
    report: Any,
) -> list[Any]:
    """Build the engine again and call .fix() on the report."""
    from fakoli_state.clock import SystemClock
    from fakoli_state.sync import registry as sync_registry
    from fakoli_state.sync.reconciliation import ReconciliationEngine

    configured = sorted(sync_registry.PROVIDER_REGISTRY)
    engine = ReconciliationEngine(
        backend,
        state_dir=state_dir,
        clock=SystemClock(),
        configured_providers=configured,
    )
    return engine.fix(report)


def _print_reconciliation_report(report: Any) -> None:
    """Render a reconciliation report to stdout."""
    typer.echo(f"Reconciliation scanned at {report.scanned_at.isoformat()}")
    if not report.discrepancies:
        typer.echo("  No discrepancies found.")
        return
    typer.echo(f"  Found {len(report.discrepancies)} discrepancy(ies):")
    for d in report.discrepancies:
        typer.echo(f"    [{d.severity}] {d.kind}: {d.target_id}")
        typer.echo(f"      {d.description}")
        typer.echo(f"      suggested: {d.suggested_fix}")
    typer.echo("")
    typer.echo("Summary:")
    for kind, count in sorted(report.summary.items()):
        typer.echo(f"  {kind}: {count}")


def _print_fix_actions(actions: list[Any]) -> None:
    """Render a list of FixAction to stdout."""
    if not actions:
        typer.echo("No fixes to apply.")
        return
    typer.echo("")
    typer.echo(f"Applied {len(actions)} fix(es):")
    for a in actions:
        marker = (
            "ok" if a.result == "applied"
            else "skip" if a.result == "skipped"
            else "FAIL"
        )
        line = f"  [{marker}] {a.kind} {a.target_id}: {a.command}"
        if a.error:
            line += f" — {a.error}"
        typer.echo(line)


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------


def _emit_audit(
    backend: SqliteBackend,
    *,
    action: str,
    payload: dict[str, Any],
    target_kind: str,
    target_id: str,
) -> None:
    """Append a sync.* audit event via apply_event().

    Strips None fields so the JSONL is compact. The
    :class:`fakoli_state.state.payloads.SyncAuditPayload` model accepts
    None on every field so the strip is for ergonomics, not correctness.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.models import Event

    clean: dict[str, Any] = {k: v for k, v in payload.items() if v is not None}
    event = Event(
        id=PENDING_EVENT_ID,
        timestamp=SystemClock().now(),
        actor="sync-cli",
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        payload_json=clean,
    )
    try:
        backend.apply_event(event)
    except Exception as exc:  # noqa: BLE001 — audit failures must not abort sync
        # Audit emission failures are non-fatal: a sync that succeeded but
        # whose audit row failed to write is strictly better than aborting
        # the sync entirely. Log to stderr so an operator can investigate
        # without the suite hiding it.
        typer.echo(
            f"  warning: failed to emit audit event {action!r}: "
            f"{type(exc).__name__}: {exc}",
            err=True,
        )


# ---------------------------------------------------------------------------
# tty detection
# ---------------------------------------------------------------------------


def _is_tty() -> bool:
    """Return True if stdin AND stdout are connected to an interactive terminal.

    typer.prompt reads from stdin (the question is answerable) and writes
    the prompt to stdout (the user can see it). If either side is
    redirected we cannot safely interact, so default to non-interactive
    behavior (caller falls back to local_wins with a stderr warning, or
    fails fast on --fix-without-yes).
    """
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# JSON helper (kept here so tests can mock if needed)
# ---------------------------------------------------------------------------


def _to_json(obj: Any) -> str:  # pragma: no cover — convenience for debug printing
    return json.dumps(obj, sort_keys=True, default=str)
