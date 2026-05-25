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

import typer

from fakoli_state import __version__

app = typer.Typer(
    name="fakoli-state",
    help=(
        "Local-first project state engine: turn brainstorms and PRDs into reviewed, "
        "lockable, evidence-backed work packets that humans and AI agents can "
        "coordinate on without conflicts."
    ),
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
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


if __name__ == "__main__":
    app()
