"""init and status commands (Phase 2)."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from fakoli_state.cli._helpers import (
    _STATE_DIR_NAME,
    _is_plugin_root,
    _open_backend,
    _resolve_state_dir,
    _slug,
)

if TYPE_CHECKING:
    from fakoli_state.state.sqlite import SqliteBackend


# ---------------------------------------------------------------------------
# init subcommand
# ---------------------------------------------------------------------------


def init(
    name: str | None = typer.Option(  # noqa: B008
        None,
        "--name",
        help=(
            "Human-readable project name. "
            "Defaults to the basename of the current directory."
        ),
    ),
    id: str | None = typer.Option(  # noqa: A002,B008
        None,
        "--id",
        help=(
            "Project identifier slug (e.g. 'my-project'). "
            "Defaults to a slug derived from --name."
        ),
    ),
    force: bool = typer.Option(  # noqa: B008
        False,
        "--force",
        help="Overwrite an existing .fakoli-state/ directory.",
    ),
) -> None:
    """Scaffold a .fakoli-state/ directory in the current working directory.

    Creates the canonical project-state layout including config.yaml,
    state.db (SQLite), events.jsonl (append-only event log), and an
    empty packets/ subdirectory.
    """
    from fakoli_state.config import write_default_config

    cwd = Path.cwd().resolve()

    # Guard: refuse to initialise inside the fakoli-state plugin directory.
    if _is_plugin_root(cwd):
        typer.echo(
            "Error: this directory is the fakoli-state plugin root. "
            "Run `fakoli-state init` from your project directory, "
            "not from inside the plugin.",
            err=True,
        )
        raise typer.Exit(code=1)

    state_dir = cwd / _STATE_DIR_NAME

    # Guard: existing state directory without --force.
    if state_dir.exists() and not force:
        typer.echo(
            f"Error: {state_dir} already exists. "
            "Pass --force to reinitialise.",
            err=True,
        )
        raise typer.Exit(code=1)

    # --force reinit: wipe the canonical state files before scaffolding so the
    # replay/audit guarantee holds. Without this, the new project.created and
    # state.initialized events would be appended to the old events.jsonl,
    # producing duplicate IDs and a log that no longer replays to current DB.
    # packets/ is preserved (user-generated work packets are not canonical
    # state). snapshots/ may exist if `fakoli-state snapshot` was run; if
    # present it is also preserved for the same reason (PS-2: init no longer
    # pre-creates it).
    if state_dir.exists() and force:
        db_file = state_dir / "state.db"
        if db_file.exists():
            db_file.unlink()
        # WAL/SHM sidecar files left by SQLite must go too.
        for sidecar in ("state.db-wal", "state.db-shm"):
            sidecar_path = state_dir / sidecar
            if sidecar_path.exists():
                sidecar_path.unlink()
        events_file = state_dir / "events.jsonl"
        if events_file.exists():
            events_file.unlink()

    # Resolve project name and id.
    project_name = name if name else cwd.name
    project_id = id if id else _slug(project_name)

    # Create directory structure.
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "packets").mkdir(exist_ok=True)
    (state_dir / "events.jsonl").touch()
    # Note: snapshots/ used to be pre-created here, but nothing in the
    # codebase ever writes to it (PS-2). When `fakoli-state snapshot` ships
    # it will create the directory on first use.

    # Write config.yaml via the config module.
    # write_default_config generates a UUID for project_id internally; the --id
    # argument controls the project_id used in the state backend event below.
    config_path = state_dir / "config.yaml"
    if config_path.exists() and force:
        config_path.unlink()
    write_default_config(config_path, project_name=project_name)

    # Initialise state.db via SqliteBackend.
    backend = _open_backend(state_dir)
    try:
        _apply_init_event(backend, project_name=project_name, project_id=project_id)
    finally:
        backend.close()

    # Print confirmation.
    typer.echo(f"Initialized fakoli-state for '{project_name}' (id: {project_id})")
    typer.echo("")
    typer.echo(f"  {config_path}")
    typer.echo(f"  {state_dir / 'state.db'}")
    typer.echo(f"  {state_dir / 'events.jsonl'}")
    typer.echo(f"  {state_dir / 'packets'}/")
    typer.echo("")
    typer.echo(
        "Next step: author your PRD at "
        f"{state_dir / 'prd.md'}, "
        "then run `fakoli-state prd parse`."
    )


def _apply_init_event(
    backend: SqliteBackend,
    *,
    project_name: str,
    project_id: str,
) -> None:
    """Build and apply the project.created and state.initialized events.

    These two events seed the project row in state.db and mark the
    initialisation in the append-only audit log.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.models import EventDraft

    clock = SystemClock()
    now = clock.now()

    project_draft = EventDraft(
        timestamp=now,
        actor="fakoli-state-cli",
        action="project.created",
        target_kind="project",
        target_id=project_id,
        payload_json={
            "id": project_id,
            "name": project_name,
            "description": "",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    )
    backend.append(project_draft)

    init_draft = EventDraft(
        timestamp=now,
        actor="fakoli-state-cli",
        action="state.initialized",
        target_kind="project",
        target_id=project_id,
        payload_json={},
    )
    backend.append(init_draft)


# ---------------------------------------------------------------------------
# status subcommand
# ---------------------------------------------------------------------------


def status(
    hook_format: bool = typer.Option(  # noqa: B008
        False,
        "--hook-format",
        help=(
            "Print a single compact line for SessionStart hook consumption. "
            "Exits 0 even when fakoli-state is not initialized "
            "(hooks must never fail the session)."
        ),
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help=(
            "Project directory to inspect. "
            "Defaults to the current working directory."
        ),
    ),
) -> None:
    """Show the current fakoli-state summary for this project.

    Default output is a human-readable multi-line summary.
    Pass --hook-format for the single-line compact format consumed by
    the SessionStart detect-state.sh hook.
    """
    state_dir = _resolve_state_dir(cwd)

    if not state_dir.exists():
        if hook_format:
            typer.echo("uninitialized")
            raise typer.Exit(code=0)
        typer.echo(
            "fakoli-state not initialized in this project. "
            "Run `fakoli-state init` to start."
        )
        raise typer.Exit(code=1)

    backend = _open_backend(state_dir)
    try:
        project = backend.get_project()
        prd = backend.get_prd()
        all_tasks = backend.list_tasks()
        active_claims = backend.list_active_claims()
    finally:
        backend.close()

    # Aggregate task counts.
    ready_count = sum(1 for t in all_tasks if t.status == "ready")
    in_progress_count = sum(1 for t in all_tasks if t.status == "in_progress")
    blocked_count = sum(1 for t in all_tasks if t.status == "blocked")

    prd_status_str = str(prd.status) if prd is not None else "none"
    active_claim_count = len(active_claims)

    if hook_format:
        line = (
            f"active-claims:{active_claim_count} "
            f"ready-tasks:{ready_count} "
            f"blockers:{blocked_count} "
            f"prd-status:{prd_status_str}"
        )
        typer.echo(line)
        raise typer.Exit(code=0)

    # Human-readable multi-line output.
    project_name = project.name if project is not None else "(unknown)"
    project_id_str = project.id if project is not None else "(unknown)"
    config_path = state_dir / "config.yaml"

    # Try to read project metadata from config if backend has no project row.
    if project is None and config_path.exists():
        try:
            from fakoli_state.config import load_config

            cfg = load_config(config_path)
            project_name = cfg.project_name
            project_id_str = cfg.project_id
        except Exception:  # noqa: BLE001  (config errors must not crash status)
            pass

    # Determine initialized-at timestamp from the first events.jsonl entry.
    initialized_at = _read_initialized_at(state_dir)

    sync_label = "off"
    if config_path.exists():
        try:
            from fakoli_state.config import load_config

            cfg = load_config(config_path)
            if cfg.sync_github_enabled:
                sync_label = "github"
        except Exception:  # noqa: BLE001
            pass

    typer.echo(f'fakoli-state for "{project_name}" (id: {project_id_str})')
    typer.echo(f"Path: {state_dir}")
    typer.echo(f"Initialized: {initialized_at}")
    typer.echo("")
    typer.echo(f"PRD:           {prd_status_str}")
    typer.echo(
        f"Tasks:         {len(all_tasks)} total "
        f"({ready_count} ready, "
        f"{in_progress_count} in_progress, "
        f"{blocked_count} blocked)"
    )
    typer.echo(f"Active claims: {active_claim_count}")
    typer.echo(f"Sync:          {sync_label}")


def _read_initialized_at(state_dir: Path) -> str:
    """Return the ISO timestamp from the first events.jsonl entry.

    Falls back to the mtime of state.db, then to 'unknown'.
    """
    events_path = state_dir / "events.jsonl"
    if events_path.exists():
        try:
            with events_path.open(encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    ts = data.get("timestamp", "")
                    if ts:
                        return str(ts)
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    db_path = state_dir / "state.db"
    if db_path.exists():
        try:
            mtime = db_path.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC)
            return dt.isoformat()
        except OSError:
            pass

    return "unknown"
