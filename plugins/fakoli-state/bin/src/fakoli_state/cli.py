"""fakoli-state CLI — pure state operations for humans, agents, and external tools.

Planned command set (Phases 2-8):

  init                  Scaffold .fakoli-state/ in cwd (Phase 2)
  status                Active claims, blockers, sync state (Phase 2)
  prd parse             Re-parse prd.md into state (Phase 3)
  prd review            Transition PRD draft → reviewed → approved (Phase 3)
  plan                  Generate features + tasks from parsed requirements (Phase 3)
  score [TASK_ID]       Populate six-dimension scores; --use-llm to augment (Phase 3)
  expand TASK_ID        Break a complex task into subtasks (Phase 3)
  review tasks          Promote drafted → reviewed → ready (Phase 3)
  list [--status X]     List tasks filtered by status (Phase 3)
  show TASK_ID          Show task detail (Phase 3)
  next                  Pick the highest-priority claimable task (Phase 4)
  claim TASK_ID         Acquire an exclusive lease; auto-creates branch (Phase 4)
  release TASK_ID       Release a claim (Phase 4)
  renew TASK_ID         Extend a lease heartbeat (Phase 4)
  packet TASK_ID        Render a work packet (md or json) (Phase 5)
  submit TASK_ID        Record completion evidence (Phase 5)
  apply TASK_ID         Human review → accepted → done (Phase 5)
  conflicts             Show conflict groups and overlapping claims (Phase 5)
  sync [github]         Bidirectional GitHub Issues sync (Phase 8)
  replay                Reconstruct SQLite from events.jsonl audit log (Phase 8)

All mutating commands accept --dry-run and --verbose global flags (Phase 2+).
"""

from __future__ import annotations

import datetime
import json
import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from fakoli_state import __version__

if TYPE_CHECKING:
    from fakoli_state.state.models import Evidence, Task
    from fakoli_state.state.sqlite import SqliteBackend

app = typer.Typer(
    name="fakoli-state",
    help=(
        "Local-first project state engine: turn brainstorms and PRDs into reviewed, "
        "lockable, evidence-backed work packets that humans and AI agents can "
        "coordinate on without conflicts."
    ),
    no_args_is_help=True,
)

# Sub-app for `prd` subcommands.
prd_app = typer.Typer(
    name="prd",
    help="PRD lifecycle commands: parse, review, approve.",
    no_args_is_help=True,
)
app.add_typer(prd_app, name="prd")

# Sub-app for `review` subcommands.
review_app = typer.Typer(
    name="review",
    help="Review lifecycle commands: tasks.",
    no_args_is_help=True,
)
app.add_typer(review_app, name="review")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATE_DIR_NAME = ".fakoli-state"
_PLUGIN_MANIFEST = ".claude-plugin/plugin.json"
_PRD_FILENAME = "prd.md"


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _resolve_state_dir(cwd: Path | None) -> Path:
    """Return the absolute path to the .fakoli-state/ directory.

    Args:
        cwd: Working directory to use. Falls back to Path.cwd() when None.

    Returns:
        Absolute Path pointing at <cwd>/.fakoli-state/.
    """
    base = cwd.resolve() if cwd is not None else Path.cwd().resolve()
    return base / _STATE_DIR_NAME


def _open_backend(state_dir: Path) -> SqliteBackend:
    """Instantiate a SqliteBackend, call initialize(), and return it.

    The caller is responsible for calling .close() when done — use a try/finally.

    Args:
        state_dir: Absolute path to the .fakoli-state/ directory.

    Returns:
        An initialized SqliteBackend ready for queries and mutations.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.sqlite import SqliteBackend as _SqliteBackend

    db_path = str(state_dir / "state.db")
    events_path = str(state_dir / "events.jsonl")
    backend = _SqliteBackend(
        db_path=db_path,
        events_path=events_path,
        clock=SystemClock(),
    )
    backend.initialize()
    return backend


def _slug(text: str) -> str:
    """Convert a human-readable name to a URL-safe lowercase slug.

    Example: "My Project" → "my-project"
    """
    lowered = text.lower()
    stripped = re.sub(r"[^a-z0-9]+", "-", lowered)
    return stripped.strip("-") or "project"


def _is_plugin_root(directory: Path) -> bool:
    """Return True if *directory* is the fakoli-state plugin root.

    Detects the plugin root by checking for a .claude-plugin/plugin.json that
    declares name == "fakoli-state".  This prevents accidental initialisation
    inside the plugin directory itself.
    """
    manifest = directory / _PLUGIN_MANIFEST
    if not manifest.exists():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return bool(data.get("name") == "fakoli-state")
    except (json.JSONDecodeError, OSError):
        return False


def _require_state_dir(state_dir: Path) -> None:
    """Exit 1 with a helpful message if the state directory does not exist."""
    if not state_dir.exists():
        typer.echo(
            "Error: fakoli-state not initialized in this project. "
            "Run `fakoli-state init` first.",
            err=True,
        )
        raise typer.Exit(code=1)


def _next_event_id(backend: SqliteBackend) -> str:
    """Thin shim that delegates to backend.next_event_id().

    Kept as a module-level function so existing callers don't need to
    change. The backend method is the single source of truth (Greptile +
    critic PR #39 finding: two parallel generators produced incompatible
    ID formats once both landed in the same events table).
    """
    return backend.next_event_id()


def _get_project_id(backend: SqliteBackend) -> str:
    """Return the project ID from the backend, or 'project' as a fallback."""
    project = backend.get_project()
    if project is not None:
        return project.id
    return "project"


# ---------------------------------------------------------------------------
# --version callback (unchanged from Phase 1)
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(  # noqa: B008
        False,
        "--version",
        "-V",
        help="Print the version and exit.",
        is_eager=True,
    ),
) -> None:
    """fakoli-state — local-first project state engine."""
    if version:
        typer.echo(f"fakoli-state {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# init subcommand
# ---------------------------------------------------------------------------


@app.command()
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
    state.db (SQLite), events.jsonl (append-only event log), and
    empty packets/ and snapshots/ subdirectories.
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
    # packets/ and snapshots/ are preserved (user data; --force is for the
    # canonical state, not for nuking work).
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
    (state_dir / "snapshots").mkdir(exist_ok=True)
    (state_dir / "events.jsonl").touch()

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
    typer.echo(f"  {state_dir / 'snapshots'}/")
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
    from fakoli_state.state.models import Event

    clock = SystemClock()
    now = clock.now()

    project_event = Event(
        id="E000001",
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
    backend.apply_event(project_event)

    init_event = Event(
        id="E000002",
        timestamp=now,
        actor="fakoli-state-cli",
        action="state.initialized",
        target_kind="project",
        target_id=project_id,
        payload_json={},
    )
    backend.apply_event(init_event)


# ---------------------------------------------------------------------------
# status subcommand
# ---------------------------------------------------------------------------


@app.command()
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
    stale_count = sum(1 for t in all_tasks if t.status == "stale")

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
        f"{blocked_count} blocked, "
        f"{stale_count} stale)"
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


# ---------------------------------------------------------------------------
# prd subcommands
# ---------------------------------------------------------------------------


@prd_app.command("parse")
def prd_parse(
    file: Path | None = typer.Option(  # noqa: B008
        None,
        "--file",
        help=(
            "Path to the PRD markdown file. "
            "Defaults to .fakoli-state/prd.md in the current directory."
        ),
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Parse prd.md and store the result as a prd.parsed event.

    Reads .fakoli-state/prd.md (or --file PATH), calls the template parser,
    emits a prd.parsed event with the full PRD + requirements payload.

    Exits 1 if there are parse errors or the file cannot be read.
    On success, prints a summary of what was parsed.
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.planning.template import parse_prd
    from fakoli_state.state.models import Event

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    prd_path = file if file is not None else state_dir / _PRD_FILENAME
    if not prd_path.exists():
        typer.echo(
            f"Error: PRD file not found at {prd_path}. "
            "Author your PRD there or pass --file PATH.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        markdown = prd_path.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: cannot read {prd_path}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    result = parse_prd(markdown, prd_id="prd")

    if result.errors:
        for err in result.errors:
            typer.echo(
                f"  Parse error [{err.section}:{err.line}]: {err.message}",
                err=True,
            )
        typer.echo(
            f"Error: PRD parse failed with {len(result.errors)} error(s). "
            "Fix the issues above and re-run.",
            err=True,
        )
        raise typer.Exit(code=1)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()
        now = clock.now()
        project_id = _get_project_id(backend)
        event_id = _next_event_id(backend)

        payload: dict[str, object] = {
            "project_id": project_id,
            "status": result.prd.status.value,
            "summary": result.prd.summary,
            "goals": result.prd.goals,
            "non_goals": result.prd.non_goals,
            "requirements": [
                {
                    "id": r.id,
                    "prd_section": r.prd_section,
                    "text": r.text,
                    "source_paragraph": r.source_paragraph,
                    "derived": r.derived,
                }
                for r in result.requirements
            ],
            "acceptance_criteria": result.prd.acceptance_criteria,
            "risks": result.prd.risks,
            "open_questions": result.prd.open_questions,
        }

        event = Event(
            id=event_id,
            timestamp=now,
            actor="fakoli-state-cli",
            action="prd.parsed",
            target_kind="prd",
            target_id=project_id,
            payload_json=payload,
        )
        backend.apply_event(event)
    finally:
        backend.close()

    typer.echo(
        f"Parsed {len(result.requirements)} requirements, "
        f"{len(result.features)} features, "
        f"{len(result.tasks)} tasks."
    )
    typer.echo(f"PRD source: {prd_path}")


@prd_app.command("review")
def prd_review(
    approve: bool = typer.Option(  # noqa: B008
        False,
        "--approve",
        help="Approve the PRD (reviewed → approved). Without this flag: draft → reviewed.",
    ),
    reviewer: str = typer.Option(  # noqa: B008
        "human",
        "--reviewer",
        help="Identity of the reviewer.",
    ),
    notes: str | None = typer.Option(  # noqa: B008
        None,
        "--notes",
        help="Optional review notes.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Transition the PRD through the review lifecycle.

    Without --approve: draft → reviewed (emits prd.reviewed event).
    With --approve:    reviewed → approved (emits prd.approved event).
    """
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.models import Event

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()
        now = clock.now()
        project_id = _get_project_id(backend)

        prd = backend.get_prd()
        if prd is None:
            typer.echo(
                "Error: no PRD found in state. Run `fakoli-state prd parse` first.",
                err=True,
            )
            raise typer.Exit(code=1)

        event_id = _next_event_id(backend)

        if approve:
            if prd.status.value != "reviewed":
                typer.echo(
                    f"Error: PRD must be in 'reviewed' status to approve, "
                    f"got '{prd.status.value}'. "
                    "Run `fakoli-state prd review` first.",
                    err=True,
                )
                raise typer.Exit(code=1)

            event = Event(
                id=event_id,
                timestamp=now,
                actor="fakoli-state-cli",
                action="prd.approved",
                target_kind="prd",
                target_id=project_id,
                payload_json={"project_id": project_id, "approver": reviewer},
            )
            backend.apply_event(event)
            typer.echo(f"PRD approved by '{reviewer}'.")
        else:
            if prd.status.value != "draft":
                typer.echo(
                    f"Error: PRD must be in 'draft' status to review, "
                    f"got '{prd.status.value}'. "
                    "Pass --approve to move from reviewed → approved.",
                    err=True,
                )
                raise typer.Exit(code=1)

            event = Event(
                id=event_id,
                timestamp=now,
                actor="fakoli-state-cli",
                action="prd.reviewed",
                target_kind="prd",
                target_id=project_id,
                payload_json={"project_id": project_id, "reviewer": reviewer, "notes": notes},
            )
            backend.apply_event(event)
            typer.echo(f"PRD reviewed by '{reviewer}'.")
            typer.echo("Run `fakoli-state prd review --approve` to approve.")
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# plan subcommand
# ---------------------------------------------------------------------------


@app.command()
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
            event_id = _next_event_id(backend)
            now = clock.now()
            feature_data = feature.model_dump(mode="json")
            event = Event(
                id=event_id,
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
            event_id = _next_event_id(backend)
            now = clock.now()
            task_data = task.model_dump(mode="json")
            event = Event(
                id=event_id,
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
            event_id = _next_event_id(backend)
            now = clock.now()
            # Upsert with full updated fields.
            task_data = inferred_task.model_dump(mode="json")
            upsert_event = Event(
                id=event_id,
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
                event_id = _next_event_id(backend)
                now = clock.now()
                status_event = Event(
                    id=event_id,
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


@app.command()
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
            event_id = _next_event_id(backend)

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
                id=event_id,
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


def _scores_complete(task: Task) -> bool:
    """Return True if all six score dimensions are populated."""
    s = task.scores
    return all(
        v is not None
        for v in (
            s.complexity,
            s.parallelizability,
            s.context_load,
            s.blast_radius,
            s.review_risk,
            s.agent_suitability,
        )
    )


# ---------------------------------------------------------------------------
# expand subcommand
# ---------------------------------------------------------------------------


@app.command()
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

            event_id = _next_event_id(backend)
            event = Event(
                id=event_id,
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

            event_id = _next_event_id(backend)
            event = Event(
                id=event_id,
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


@app.command("list")
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


@app.command()
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

        # Fetch recent events for this task from the events table.
        recent_events = _fetch_recent_events(backend, task.id, limit=10)
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


def _fetch_recent_events(
    backend: SqliteBackend,
    task_id: str,
    *,
    limit: int = 10,
) -> list[tuple[str, str]]:
    """Return the most recent events for a given task_id.

    Queries the events mirror table directly for speed.

    Args:
        backend: An initialised SqliteBackend.
        task_id: The task ID to filter events by.
        limit:   Maximum number of events to return.

    Returns:
        List of (action, timestamp) tuples, most recent first.
    """
    conn = backend._conn  # noqa: SLF001
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT action, timestamp
              FROM events
             WHERE target_id = ?
               AND target_kind = 'task'
             ORDER BY timestamp DESC
             LIMIT ?
            """,
            (task_id, limit),
        ).fetchall()
        return [(row[0], row[1]) for row in rows]
    except sqlite3.OperationalError:
        return []


# ---------------------------------------------------------------------------
# Stale-claim reaper helper (shared by all mutating commands)
# ---------------------------------------------------------------------------


def _reap_stale_claims(backend: SqliteBackend) -> None:
    """Run the stale-claim detector against *backend*.

    Called at the start of claim/release/renew/next so users always see
    consistent state without having to think about expiry.  Failures are
    swallowed — reaping is best-effort; a stale claim that slips through will
    be caught on the next invocation.
    """
    try:
        from fakoli_state.claims.stale import detect_and_release_stale
        from fakoli_state.clock import SystemClock

        detect_and_release_stale(backend, SystemClock())
    except Exception:  # noqa: BLE001
        pass  # best-effort; never block the primary command


# ---------------------------------------------------------------------------
# claim subcommand
# ---------------------------------------------------------------------------


@app.command()
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
        help="Override conflict warnings.",
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

        try:
            result = manager.claim(task_id, expected_files=expected_files, force=force)
        except ClaimError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        # Git branch creation — non-blocking; warnings go to stderr.
        branch_result = create_branch_for_task(
            task_id,
            task.title,
            cwd=resolved_cwd,
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


@app.command()
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


@app.command()
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


@app.command()
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


# ---------------------------------------------------------------------------
# packet subcommand
# ---------------------------------------------------------------------------


@app.command()
def packet(
    task_id: str = typer.Argument(..., help="Task ID to render a work packet for (e.g. T001)."),  # noqa: B008
    fmt: str = typer.Option(  # noqa: B008
        "md",
        "--format",
        "-f",
        help="Output format: md (default) or json.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Render a work packet for TASK_ID and write it to .fakoli-state/packets/."""
    from fakoli_state.context.packets import render_packet

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        _reap_stale_claims(backend)

        # Fetch the task.
        task = backend.get_task(task_id)
        if task is None:
            typer.echo(f"Error: task '{task_id}' not found.", err=True)
            raise typer.Exit(code=1)

        # Fetch the parent feature via a direct SQL query (sqlite backend
        # exposes no public get_feature(); _conn access mirrors _fetch_recent_events).
        feature = None
        conn = backend._conn  # noqa: SLF001
        if conn is not None:
            try:
                row = conn.execute(
                    "SELECT id, title, description, status, requirements, tasks "
                    "FROM features WHERE id = ?",
                    (task.feature_id,),
                ).fetchone()
                if row is not None:
                    from fakoli_state.state.models import Feature, FeatureStatus

                    feature = Feature(
                        id=row[0],
                        title=row[1],
                        description=row[2],
                        status=FeatureStatus(row[3]),
                        requirements=json.loads(row[4] or "[]"),
                        tasks=json.loads(row[5] or "[]"),
                    )
            except Exception:  # noqa: BLE001
                pass  # feature is optional; render_packet handles None

        # Split dependencies into completed and open.
        dependencies_completed: list[Task] = []
        dependencies_open: list[Task] = []
        if task.dependencies:
            dep_tasks = [backend.get_task(dep_id) for dep_id in task.dependencies]
            for dep in dep_tasks:
                if dep is None:
                    continue
                if dep.status.value == "done":
                    dependencies_completed.append(dep)
                else:
                    dependencies_open.append(dep)

        # Fetch the active claim for this task, if any.
        active_claim = None
        for claim in backend.list_active_claims():
            if claim.task_id == task_id:
                active_claim = claim
                break

        work_packet = render_packet(
            task,
            feature=feature,
            dependencies_completed=dependencies_completed,
            dependencies_open=dependencies_open,
            related_decisions=None,  # Phase 6+ wiring
            active_claim=active_claim,
        )
    finally:
        backend.close()

    # Determine output path and content.
    packets_dir = state_dir / "packets"
    packets_dir.mkdir(exist_ok=True)

    if fmt == "json":
        out_path = packets_dir / f"{task_id}.json"
        content = json.dumps(work_packet.json_data, indent=2)
    else:
        out_path = packets_dir / f"{task_id}.md"
        content = work_packet.markdown

    out_path.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote packet to {out_path}")
    typer.echo("")
    typer.echo(work_packet.markdown)


# ---------------------------------------------------------------------------
# submit subcommand
# ---------------------------------------------------------------------------


@app.command()
def submit(
    task_id: str = typer.Argument(..., help="Task ID to submit evidence for (e.g. T001)."),  # noqa: B008
    commands: str = typer.Option(  # noqa: B008
        ...,
        "--commands",
        help="Comma-separated verification commands that were run.",
    ),
    files_changed: str = typer.Option(  # noqa: B008
        ...,
        "--files-changed",
        help="Comma-separated file paths modified.",
    ),
    output_file: Path | None = typer.Option(  # noqa: B008
        None,
        "--output-file",
        help="Path to a file whose content will be used as the output excerpt.",
    ),
    pr_url: str | None = typer.Option(  # noqa: B008
        None,
        "--pr-url",
        help="Pull request URL.",
    ),
    commit_sha: str | None = typer.Option(  # noqa: B008
        None,
        "--commit-sha",
        help="Commit SHA associated with this submission.",
    ),
    known_limitations: str | None = typer.Option(  # noqa: B008
        None,
        "--known-limitations",
        help="Known limitations or caveats.",
    ),
    actor: str | None = typer.Option(  # noqa: B008
        None,
        "--actor",
        help="Actor submitting evidence; defaults to $USER or 'agent'.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Record completion evidence for TASK_ID; auto-releases the active claim."""
    import os
    import uuid

    from fakoli_state.clock import SystemClock
    from fakoli_state.state.models import Event

    resolved_actor = actor or os.environ.get("USER") or "agent"
    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    backend = _open_backend(state_dir)
    try:
        clock = SystemClock()
        _reap_stale_claims(backend)

        # Locate the active claim for this task.
        active_claims = backend.list_active_claims()
        task_claim = None
        for c in active_claims:
            if c.task_id == task_id:
                task_claim = c
                break

        if task_claim is None:
            typer.echo(
                f"Error: no active claim found for task '{task_id}'. "
                "Run `fakoli-state claim {task_id}` first.".format(task_id=task_id),
                err=True,
            )
            raise typer.Exit(code=1)

        # Parse comma-separated arguments.
        commands_list = [c.strip() for c in commands.split(",") if c.strip()]
        files_list = [f.strip() for f in files_changed.split(",") if f.strip()]

        # Read and truncate output file content if provided.
        output_excerpt: str | None = None
        if output_file is not None:
            try:
                raw = output_file.read_text(encoding="utf-8", errors="replace")
                output_excerpt = raw[:8000]
            except OSError as exc:
                typer.echo(
                    f"Warning: cannot read --output-file {output_file}: {exc}",
                    err=True,
                )

        # Build a unique evidence ID with "EV" prefix (mirrors ClaimManager UUID pattern).
        evidence_id = "EV" + uuid.uuid4().hex[:8].upper()

        now = clock.now()
        event_id = _next_event_id(backend)

        payload: dict[str, object] = {
            "task_id": task_id,
            "claim_id": task_claim.id,
            "submitted_by": resolved_actor,
            "evidence_id": evidence_id,
            "commands_run": commands_list,
            "files_changed": files_list,
            "output_excerpt": output_excerpt,
            "pr_url": pr_url,
            "commit_sha": commit_sha,
            "screenshots": [],
            "known_limitations": known_limitations,
        }

        event = Event(
            id=event_id,
            timestamp=now,
            actor=resolved_actor,
            action="evidence.submitted",
            target_kind="task",
            target_id=task_id,
            payload_json=payload,
        )
        backend.apply_event(event)

        # Fetch the fresh task state and evidence for gates summary.
        fresh_task = backend.get_task(task_id)
    finally:
        backend.close()

    typer.echo(f"Evidence submitted for task '{task_id}'.")
    typer.echo(f"  Evidence ID:  {evidence_id}")
    typer.echo(f"  Claim ID:     {task_claim.id} (auto-released)")
    typer.echo(f"  Submitted by: {resolved_actor}")
    typer.echo(f"  Commands:     {commands_list}")
    typer.echo(f"  Files:        {files_list}")
    if pr_url:
        typer.echo(f"  PR URL:       {pr_url}")
    if commit_sha:
        typer.echo(f"  Commit SHA:   {commit_sha}")
    typer.echo("")
    typer.echo(f"Task '{task_id}' status → needs_review.")
    typer.echo(f"Run `fakoli-state apply {task_id}` when ready for human review.")

    # Gate summary: build a minimal Evidence object for evidence_complete check.
    if fresh_task is not None:
        try:

            from fakoli_state.review.gates import evidence_complete
            from fakoli_state.state.models import Evidence

            evidence_obj = Evidence(
                id=evidence_id,
                task_id=task_id,
                claim_id=task_claim.id,
                commands_run=commands_list,
                output_excerpt=output_excerpt,
                files_changed=files_list,
                pr_url=pr_url,
                commit_sha=commit_sha,
                screenshots=[],
                known_limitations=known_limitations,
                submitted_at=now,
                submitted_by=resolved_actor,
            )
            passed, missing = evidence_complete(fresh_task, evidence_obj)
            if passed:
                typer.echo("Evidence gate: PASSED — all required evidence present.")
            else:
                typer.echo(
                    "Evidence gate: INCOMPLETE — missing items for required_evidence:"
                )
                for item in missing:
                    typer.echo(f"  - {item}")
        except Exception:  # noqa: BLE001
            pass  # gate summary is informational; never block the command


# ---------------------------------------------------------------------------
# apply subcommand
# ---------------------------------------------------------------------------


@app.command()
def apply(
    task_id: str = typer.Argument(..., help="Task ID to apply a review decision to (e.g. T001)."),  # noqa: B008
    approve: bool = typer.Option(  # noqa: B008
        False,
        "--approve",
        help="Approve: transition needs_review → accepted → done.",
    ),
    reject: bool = typer.Option(  # noqa: B008
        False,
        "--reject",
        help="Reject: transition needs_review → rejected.",
    ),
    reason: str | None = typer.Option(  # noqa: B008
        None,
        "--reason",
        help="Review notes; required when using --reject.",
    ),
    reviewer: str | None = typer.Option(  # noqa: B008
        None,
        "--reviewer",
        help="Reviewer identity; defaults to $USER or 'human'.",
    ),
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Human review gate: transition needs_review → accepted (→ done) or → rejected."""
    import os

    state_dir = _resolve_state_dir(cwd)
    _require_state_dir(state_dir)

    resolved_reviewer = reviewer or os.environ.get("USER") or "human"

    backend = _open_backend(state_dir)
    try:
        _reap_stale_claims(backend)

        task = backend.get_task(task_id)
        if task is None:
            typer.echo(f"Error: task '{task_id}' not found.", err=True)
            raise typer.Exit(code=1)

        if task.status.value != "needs_review":
            typer.echo(
                f"Error: task '{task_id}' has status '{task.status.value}', "
                "expected 'needs_review'. "
                "Run `fakoli-state submit` first to record completion evidence.",
                err=True,
            )
            raise typer.Exit(code=1)

        # Review-only mode: neither --approve nor --reject; show evidence summary.
        if not approve and not reject:
            # Fetch the latest evidence row for this task directly.
            evidence_obj = _fetch_latest_evidence(backend, task_id)
            if evidence_obj is not None:
                try:
                    from fakoli_state.review.gates import evidence_complete

                    passed, missing = evidence_complete(task, evidence_obj)
                    typer.echo(f"Task '{task_id}' awaiting review (status: needs_review).")
                    typer.echo("")
                    if passed:
                        typer.echo("Evidence gate: PASSED — all required evidence present.")
                    else:
                        typer.echo(
                            "Evidence gate: INCOMPLETE — missing items for required_evidence:"
                        )
                        for item in missing:
                            typer.echo(f"  - {item}")
                except Exception:  # noqa: BLE001
                    typer.echo(f"Task '{task_id}' awaiting review (status: needs_review).")
            else:
                typer.echo(f"Task '{task_id}' awaiting review (status: needs_review).")
                typer.echo("No evidence found — run `fakoli-state submit` first.")
            typer.echo("")
            typer.echo(
                "Pass --approve to accept or --reject --reason TEXT to reject."
            )
            raise typer.Exit(code=0)

        # Mutual exclusion guard.
        if approve and reject:
            typer.echo(
                "Error: pass either --approve or --reject, not both.",
                err=True,
            )
            raise typer.Exit(code=1)

        # --reject requires --reason.
        if reject and not reason:
            typer.echo(
                "Error: --reject requires --reason TEXT.",
                err=True,
            )
            raise typer.Exit(code=1)

        from fakoli_state.clock import SystemClock
        from fakoli_state.state.models import Event

        clock = SystemClock()
        now = clock.now()
        event_id = _next_event_id(backend)

        if approve:
            decision = "accepted"
        else:
            decision = "rejected"

        payload: dict[str, object] = {
            "task_id": task_id,
            "reviewer": resolved_reviewer,
            "decision": decision,
            "notes": reason,
        }

        event = Event(
            id=event_id,
            timestamp=now,
            actor=resolved_reviewer,
            action="task.applied",
            target_kind="task",
            target_id=task_id,
            payload_json=payload,
        )
        backend.apply_event(event)
    finally:
        backend.close()

    if approve:
        typer.echo(f"Task '{task_id}' approved by '{resolved_reviewer}' → done.")
    else:
        typer.echo(
            f"Task '{task_id}' rejected by '{resolved_reviewer}' → rejected."
        )
        if reason:
            typer.echo(f"  Reason: {reason}")


def _fetch_latest_evidence(
    backend: SqliteBackend,
    task_id: str,
) -> Evidence | None:
    """Return the most recently submitted Evidence for task_id, or None.

    Queries the evidence table directly via the backend's internal connection.
    This mirrors the _fetch_recent_events pattern (both access backend._conn
    because the Backend protocol does not expose evidence read methods yet).

    Args:
        backend: An initialised SqliteBackend.
        task_id: The task ID to fetch evidence for.

    Returns:
        The most recent Evidence model, or None if no evidence exists.
    """
    conn = backend._conn  # noqa: SLF001
    if conn is None:
        return None
    try:
        row = conn.execute(
            """
            SELECT id, task_id, claim_id, commands_run, output_excerpt,
                   files_changed, pr_url, commit_sha, screenshots,
                   known_limitations, submitted_at, submitted_by
              FROM evidence
             WHERE task_id = ?
             ORDER BY submitted_at DESC
             LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None

        import datetime

        from fakoli_state.state.models import Evidence

        return Evidence(
            id=row[0],
            task_id=row[1],
            claim_id=row[2],
            commands_run=json.loads(row[3] or "[]"),
            output_excerpt=row[4],
            files_changed=json.loads(row[5] or "[]"),
            pr_url=row[6],
            commit_sha=row[7],
            screenshots=json.loads(row[8] or "[]"),
            known_limitations=row[9],
            submitted_at=datetime.datetime.fromisoformat(row[10]).replace(
                tzinfo=datetime.UTC
            ) if not datetime.datetime.fromisoformat(row[10]).tzinfo else
            datetime.datetime.fromisoformat(row[10]),
            submitted_by=row[11],
        )
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# hook sub-app — internal helpers invoked by the plugin's bash hooks
# ---------------------------------------------------------------------------

hook_app = typer.Typer(
    name="hook",
    help="Internal hook helpers — invoked by the plugin's bash hooks.",
    no_args_is_help=True,
)
app.add_typer(hook_app, name="hook")


@hook_app.command("check-claim")
def hook_check_claim(
    file: str = typer.Option(..., "--file", help="Path of the file about to be modified."),  # noqa: B008,A002
    actor: str = typer.Option(..., "--actor", help="Session actor / session_id."),  # noqa: B008
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Used by hooks/check-claim.sh — exit 0 always; output goes to stderr.

    Checks whether FILE is within the scope of an active claim.
    - If FILE is in expected_files of a claim by THIS actor: silent exit 0.
    - If FILE is in expected_files of a claim by ANOTHER actor: warn to stderr.
    - If no active claims exist: silent exit 0.
    """
    # Defer all imports inside the body — this hook fires on every file edit,
    # so startup latency is the primary concern.
    try:
        from fakoli_state.clock import SystemClock as _SystemClock
        from fakoli_state.state.sqlite import SqliteBackend as _SqliteBackend

        state_dir = _resolve_state_dir(cwd)
        if not state_dir.exists():
            raise typer.Exit(code=0)

        db_path = str(state_dir / "state.db")
        events_path = str(state_dir / "events.jsonl")
        backend = _SqliteBackend(
            db_path=db_path,
            events_path=events_path,
            clock=_SystemClock(),
        )
        backend.initialize()
        try:
            active_claims = backend.list_active_claims()
        finally:
            backend.close()

        if not active_claims:
            raise typer.Exit(code=0)

        normalized = file.lstrip("./")
        for active_claim in active_claims:
            # Normalize expected_files the same way for comparison.
            claim_files = {f.lstrip("./") for f in active_claim.expected_files}
            if normalized in claim_files or file in claim_files:
                if active_claim.claimed_by != actor:
                    typer.echo(
                        f"[fakoli-state:check-claim] WARNING: file '{file}' is "
                        f"in the scope of claim '{active_claim.id}' owned by "
                        f"'{active_claim.claimed_by}', not '{actor}'.",
                        err=True,
                    )
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        pass  # hook must never block the tool
    raise typer.Exit(code=0)


@hook_app.command("record-file-change")
def hook_record_file_change(
    file: str = typer.Option(..., "--file", help="Path of the file that was modified."),  # noqa: B008,A002
    tool: str = typer.Option(..., "--tool", help="Tool name (Edit, Write, NotebookEdit)."),  # noqa: B008
    actor: str = typer.Option(..., "--actor", help="Session actor / session_id."),  # noqa: B008
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Used by hooks/record-file-change.sh — appends a file_changed event.

    Writes a file_changed event to both the SQLite events table and events.jsonl.
    Exits 0 always; any failure is silently swallowed so the hook never blocks
    the tool that triggered it.
    """
    # Defer all imports — this hook fires on every file write; keep startup fast.
    try:
        from fakoli_state.clock import SystemClock as _SystemClock
        from fakoli_state.state.models import Event as _Event
        from fakoli_state.state.sqlite import SqliteBackend as _SqliteBackend

        state_dir = _resolve_state_dir(cwd)
        if not state_dir.exists():
            raise typer.Exit(code=0)

        db_path = str(state_dir / "state.db")
        events_path = str(state_dir / "events.jsonl")
        clock = _SystemClock()
        backend = _SqliteBackend(
            db_path=db_path,
            events_path=events_path,
            clock=clock,
        )
        backend.initialize()
        try:
            now = clock.now()
            event_id = _next_event_id(backend)
            event = _Event(
                id=event_id,
                timestamp=now,
                actor=actor or "hook",
                action="file_changed",
                target_kind="file",
                target_id=file,
                payload_json={
                    "file": file,
                    "tool": tool,
                    "actor": actor,
                    "changed_at": now.isoformat(),
                },
            )
            backend.apply_event(event)
        finally:
            backend.close()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        pass  # hook must never block the tool
    raise typer.Exit(code=0)


@hook_app.command("capture-evidence")
def hook_capture_evidence(
    command: str = typer.Option(..., "--command", help="Full bash command string that was run."),  # noqa: B008
    exit_code: int = typer.Option(..., "--exit-code", help="Exit code of the command."),  # noqa: B008
    stdout_file: Path | None = typer.Option(  # noqa: B008
        None,
        "--stdout-file",
        help="Path to a temp file containing the command's stdout.",
    ),
    stderr_file: Path | None = typer.Option(  # noqa: B008
        None,
        "--stderr-file",
        help="Path to a temp file containing the command's stderr.",
    ),
    actor: str = typer.Option(..., "--actor", help="Session actor / session_id."),  # noqa: B008
    cwd: Path | None = typer.Option(  # noqa: B008
        None,
        "--cwd",
        help="Project directory. Defaults to the current working directory.",
        hidden=True,
    ),
) -> None:
    """Append a verification-command capture to .fakoli-state/.evidence-buffer/.

    Called by hooks/capture-evidence.sh after every bash tool invocation.
    Failures are swallowed — this hook must never break the session.
    Always exits 0.
    """
    # All failures are silently swallowed — hook must never break the session.
    try:
        import datetime

        state_dir = _resolve_state_dir(cwd)
        if not state_dir.exists():
            raise typer.Exit(code=0)

        # Read stdout/stderr excerpts from temp files (up to 4000 chars each).
        stdout_excerpt = ""
        if stdout_file is not None:
            try:
                stdout_excerpt = stdout_file.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                pass

        stderr_excerpt = ""
        if stderr_file is not None:
            try:
                stderr_excerpt = stderr_file.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                pass

        # Build the evidence record.
        now = datetime.datetime.now(datetime.UTC)
        record: dict[str, object] = {
            "timestamp": now.isoformat(),
            "command": command,
            "exit_code": exit_code,
            "stdout_excerpt": stdout_excerpt,
            "stderr_excerpt": stderr_excerpt,
            "actor": actor,
        }

        # Determine which buffer file to append to by looking up the active claim.
        buffer_dir = state_dir / ".evidence-buffer"
        buffer_dir.mkdir(exist_ok=True)

        claim_id: str | None = None
        try:
            from fakoli_state.clock import SystemClock as _SystemClock
            from fakoli_state.state.sqlite import SqliteBackend as _SqliteBackend

            db_path = str(state_dir / "state.db")
            events_path = str(state_dir / "events.jsonl")
            _backend = _SqliteBackend(
                db_path=db_path,
                events_path=events_path,
                clock=_SystemClock(),
            )
            _backend.initialize()
            try:
                for active_claim in _backend.list_active_claims():
                    if active_claim.claimed_by == actor:
                        claim_id = active_claim.id
                        break
            finally:
                _backend.close()
        except Exception:  # noqa: BLE001
            pass  # if the DB is unavailable, fall through to orphan

        if claim_id is not None:
            buffer_file = buffer_dir / f"{claim_id}.json"
        else:
            # No active claim found — write to orphan buffer. Recovery path
            # uses the existing `submit --output-file` flag; the previously-
            # referenced `evidence attach` subcommand did not exist (Critic-2
            # flagged that following the error message produced Typer's
            # "No such command 'evidence'" error).
            record["note"] = (
                "orphan — no active claim found at capture time; "
                "pass this file via: fakoli-state submit TASK_ID --output-file <THIS_FILE>"
            )
            buffer_file = buffer_dir / "orphan.json"

        # Append the JSON record as a single line (JSONL).
        with buffer_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        pass  # hook must never block the session

    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
