"""Dependency and conflict-group inference for Task lists — no I/O, no LLM.

Derives structural edges from ``likely_files`` overlap heuristics so that the
planning engine can seed ``Task.dependencies`` and ``Task.conflict_groups``
without requiring LLM augmentation.

Heuristics
----------
``infer_dependencies``:
    If Task A's ``likely_files`` is a *strict subset* of Task B's, A is added
    as a dependency of B (the broader change goes first; A specialises B).
    Conservative: only strict-subset edges are added — never speculative ones.

``infer_conflict_groups``:
    For each pair of tasks with *any* ``likely_files`` overlap that are NOT in a
    strict subset/superset relationship, they are grouped into a named
    ConflictGroup.  Group IDs follow the pattern ``CG-<sorted-task-ids>``.
"""

from __future__ import annotations

from typing import NamedTuple

from fakoli_state.state.models import ConflictGroup, Task

__all__ = [
    "InferenceResult",
    "infer_all",
    "infer_conflict_groups",
    "infer_dependencies",
]


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


class InferenceResult(NamedTuple):
    """Output of ``infer_all`` — always returned, never raised."""

    tasks: list[Task]
    conflict_groups: list[ConflictGroup]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _files_set(task: Task) -> frozenset[str]:
    """Return the task's likely_files as a frozenset for set operations."""
    return frozenset(task.likely_files)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def infer_dependencies(tasks: list[Task]) -> list[Task]:
    """Return a new Task list with ``.dependencies`` populated by subset heuristics.

    For each pair (A, B): if A.likely_files is a *strict* subset of B.likely_files,
    A is added to B.dependencies.  "B is a broader change; A specialises B, so B
    should be authored first."

    Pure — takes a Task list, returns a Task list.  Input tasks are never mutated;
    output tasks are produced via ``model_copy``.

    Args:
        tasks: List of Task models (likely_files populated from PRD parse).

    Returns:
        New list of Task instances with dependencies set from subset edges.
        Tasks with no inferred dependencies are returned unchanged.
    """
    if not tasks:
        return []

    # Build a map from task ID to its file set, then find all strict-subset edges.
    # An edge A → B means "A.files ⊂ B.files (strict)", so B depends on A.
    # Wait — task spec says: "if Task A's likely_files is a strict subset of
    # Task B's, A depends on B (because B is a broader change that A specialises;
    # the broader work usually goes first)."
    # So: A_files ⊂ B_files (strict) → A.dependencies.append(B.id)

    file_sets: dict[str, frozenset[str]] = {
        t.id: _files_set(t) for t in tasks
    }

    # Collect dependency edges: new_deps[task_id] = set of dependency IDs.
    new_deps: dict[str, set[str]] = {t.id: set(t.dependencies) for t in tasks}

    task_ids = [t.id for t in tasks]
    for id_a in task_ids:
        set_a = file_sets[id_a]
        if not set_a:
            # A task with no likely_files cannot be a subset of anything.
            continue
        for id_b in task_ids:
            if id_a == id_b:
                continue
            set_b = file_sets[id_b]
            # Strict subset: A ⊂ B means A ⊆ B and A ≠ B.
            if set_a < set_b:
                # A specialises B → A depends on B.
                new_deps[id_a].add(id_b)

    # Build the output list, replacing only tasks whose dependency set changed.
    updated: list[Task] = []
    for task in tasks:
        merged = sorted(new_deps[task.id])
        if merged != task.dependencies:
            updated.append(task.model_copy(update={"dependencies": merged}))
        else:
            updated.append(task)

    return updated


def infer_conflict_groups(
    tasks: list[Task],
) -> tuple[list[Task], list[ConflictGroup]]:
    """Return (tasks-with-conflict_groups-populated, ConflictGroup list).

    For each pair of tasks with ANY ``likely_files`` overlap that are NOT in a
    strict subset/superset relationship, group them together.  Groups are named
    ``CG-<sorted-task-ids>`` where the IDs are separated by ``-``.

    A task may appear in multiple conflict groups (one per pair that it is part
    of).  The ``Task.conflict_groups`` field records the IDs of all groups the
    task belongs to.

    Pure — takes a Task list, returns a new Task list and ConflictGroup list.

    Args:
        tasks: List of Task models (dependency inference should already be applied).

    Returns:
        Tuple of (updated Task list, list of ConflictGroup instances).
    """
    if not tasks:
        return [], []

    file_sets: dict[str, frozenset[str]] = {
        t.id: _files_set(t) for t in tasks
    }

    # Map task ID → set of conflict-group IDs it belongs to.
    task_conflict_groups: dict[str, set[str]] = {t.id: set() for t in tasks}
    conflict_groups: list[ConflictGroup] = []

    task_ids = [t.id for t in tasks]
    seen_pairs: set[frozenset[str]] = set()

    for idx_a in range(len(task_ids)):
        id_a = task_ids[idx_a]
        set_a = file_sets[id_a]
        if not set_a:
            continue
        for idx_b in range(idx_a + 1, len(task_ids)):
            id_b = task_ids[idx_b]
            pair = frozenset({id_a, id_b})
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            set_b = file_sets[id_b]
            if not set_b:
                continue

            overlap = set_a & set_b
            if not overlap:
                continue

            # If one is a strict subset of the other, skip — that's a dependency,
            # not a conflict.
            if set_a < set_b or set_b < set_a:
                continue

            # Partial overlap and neither is a subset: this is a conflict group.
            sorted_ids = sorted([id_a, id_b])
            cg_id = "CG-" + "-".join(sorted_ids)
            cg = ConflictGroup(
                id=cg_id,
                name=cg_id,
                task_ids=sorted_ids,
                reason=(
                    f"Tasks {id_a} and {id_b} share overlapping files: "
                    + ", ".join(sorted(overlap))
                ),
            )
            conflict_groups.append(cg)
            task_conflict_groups[id_a].add(cg_id)
            task_conflict_groups[id_b].add(cg_id)

    # Build updated task list.
    updated_tasks: list[Task] = []
    for task in tasks:
        new_cgs = sorted(task_conflict_groups[task.id])
        existing_cgs = sorted(task.conflict_groups)
        if new_cgs != existing_cgs:
            updated_tasks.append(
                task.model_copy(update={"conflict_groups": new_cgs})
            )
        else:
            updated_tasks.append(task)

    return updated_tasks, conflict_groups


def infer_all(tasks: list[Task]) -> InferenceResult:
    """Compose dependency and conflict inference into a single result.

    Apply in order: dependencies first, then conflict groups.  This ordering
    matters because ``infer_conflict_groups`` skips strict-subset pairs which
    are correctly classified as dependencies by ``infer_dependencies``.

    Pure — takes a Task list, returns an InferenceResult.  No I/O.

    Args:
        tasks: List of Task models to annotate.

    Returns:
        InferenceResult with the fully-annotated Task list and conflict groups.
    """
    tasks_with_deps = infer_dependencies(tasks)
    tasks_with_all, conflict_groups = infer_conflict_groups(tasks_with_deps)
    return InferenceResult(tasks=tasks_with_all, conflict_groups=conflict_groups)
