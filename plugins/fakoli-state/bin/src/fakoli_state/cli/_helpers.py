"""Shared helpers used across all fakoli-state CLI command modules.

This module must NOT import from any sibling command module — it is the
common dependency, not a consumer. Circular imports are impossible by design.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from fakoli_state.state.models import Task
    from fakoli_state.state.sqlite import SqliteBackend

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATE_DIR_NAME = ".fakoli-state"
_PLUGIN_MANIFEST = ".claude-plugin/plugin.json"
_PRD_FILENAME = "prd.md"


# ---------------------------------------------------------------------------
# Backend helpers
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


def _get_project_id(backend: SqliteBackend) -> str:
    """Return the project ID from the backend, or 'project' as a fallback."""
    project = backend.get_project()
    if project is not None:
        return project.id
    return "project"


# ---------------------------------------------------------------------------
# Stale-claim reaper helper (shared by all mutating commands)
# ---------------------------------------------------------------------------


def _reap_stale_claims(backend: SqliteBackend) -> None:
    """Run the stale-claim detector against *backend*.

    Called at the start of claim/release/renew/next so users always see
    consistent state without having to think about expiry.  Operational
    failures (e.g. ``StateLocked`` from a concurrent writer holding the
    busy_timeout, ``TransactionAborted`` from a transient race) are
    swallowed — reaping is best-effort and a stale claim that slips through
    will be caught on the next invocation.

    ``SchemaMismatch`` (CL-3) is **not** swallowed: a DB whose
    ``user_version`` does not match the code's ``SCHEMA_VERSION`` is a
    genuine "your install needs migration" signal, not a transient hiccup.
    Hiding it behind a confusing secondary error from the primary command
    leaves users debugging the wrong layer.  Let it propagate so the CLI's
    top-level error handler can surface the clean schema message.
    """
    from fakoli_state.claims.stale import detect_and_release_stale
    from fakoli_state.clock import SystemClock
    from fakoli_state.state.backend import (
        SchemaMismatch,
        StateLocked,
        TransactionAborted,
    )

    try:
        detect_and_release_stale(backend, SystemClock())
    except SchemaMismatch:
        raise  # CL-3: surface DB-version drift; do not mask
    except (StateLocked, TransactionAborted):
        pass  # operational; reaping is best-effort and self-healing
    except Exception:  # noqa: BLE001
        # Greptile PR #48 P2: raw sqlite3.OperationalError ("unable to open
        # database file", disk full, etc.) and any other unwrapped exception
        # must not block the primary command. Reaping is opportunistic — if
        # it fails for unexpected reasons we still log nothing here (per the
        # "never noisy" contract) and let the primary op proceed. The next
        # invocation will retry.
        pass


# ---------------------------------------------------------------------------
# Score helper (used by plan.py and init_status.py)
# ---------------------------------------------------------------------------


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
