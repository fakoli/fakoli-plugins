"""Tests for fakoli_state.state.transitions — every public transition function.

Each transition has:
- A happy-path test: status change + updated_at change
- A gate-failure test: TransitionError raised with expected gate_name / code

Special tests:
- PRD → ready → claimed requires reviewed PRD
- drafted → reviewed requires acceptance_criteria
- Transitions return new instance (model_copy semantics)
- Evidence complete substring membership
"""

from __future__ import annotations

import datetime

import pytest

from fakoli_state.state.models import (
    PRD,
    Claim,
    ClaimStatus,
    ClaimType,
    Evidence,
    PRDStatus,
    Task,
    TaskStatus,
    Verification,
)
from fakoli_state.state.transitions import (
    TransitionError,
    prd_draft_to_reviewed,
    prd_reviewed_to_approved,
    prd_to_rejected,
    task_accepted_to_done,
    task_blocked_to_in_progress,
    task_claimed_to_in_progress,
    task_drafted_to_reviewed,
    task_in_progress_to_blocked,
    task_in_progress_to_needs_review,
    task_needs_review_to_accepted,
    task_needs_review_to_rejected,
    task_proposed_to_drafted,
    task_ready_to_claimed,
    task_rejected_to_drafted,
    task_reviewed_to_ready,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UTC = datetime.UTC
_T0 = datetime.datetime(2026, 5, 24, 18, 0, 0, tzinfo=_UTC)
_T1 = datetime.datetime(2026, 5, 24, 19, 0, 0, tzinfo=_UTC)  # 1 hour later


def _make_prd(**overrides: object) -> PRD:
    defaults: dict[str, object] = {"status": PRDStatus.draft}
    defaults.update(overrides)
    return PRD(**defaults)


def _make_task(status: TaskStatus = TaskStatus.proposed, **overrides: object) -> Task:
    defaults: dict[str, object] = {
        "id": "T001",
        "feature_id": "F001",
        "title": "Write tests",
        "description": "Comprehensive tests",
        "status": status,
        "created_at": _T0,
        "updated_at": _T0,
    }
    defaults.update(overrides)
    return Task(**defaults)


def _make_reviewed_task(**overrides: object) -> Task:
    """A task ready to pass the readiness gate."""
    return _make_task(
        status=TaskStatus.drafted,
        acceptance_criteria=["it must work"],
        verification=Verification(commands=["pytest"]),
        **overrides,
    )


def _make_claim(
    *,
    task_id: str = "T001",
    status: ClaimStatus = ClaimStatus.active,
    expires_in_seconds: float = 3600,
    now: datetime.datetime = _T0,
) -> Claim:
    return Claim(
        id="C001",
        task_id=task_id,
        claimed_by="agent-x",
        claim_type=ClaimType.task,
        status=status,
        created_at=now,
        lease_expires_at=now + datetime.timedelta(seconds=expires_in_seconds),
        last_heartbeat_at=now,
    )


def _make_evidence(
    *,
    task_id: str = "T001",
    commands_run: list[str] | None = None,
    files_changed: list[str] | None = None,
    output_excerpt: str | None = None,
    pr_url: str | None = None,
    commit_sha: str | None = None,
) -> Evidence:
    return Evidence(
        id="EV001",
        task_id=task_id,
        claim_id="C001",
        commands_run=commands_run or [],
        files_changed=files_changed or [],
        output_excerpt=output_excerpt,
        pr_url=pr_url,
        commit_sha=commit_sha,
        submitted_at=_T0,
        submitted_by="agent-x",
    )


# ---------------------------------------------------------------------------
# TransitionError structure
# ---------------------------------------------------------------------------


class TestTransitionError:
    def test_transition_error_attributes(self) -> None:
        """TransitionError stores code, gate_name, current_status, message."""
        err = TransitionError(
            code="gate_failed",
            gate_name="readiness_gate",
            current_status="drafted",
            message="Something is missing.",
        )
        assert err.code == "gate_failed"
        assert err.gate_name == "readiness_gate"
        assert err.current_status == "drafted"
        assert err.message == "Something is missing."
        assert "readiness_gate" in repr(err)

    def test_transition_error_no_gate_name(self) -> None:
        """TransitionError gate_name defaults to None."""
        err = TransitionError(
            code="wrong_status",
            current_status="proposed",
            message="Wrong status.",
        )
        assert err.gate_name is None


# ---------------------------------------------------------------------------
# PRD transitions
# ---------------------------------------------------------------------------


class TestPRDTransitions:
    def test_prd_draft_to_reviewed_happy(self) -> None:
        prd = _make_prd(status=PRDStatus.draft)
        result = prd_draft_to_reviewed(prd, reviewer="alice", now=_T1)
        assert result.status == PRDStatus.reviewed
        assert result.last_reviewed_by == "alice"
        assert result.last_reviewed_at == _T1

    def test_prd_draft_to_reviewed_wrong_status(self) -> None:
        prd = _make_prd(status=PRDStatus.approved)
        with pytest.raises(TransitionError) as exc_info:
            prd_draft_to_reviewed(prd, reviewer="alice", now=_T1)
        assert exc_info.value.code == "wrong_status"
        assert exc_info.value.current_status == "approved"

    def test_prd_reviewed_to_approved_happy(self) -> None:
        prd = _make_prd(status=PRDStatus.reviewed)
        result = prd_reviewed_to_approved(prd, approver="bob", now=_T1)
        assert result.status == PRDStatus.approved
        assert result.last_reviewed_by == "bob"

    def test_prd_reviewed_to_approved_wrong_status(self) -> None:
        prd = _make_prd(status=PRDStatus.draft)
        with pytest.raises(TransitionError) as exc_info:
            prd_reviewed_to_approved(prd, approver="bob", now=_T1)
        assert exc_info.value.code == "wrong_status"
        assert exc_info.value.current_status == "draft"

    def test_prd_to_rejected_from_draft(self) -> None:
        prd = _make_prd(status=PRDStatus.draft)
        result = prd_to_rejected(prd, reviewer="carol", reason="incomplete", now=_T1)
        assert result.status == PRDStatus.rejected
        assert any("Rejected by carol" in q for q in result.open_questions)

    def test_prd_to_rejected_from_reviewed(self) -> None:
        prd = _make_prd(status=PRDStatus.reviewed)
        result = prd_to_rejected(prd, reviewer="carol", reason="bad goals", now=_T1)
        assert result.status == PRDStatus.rejected

    def test_prd_to_rejected_from_approved_raises(self) -> None:
        prd = _make_prd(status=PRDStatus.approved)
        with pytest.raises(TransitionError) as exc_info:
            prd_to_rejected(prd, reviewer="carol", reason="too late", now=_T1)
        assert exc_info.value.code == "wrong_status"
        assert exc_info.value.current_status == "approved"

    def test_prd_to_rejected_from_rejected_raises(self) -> None:
        prd = _make_prd(status=PRDStatus.rejected)
        with pytest.raises(TransitionError) as exc_info:
            prd_to_rejected(prd, reviewer="carol", reason="again", now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — proposed → drafted
# ---------------------------------------------------------------------------


class TestTaskProposedToDrafted:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.proposed)
        result = task_proposed_to_drafted(task, now=_T1)
        assert result.status == TaskStatus.drafted
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.drafted)
        with pytest.raises(TransitionError) as exc_info:
            task_proposed_to_drafted(task, now=_T1)
        assert exc_info.value.code == "wrong_status"
        assert exc_info.value.current_status == "drafted"


# ---------------------------------------------------------------------------
# Task transitions — drafted → reviewed
# ---------------------------------------------------------------------------


class TestTaskDraftedToReviewed:
    def test_happy_path(self) -> None:
        task = _make_reviewed_task()
        result = task_drafted_to_reviewed(task, now=_T1)
        assert result.status == TaskStatus.reviewed
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.proposed)
        with pytest.raises(TransitionError) as exc_info:
            task_drafted_to_reviewed(task, now=_T1)
        assert exc_info.value.code == "wrong_status"

    def test_task_drafted_to_reviewed_requires_acceptance_criteria(self) -> None:
        """Empty acceptance_criteria raises TransitionError from readiness_gate."""
        task = _make_task(
            status=TaskStatus.drafted,
            acceptance_criteria=[],  # empty!
            verification=Verification(commands=["pytest"]),
        )
        with pytest.raises(TransitionError) as exc_info:
            task_drafted_to_reviewed(task, now=_T1)
        err = exc_info.value
        assert err.code == "gate_failed"
        assert err.gate_name == "readiness_gate"
        assert "acceptance_criteria" in err.message

    def test_task_drafted_to_reviewed_requires_verification_commands(self) -> None:
        """Empty verification.commands raises TransitionError from readiness_gate."""
        task = _make_task(
            status=TaskStatus.drafted,
            acceptance_criteria=["it works"],
            verification=Verification(commands=[]),  # empty!
        )
        with pytest.raises(TransitionError) as exc_info:
            task_drafted_to_reviewed(task, now=_T1)
        err = exc_info.value
        assert err.code == "gate_failed"
        assert err.gate_name == "readiness_gate"
        assert "verification.commands" in err.message

    def test_task_drafted_to_reviewed_both_missing(self) -> None:
        """Both missing fields → error message lists both."""
        task = _make_task(
            status=TaskStatus.drafted,
            acceptance_criteria=[],
            verification=Verification(commands=[]),
        )
        with pytest.raises(TransitionError) as exc_info:
            task_drafted_to_reviewed(task, now=_T1)
        assert "acceptance_criteria" in exc_info.value.message
        assert "verification.commands" in exc_info.value.message


# ---------------------------------------------------------------------------
# Task transitions — reviewed → ready
# ---------------------------------------------------------------------------


class TestTaskReviewedToReady:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.reviewed)
        result = task_reviewed_to_ready(task, now=_T1)
        assert result.status == TaskStatus.ready
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.drafted)
        with pytest.raises(TransitionError) as exc_info:
            task_reviewed_to_ready(task, now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — ready → claimed
# ---------------------------------------------------------------------------


class TestTaskReadyToClaimed:
    def test_happy_path_reviewed_prd(self) -> None:
        task = _make_task(status=TaskStatus.ready)
        claim = _make_claim()
        prd = _make_prd(status=PRDStatus.reviewed)
        result = task_ready_to_claimed(task, claim, prd, now=_T1)
        assert result.status == TaskStatus.claimed
        assert result.updated_at == _T1

    def test_happy_path_approved_prd(self) -> None:
        task = _make_task(status=TaskStatus.ready)
        claim = _make_claim()
        prd = _make_prd(status=PRDStatus.approved)
        result = task_ready_to_claimed(task, claim, prd, now=_T1)
        assert result.status == TaskStatus.claimed

    def test_task_ready_to_claimed_requires_reviewed_prd(self) -> None:
        """PRD in draft → TransitionError(code='gate_failed', gate_name='prd_status_gate')."""
        task = _make_task(status=TaskStatus.ready)
        claim = _make_claim()
        prd = _make_prd(status=PRDStatus.draft)
        with pytest.raises(TransitionError) as exc_info:
            task_ready_to_claimed(task, claim, prd, now=_T1)
        err = exc_info.value
        assert err.code == "gate_failed"
        assert err.gate_name == "prd_status_gate"
        assert "reviewed" in err.message or "approved" in err.message

    def test_task_ready_to_claimed_wrong_task_status(self) -> None:
        task = _make_task(status=TaskStatus.drafted)
        claim = _make_claim()
        prd = _make_prd(status=PRDStatus.reviewed)
        with pytest.raises(TransitionError) as exc_info:
            task_ready_to_claimed(task, claim, prd, now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — claimed → in_progress
# ---------------------------------------------------------------------------


class TestTaskClaimedToInProgress:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.claimed)
        result = task_claimed_to_in_progress(task, now=_T1)
        assert result.status == TaskStatus.in_progress
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.ready)
        with pytest.raises(TransitionError) as exc_info:
            task_claimed_to_in_progress(task, now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — in_progress → blocked
# ---------------------------------------------------------------------------


class TestTaskInProgressToBlocked:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.in_progress)
        result = task_in_progress_to_blocked(task, reason="waiting for infra", now=_T1)
        assert result.status == TaskStatus.blocked
        assert any("Blocked: waiting for infra" in n for n in result.implementation_notes)
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.claimed)
        with pytest.raises(TransitionError) as exc_info:
            task_in_progress_to_blocked(task, reason="no", now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — blocked → in_progress
# ---------------------------------------------------------------------------


class TestTaskBlockedToInProgress:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.blocked)
        result = task_blocked_to_in_progress(task, now=_T1)
        assert result.status == TaskStatus.in_progress
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.in_progress)
        with pytest.raises(TransitionError) as exc_info:
            task_blocked_to_in_progress(task, now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — in_progress → needs_review
# ---------------------------------------------------------------------------


class TestTaskInProgressToNeedsReview:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.in_progress)
        evidence = _make_evidence()
        result = task_in_progress_to_needs_review(task, evidence=evidence, now=_T1)
        assert result.status == TaskStatus.needs_review
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.claimed)
        evidence = _make_evidence()
        with pytest.raises(TransitionError) as exc_info:
            task_in_progress_to_needs_review(task, evidence=evidence, now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — needs_review → accepted
# ---------------------------------------------------------------------------


class TestTaskNeedsReviewToAccepted:
    def test_happy_path_no_required_evidence(self) -> None:
        """With no required_evidence, gate passes automatically."""
        task = _make_task(status=TaskStatus.needs_review)
        evidence = _make_evidence()
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted
        assert any("Accepted by alice" in n for n in result.implementation_notes)
        assert result.updated_at == _T1

    def test_happy_path_with_matching_evidence(self) -> None:
        """Required evidence present in commands_run."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["pytest output"]),
        )
        evidence = _make_evidence(
            commands_run=["pytest -x"],
            output_excerpt="pytest output: 10 passed",
        )
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.in_progress)
        evidence = _make_evidence()
        with pytest.raises(TransitionError) as exc_info:
            task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert exc_info.value.code == "wrong_status"

    def test_evidence_gate_failure(self) -> None:
        """Missing required evidence raises TransitionError from evidence_gate."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["test coverage report"]),
        )
        evidence = _make_evidence(commands_run=["pytest"])  # no coverage report!
        with pytest.raises(TransitionError) as exc_info:
            task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        err = exc_info.value
        assert err.code == "gate_failed"
        assert err.gate_name == "evidence_gate"
        assert "test coverage report" in err.message


# ---------------------------------------------------------------------------
# Task transitions — accepted → done
# ---------------------------------------------------------------------------


class TestTaskAcceptedToDone:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.accepted)
        result = task_accepted_to_done(task, now=_T1)
        assert result.status == TaskStatus.done
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.needs_review)
        with pytest.raises(TransitionError) as exc_info:
            task_accepted_to_done(task, now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — needs_review → rejected
# ---------------------------------------------------------------------------


class TestTaskNeedsReviewToRejected:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.needs_review)
        result = task_needs_review_to_rejected(
            task, reviewer="bob", reason="tests missing", now=_T1
        )
        assert result.status == TaskStatus.rejected
        assert any("Rejected by bob: tests missing" in n for n in result.implementation_notes)
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.done)
        with pytest.raises(TransitionError) as exc_info:
            task_needs_review_to_rejected(task, reviewer="bob", reason="bad", now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Task transitions — rejected → drafted
# ---------------------------------------------------------------------------


class TestTaskRejectedToDrafted:
    def test_happy_path(self) -> None:
        task = _make_task(status=TaskStatus.rejected)
        result = task_rejected_to_drafted(task, now=_T1)
        assert result.status == TaskStatus.drafted
        assert result.updated_at == _T1

    def test_wrong_status(self) -> None:
        task = _make_task(status=TaskStatus.done)
        with pytest.raises(TransitionError) as exc_info:
            task_rejected_to_drafted(task, now=_T1)
        assert exc_info.value.code == "wrong_status"


# ---------------------------------------------------------------------------
# Immutability: transitions return new instances (model_copy semantics)
# ---------------------------------------------------------------------------


class TestTransitionImmutability:
    def test_transitions_return_new_instance_not_mutated(self) -> None:
        """Original task.status is unchanged after transition (model_copy semantics)."""
        original = _make_task(status=TaskStatus.proposed)
        original_status = original.status
        original_id = id(original)

        result = task_proposed_to_drafted(original, now=_T1)

        # Status was NOT changed in place
        assert original.status == original_status
        assert original.status == TaskStatus.proposed
        # Result is a different object
        assert id(result) != original_id
        assert result.status == TaskStatus.drafted

    def test_prd_transition_returns_new_instance(self) -> None:
        original = _make_prd(status=PRDStatus.draft)
        result = prd_draft_to_reviewed(original, reviewer="alice", now=_T1)
        assert original.status == PRDStatus.draft
        assert result.status == PRDStatus.reviewed
        assert original is not result

    def test_implementation_notes_not_mutated(self) -> None:
        """task_in_progress_to_blocked appends a note without mutating the original list."""
        original = _make_task(status=TaskStatus.in_progress)
        original_notes = list(original.implementation_notes)

        result = task_in_progress_to_blocked(original, reason="waiting", now=_T1)

        assert original.implementation_notes == original_notes
        assert len(result.implementation_notes) == len(original_notes) + 1


# ---------------------------------------------------------------------------
# Evidence gate — substring membership
# ---------------------------------------------------------------------------


class TestEvidenceSubstringMembership:
    def test_required_evidence_substring_in_commands_run(self) -> None:
        """required_evidence item found as substring of commands_run entry → passes."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["pytest"]),
        )
        evidence = _make_evidence(commands_run=["pytest -x --cov=fakoli_state"])
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted

    def test_required_evidence_substring_in_files_changed(self) -> None:
        """required_evidence item found as substring of files_changed entry → passes."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["src/foo"]),
        )
        evidence = _make_evidence(files_changed=["src/foo.py", "tests/test_foo.py"])
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted

    def test_required_evidence_substring_in_output_excerpt(self) -> None:
        """required_evidence item found as substring of output_excerpt → passes."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["10 passed"]),
        )
        evidence = _make_evidence(output_excerpt="pytest output: 10 passed, 0 failed")
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted

    def test_required_evidence_not_found_fails(self) -> None:
        """required_evidence item NOT in any corpus field → evidence_gate fails."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["coverage.xml"]),
        )
        evidence = _make_evidence(
            commands_run=["pytest -x"],
            output_excerpt="10 passed",
        )
        with pytest.raises(TransitionError) as exc_info:
            task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert exc_info.value.gate_name == "evidence_gate"

    def test_evidence_gate_passes_with_empty_required_evidence(self) -> None:
        """No required_evidence → gate always passes."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=[]),
        )
        evidence = _make_evidence()  # also empty
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted

    def test_required_evidence_substring_in_pr_url(self) -> None:
        """required_evidence item found as substring of pr_url → passes."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["github.com/pr"]),
        )
        evidence = _make_evidence(pr_url="https://github.com/pr/42")
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted

    def test_required_evidence_substring_in_commit_sha(self) -> None:
        """required_evidence item found as substring of commit_sha → passes."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["abc123"]),
        )
        evidence = _make_evidence(commit_sha="abc123def456")
        result = task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        assert result.status == TaskStatus.accepted

    def test_multiple_required_evidence_all_must_match(self) -> None:
        """All items in required_evidence must be present — partial match is not enough."""
        task = _make_task(
            status=TaskStatus.needs_review,
            verification=Verification(required_evidence=["pytest", "coverage"]),
        )
        evidence = _make_evidence(commands_run=["pytest -x"])  # has pytest but not coverage
        with pytest.raises(TransitionError) as exc_info:
            task_needs_review_to_accepted(task, reviewer="alice", evidence=evidence, now=_T1)
        err = exc_info.value
        assert err.gate_name == "evidence_gate"
        assert "coverage" in err.message
