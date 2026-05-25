"""Git branch helpers for fakoli-state claim flow.

Pure subprocess wrappers — no git Python library dependency.  The install
footprint stays small (Phase 1 policy: no heavy deps for optional features).

All public functions return dataclasses rather than raising on git failures.
The CLI translates a created=False result into a one-line stderr warning and
continues; fakoli-state must work without git.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BranchResult:
    """Result of a create_branch_for_task() call."""

    branch: str | None     # actual branch name created; None when created=False
    created: bool          # True iff the branch was created in this call
    reason: str | None     # why created=False, OR a warning string when created=True


def _slug(text: str) -> str:
    """Lowercase, alphanumeric + hyphens, max 40 chars.

    Example: "My Feature: Auth Tokens!" → "my-feature--auth-tokens-"
             collapsed → "my-feature-auth-tokens"
    """
    lowered = text.lower()
    replaced = re.sub(r"[^a-z0-9]+", "-", lowered)
    collapsed = re.sub(r"-{2,}", "-", replaced)
    stripped = collapsed.strip("-")
    return (stripped or "task")[:40]


def is_git_available() -> bool:
    """True if the `git` binary is on PATH."""
    return shutil.which("git") is not None


def is_git_repo(cwd: Path) -> bool:
    """True if *cwd* is inside a git repository.

    Uses `git rev-parse --git-dir` which exits 0 inside any repo and non-zero
    outside.  Stderr is suppressed so we never emit git noise to the user.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=str(cwd),
        capture_output=True,
    )
    return result.returncode == 0


def _branch_exists(branch: str, cwd: Path) -> bool:
    """Return True if *branch* already exists locally."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        cwd=str(cwd),
        capture_output=True,
    )
    return result.returncode == 0


def create_branch_for_task(
    task_id: str,
    title: str,
    *,
    cwd: Path,
    base: str | None = None,
) -> BranchResult:
    """Create an ``agent/<task_id_lower>-<slug>`` branch in *cwd*.

    Behavior:
    - If git not available OR not a git repo → BranchResult(None, False, reason)
      (the CLI warns but does NOT fail the claim).
    - Builds: ``agent/<task_id.lower()>-<slug(title)>`` truncated to 80 chars.
    - If that branch already exists, appends -2, -3, … until a unique name is found.
    - Runs ``git checkout -b <branch>`` (or ``git checkout -b <branch> <base>``).
    - On success: BranchResult(branch, True, None).
    - On collision-rename: BranchResult(branch_with_suffix, True, "renamed due to collision").
    - On git error: BranchResult(None, False, str(error)).

    Args:
        task_id: The task identifier (e.g. "T001"). Lowercased before use.
        title:   Human-readable task title, converted to a slug.
        cwd:     Directory in which to run git commands.
        base:    Optional base ref to branch off. If None, branches off HEAD.

    Returns:
        BranchResult describing what happened (or why it was skipped).
    """
    if not is_git_available():
        return BranchResult(None, False, "git not available on PATH")

    if not is_git_repo(cwd):
        return BranchResult(None, False, "not a git repository")

    base_name = f"agent/{task_id.lower()}-{_slug(title)}"
    # Truncate to 80 chars total to stay well under git's 250-byte limit
    # while keeping branch names scannable.
    base_name = base_name[:80]

    # Resolve a unique branch name (handle collisions with -2, -3, …).
    branch = base_name
    collision_suffix = 2
    renamed = False
    while _branch_exists(branch, cwd):
        branch = f"{base_name}-{collision_suffix}"[:80]
        collision_suffix += 1
        renamed = True

    # Build the git checkout command.
    cmd = ["git", "checkout", "-b", branch]
    if base is not None:
        cmd.append(base)

    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error_msg = (result.stderr or result.stdout or "unknown git error").strip()
        return BranchResult(None, False, error_msg)

    warning = "renamed due to collision" if renamed else None
    return BranchResult(branch, True, warning)
