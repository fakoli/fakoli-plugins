#!/usr/bin/env python3
"""Golden-fixture generator for the SL-1 replay-equivalence test.

This script builds a realistic, *deterministic* fakoli-state event log by
driving the real ``SqliteBackend.apply_event`` pipeline with a
``FrozenClock``, then commits two artifacts under
``tests/fixtures/replay/sample-project/``:

* ``events.jsonl``       — the deterministic audit log the scenario produced.
* ``expected-state.json`` — ``serialize_state`` of that backend, pretty-printed
                            with ``sort_keys=True`` and a trailing newline.

Both artifacts are committed. Regeneration is a **deliberate human step** — it
is never run automatically by the test suite. Re-run it only when the fixture
*legitimately* changes (e.g. a new canonical collection is added to
``serialize_state`` or the scenario is intentionally extended):

    uv run --project plugins/fakoli-state/bin \
        python plugins/fakoli-state/tests/fixtures/replay/regenerate.py

After regenerating, eyeball the diff (``git diff`` on the two artifacts), run
the equivalence test, and commit the artifacts together with the code change
that motivated them.

Determinism contract
--------------------
Every timestamp in the produced ``events.jsonl`` comes from the ``FrozenClock``
(advanced explicitly between steps) or from explicit ISO strings in the event
payloads — never from wall-clock time. The scenario uses fixed IDs throughout.
As a result, running this script twice produces byte-identical artifacts.

Scenario exercised
-------------------
A small but realistic project lifecycle:

1. ``project.created`` + ``state.initialized``.
2. ``prd.parsed`` (one requirement) + ``prd.reviewed``.
3. One ``feature.created``.
4. Three tasks created and each promoted proposed -> drafted -> reviewed ->
   ready (a non-trivial multi-task log).
5. T001: ``claim.created`` with a lease, a heartbeat ``claim.renewed`` after the
   clock advances, then ``evidence.submitted`` (auto-releases the claim) and a
   ``task.applied`` acceptance (inserts a review row, task -> done).
6. T002: ``claim.created`` followed by ``claim.stale`` (a stale-claim reap;
   task returns to ready).
7. A ``sync_mapping.upserted`` mirroring T001 into github_issues.
8. Two tombstone lines proving abort / idempotent-no-op lines are skipped on
   replay:
     * a ``warn.idempotent_no_op`` produced by the genuine ``apply_event`` path
       — a *second* ``evidence.submitted`` for C001 under a different
       evidence_id is rejected as a no-op (the handler appends the warn line and
       returns without mutating; the canonical no-op event itself replays
       cleanly), and
     * an ``error.transaction_aborted`` tombstone appended to the log in the
       exact shape ``_append_abort_event`` writes.

``replay_from_empty`` skips both tombstone actions.

Why the abort tombstone is appended directly (not provoked via apply_event)
---------------------------------------------------------------------------
On the non-PENDING (replay/legacy) path, ``apply_event`` writes the canonical
event line to ``events.jsonl`` BEFORE attempting the SQLite mutation. So a
handler-rejected event leaves a *poison* canonical line in the log in addition
to its abort tombstone — and ``replay_from_empty`` would re-apply that canonical
line and re-fail, aborting the whole replay. A well-formed, replayable committed
log must therefore NOT contain a canonical event that the handler rejects. We
get the abort tombstone the honest way: append exactly the JSONL line
``_append_abort_event`` emits (``action='error.transaction_aborted'`` with an
``original_action`` / ``reason`` payload), with no poison canonical predecessor.
That line is what replay is required to skip, and it does.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fakoli_state.clock import FrozenClock
from fakoli_state.state.models import Event
from fakoli_state.state.snapshot import serialize_state
from fakoli_state.state.sqlite import SqliteBackend

# Fixed scenario epoch — matches the suite-wide FrozenClock anchor.
_T0 = datetime(2026, 5, 24, 18, 0, 0, tzinfo=UTC)

_FIXTURE_DIR = Path(__file__).parent / "sample-project"
_EVENTS_OUT = _FIXTURE_DIR / "events.jsonl"
_EXPECTED_OUT = _FIXTURE_DIR / "expected-state.json"


def _event(
    action: str,
    payload: dict[str, Any],
    *,
    event_id: str,
    clock: FrozenClock,
    target_kind: str = "task",
    target_id: str = "T001",
) -> Event:
    """Build an Event timestamped at the clock's current time."""
    return Event(
        id=event_id,
        timestamp=clock.now(),
        actor="test",
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        payload_json=payload,
    )


def _task_payload(*, task_id: str, clock: FrozenClock) -> dict[str, Any]:
    now = clock.now().isoformat()
    return {
        "id": task_id,
        "feature_id": "F001",
        "title": f"Task {task_id}",
        "description": "desc",
        "status": "proposed",
        "priority": "medium",
        "dependencies": [],
        "conflict_groups": [],
        "scores": {},
        "acceptance_criteria": [],
        "implementation_notes": [],
        "verification": {},
        "likely_files": [],
        "parent_task_id": None,
        "created_at": now,
        "updated_at": now,
    }


def _claim_payload(
    *, claim_id: str, task_id: str, clock: FrozenClock
) -> dict[str, Any]:
    now = clock.now()
    return {
        "id": claim_id,
        "task_id": task_id,
        "claimed_by": "agent-alpha",
        "claim_type": "task",
        "status": "active",
        "branch": None,
        "worktree_path": None,
        "expected_files": [],
        "created_at": now.isoformat(),
        "lease_expires_at": (now + timedelta(hours=1)).isoformat(),
        "last_heartbeat_at": now.isoformat(),
        "released_at": None,
        "release_reason": None,
    }


def build_scenario(state_dir: Path) -> SqliteBackend:
    """Build the canonical scenario through apply_event; return the backend.

    The clock is advanced between steps so lease / heartbeat / renew / stale
    timestamps are realistic and distinct. IDs are fixed so the produced
    events.jsonl is byte-stable.
    """
    clock = FrozenClock(_T0)
    db_path = str(state_dir / "state.db")
    events_path = str(state_dir / "events.jsonl")
    Path(events_path).touch()
    b = SqliteBackend(db_path=db_path, events_path=events_path, clock=clock)
    b.initialize()

    ids = iter(f"E{n:06d}" for n in range(1, 10_000))

    # 1. Project + state init.
    b.apply_event(_event(
        "project.created",
        {
            "id": "proj-1",
            "name": "Sample Project",
            "description": "A realistic replay-equivalence fixture.",
            "created_at": _T0.isoformat(),
            "updated_at": _T0.isoformat(),
        },
        event_id=next(ids), clock=clock,
        target_kind="project", target_id="proj-1",
    ))
    b.apply_event(_event(
        "state.initialized", {},
        event_id=next(ids), clock=clock,
        target_kind="project", target_id="proj-1",
    ))

    # 2. PRD parsed (one requirement) + reviewed.
    b.apply_event(_event(
        "prd.parsed",
        {
            "project_id": "proj-1",
            "status": "draft",
            "summary": "Build the thing.",
            "goals": ["Ship SL-1."],
            "non_goals": [],
            "requirements": [
                {"id": "R001", "prd_section": "requirements",
                 "text": "Replay must reproduce canonical state.",
                 "source_paragraph": None, "derived": False},
            ],
            "acceptance_criteria": ["Golden snapshot matches."],
            "risks": [],
            "open_questions": [],
        },
        event_id=next(ids), clock=clock,
        target_kind="prd", target_id="proj-1",
    ))
    b.apply_event(_event(
        "prd.reviewed", {"project_id": "proj-1", "reviewer": "alice"},
        event_id=next(ids), clock=clock,
        target_kind="prd", target_id="proj-1",
    ))

    # 3. One feature.
    b.apply_event(_event(
        "feature.created",
        {
            "id": "F001",
            "title": "Feature F001",
            "description": "The only feature.",
            "status": "proposed",
            "requirements": [],
            "tasks": [],
        },
        event_id=next(ids), clock=clock,
        target_kind="feature", target_id="F001",
    ))

    # 4. Three tasks, each promoted proposed -> drafted -> reviewed -> ready.
    for task_id in ("T001", "T002", "T003"):
        b.apply_event(_event(
            "task.created", _task_payload(task_id=task_id, clock=clock),
            event_id=next(ids), clock=clock, target_id=task_id,
        ))
        for from_s, to_s in (
            ("proposed", "drafted"),
            ("drafted", "reviewed"),
            ("reviewed", "ready"),
        ):
            b.apply_event(_event(
                "task.status_changed",
                {"task_id": task_id, "from": from_s, "to": to_s},
                event_id=next(ids), clock=clock, target_id=task_id,
            ))

    # 5. T001 — claim with a lease, a heartbeat/renew after the clock advances,
    # then evidence.submitted (auto-releases the claim) + task.applied accepted.
    b.apply_event(_event(
        "claim.created", _claim_payload(claim_id="C001", task_id="T001", clock=clock),
        event_id=next(ids), clock=clock, target_kind="claim", target_id="C001",
    ))

    clock.advance(minutes=20)  # work happens; heartbeat renews the lease.
    renew_now = clock.now()
    b.apply_event(_event(
        "claim.renewed",
        {
            "claim_id": "C001",
            "lease_expires_at": (renew_now + timedelta(hours=1)).isoformat(),
            "last_heartbeat_at": renew_now.isoformat(),
            "renewed_by": "agent-alpha",
        },
        event_id=next(ids), clock=clock, target_kind="claim", target_id="C001",
    ))

    clock.advance(minutes=10)
    b.apply_event(_event(
        "evidence.submitted",
        {
            "task_id": "T001",
            "claim_id": "C001",
            "evidence_id": "EV001",
            "submitted_by": "agent-alpha",
            "commands_run": ["pytest tests/ -v"],
            "files_changed": ["src/auth.py"],
            "output_excerpt": "5 passed",
            "pr_url": None,
            "commit_sha": None,
            "screenshots": [],
            "known_limitations": None,
        },
        event_id=next(ids), clock=clock, target_id="T001",
    ))
    b.apply_event(_event(
        "task.applied",
        {"task_id": "T001", "reviewer": "alice", "decision": "accepted", "notes": None},
        event_id=next(ids), clock=clock, target_id="T001",
    ))

    # 6. T002 — claim then claim.stale (a stale-claim reap; task -> ready).
    clock.advance(minutes=5)
    b.apply_event(_event(
        "claim.created", _claim_payload(claim_id="C002", task_id="T002", clock=clock),
        event_id=next(ids), clock=clock, target_kind="claim", target_id="C002",
    ))
    clock.advance(hours=2)  # lease (1h) is now expired.
    stale_now = clock.now()
    b.apply_event(_event(
        "claim.stale",
        {
            "claim_id": "C002",
            "task_id": "T002",
            "expired_at": (stale_now - timedelta(hours=1)).isoformat(),
            "detected_at": stale_now.isoformat(),
            "reason": "lease_expired",
            "actor": "system",
        },
        event_id=next(ids), clock=clock, target_kind="claim", target_id="C002",
    ))

    # 7. sync_mapping.upserted — mirror T001 into github_issues.
    b.apply_event(_event(
        "sync_mapping.upserted",
        {
            "task_id": "T001",
            "external_system": "github_issues",
            "external_id": "42",
            "external_url": "https://github.com/acme/repo/issues/42",
            "last_synced_at": clock.now().isoformat(),
            "sync_state": "in_sync",
            "conflict_resolution_strategy": "prompt",
            "provider_metadata": {"labels": ["sl-1"]},
        },
        event_id=next(ids), clock=clock,
        target_kind="sync_mapping", target_id="T001",
    ))

    # 8a. warn.idempotent_no_op — a real no-op tombstone. A SECOND
    # evidence.submitted for C001 under a DIFFERENT evidence_id is rejected as
    # an idempotent no-op (the handler appends a warn.idempotent_no_op line and
    # returns without mutating).
    b.apply_event(_event(
        "evidence.submitted",
        {
            "task_id": "T001",
            "claim_id": "C001",
            "evidence_id": "EV-DUP",   # different id for same claim -> no-op.
            "submitted_by": "agent-alpha",
            "commands_run": ["pytest -q"],
            "files_changed": ["src/auth.py"],
            "output_excerpt": "ok",
            "pr_url": None,
            "commit_sha": None,
            "screenshots": [],
            "known_limitations": None,
        },
        event_id=next(ids), clock=clock, target_id="T001",
    ))

    # 8b. error.transaction_aborted — appended in the exact shape
    # _append_abort_event writes (see module docstring for why this is appended
    # directly rather than provoked through apply_event). replay_from_empty
    # skips it; it never touches SQLite state.
    abort_line = {
        "id": "E000099",  # the would-be id of the rejected event
        "timestamp": clock.now().isoformat(),
        "actor": "system",
        "action": "error.transaction_aborted",
        "target_kind": "task",
        "target_id": "T003",
        "payload_json": {
            "original_action": "evidence.submitted",
            "reason": "evidence.submitted payload requires non-empty 'commands_run'.",
        },
    }
    with open(events_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(abort_line) + "\n")

    return b


def main() -> None:
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp)
        b = build_scenario(state_dir)
        try:
            snap = serialize_state(b)
        finally:
            b.close()

        # Copy the deterministic events.jsonl into the fixture dir.
        shutil.copyfile(state_dir / "events.jsonl", _EVENTS_OUT)

        # Write the golden snapshot: pretty-printed, sort_keys, trailing newline.
        _EXPECTED_OUT.write_text(
            json.dumps(snap, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"wrote {_EVENTS_OUT}")
    print(f"wrote {_EXPECTED_OUT}")


if __name__ == "__main__":
    main()
