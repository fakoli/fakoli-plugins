"""``fakoli-state replay`` — reconstruct canonical state from the event log.

This command exposes the backend's audit-guarantee primitive
(:meth:`fakoli_state.state.sqlite.SqliteBackend.replay_from_empty`) as a
user-facing, scriptable surface so the replay determinism the docs promise can
be *verified*, not just asserted.

Replay reads an append-only ``events.jsonl`` and rebuilds a fresh ``state.db``
into a **scratch directory** (``--into``). With ``--against`` it then compares
the replayed database to a reference database (the live ``state.db``) via a full
SQLite dump and exits non-zero on any divergence — the equivalence check the
``replay-equivalence`` CI job runs on every PR.

Safety: ``replay_from_empty`` *deletes* the target ``state.db`` before
rebuilding it. The command therefore refuses to write into the project's active
``.fakoli-state`` directory; ``--into`` must be a distinct scratch path.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import typer

from fakoli_state.cli._helpers import _resolve_state_dir


def _dump(db_path: str) -> str:
    """Return the full ``.dump`` of a SQLite database as a single string.

    Mirrors ``tests/test_sqlite.py::_sqlite_dump`` so the CLI equivalence check
    and the unit-test equivalence check compare state the same way.
    """
    conn = sqlite3.connect(db_path)
    try:
        return "\n".join(conn.iterdump()).strip()
    finally:
        conn.close()


def _first_diff_line(a: str, b: str) -> str:
    """Return a short human-readable description of the first differing line."""
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    for i, (la, lb) in enumerate(zip(a_lines, b_lines, strict=False)):
        if la != lb:
            return f"line {i + 1}:\n  replayed: {la}\n  expected: {lb}"
    if len(a_lines) != len(b_lines):
        return (
            f"line counts differ: replayed has {len(a_lines)} lines, "
            f"expected has {len(b_lines)} lines"
        )
    return "(no line-level difference found — check trailing bytes)"


def replay(
    from_events: Path = typer.Option(  # noqa: B008
        ...,
        "--from-events",
        help="Path to the events.jsonl audit log to replay.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    into: Path = typer.Option(  # noqa: B008
        ...,
        "--into",
        help="Scratch directory to rebuild state.db into. Must NOT be the "
        "project's active .fakoli-state directory.",
    ),
    against: Path | None = typer.Option(  # noqa: B008
        None,
        "--against",
        help="Reference state.db to compare the replayed database against. "
        "Exits non-zero (with a diff summary) on any divergence.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    force: bool = typer.Option(  # noqa: B008
        False,
        "--force",
        help="Allow --into to point at a directory that already contains a state.db.",
    ),
) -> None:
    """Replay an event log into a scratch DB; optionally assert equivalence.

    Exit codes: 0 = replay succeeded (and matched --against if given);
    1 = unsafe target or usage error; 2 = replay diverged from --against.
    """
    into_resolved = into.resolve()

    # --- Safety: never replay over the active project state ----------------
    active_state_dir = _resolve_state_dir(None)
    if into_resolved == active_state_dir:
        typer.echo(
            "Error: --into points at the active .fakoli-state directory. "
            "replay rebuilds state.db from scratch and would destroy live "
            "state. Choose a separate scratch directory.",
            err=True,
        )
        raise typer.Exit(code=1)

    into_resolved.mkdir(parents=True, exist_ok=True)
    scratch_db = into_resolved / "state.db"
    if scratch_db.exists() and not force:
        typer.echo(
            f"Error: {scratch_db} already exists. Pass --force to overwrite, "
            "or choose an empty --into directory.",
            err=True,
        )
        raise typer.Exit(code=1)

    # --- Replay into the scratch directory ---------------------------------
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.sqlite import SqliteBackend

    scratch_events = into_resolved / "events.jsonl"
    scratch_events.touch()
    backend = SqliteBackend(
        db_path=str(scratch_db),
        events_path=str(scratch_events),
        clock=SystemClock(),
    )
    backend.initialize()
    try:
        backend.replay_from_empty(str(from_events))
    finally:
        backend.close()

    typer.echo(f"Replayed {from_events} → {scratch_db}")

    # --- Optional equivalence check ----------------------------------------
    if against is not None:
        replayed_dump = _dump(str(scratch_db))
        reference_dump = _dump(str(against.resolve()))
        if replayed_dump == reference_dump:
            typer.echo("Equivalence check PASSED: replayed state matches --against.")
        else:
            typer.echo(
                "Equivalence check FAILED: replayed state diverges from --against.\n"
                + _first_diff_line(replayed_dump, reference_dump),
                err=True,
            )
            raise typer.Exit(code=2)

    # Keep the scratch copy of the source log faithful to what was replayed so
    # the directory is self-describing for later inspection.
    if from_events.resolve() != scratch_events.resolve():
        shutil.copyfile(from_events, scratch_events)
