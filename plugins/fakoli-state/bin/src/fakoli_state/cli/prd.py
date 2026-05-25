"""prd sub-app: prd parse, prd review (Phase 3)."""

from __future__ import annotations

from pathlib import Path

import typer

from fakoli_state.cli._helpers import (
    _PRD_FILENAME,
    _get_project_id,
    _open_backend,
    _require_state_dir,
    _resolve_state_dir,
)
from fakoli_state.state.backend import PENDING_EVENT_ID

prd_app = typer.Typer(
    name="prd",
    help="PRD lifecycle commands: parse, review, approve.",
    no_args_is_help=True,
)


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
            id=PENDING_EVENT_ID,
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
                id=PENDING_EVENT_ID,
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
                id=PENDING_EVENT_ID,
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
