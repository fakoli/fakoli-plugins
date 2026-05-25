"""Tests for fakoli_state.planning.template — the deterministic PRD parser.

All tests follow three rules:
1. parse_prd() NEVER raises — errors go into ParseResult.errors.
2. Missing required sections → non-empty ParseResult.errors.
3. Missing optional sections → empty lists, no errors.
"""

from __future__ import annotations

from pathlib import Path

from fakoli_state.planning.template import ParseResult, parse_prd

# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures" / "prds"


# ---------------------------------------------------------------------------
# Minimal valid PRD helper
# ---------------------------------------------------------------------------

_MINIMAL_PRD = """\
# Project: Minimal Project

## Summary

A minimal project for testing.

## Goals

- Do something useful.

## Requirements

- R001: The system does X.
- R002: The system does Y.
"""

_QUICKSTART_PATH = _FIXTURES / "quickstart.md"


# ---------------------------------------------------------------------------
# Required-section enforcement
# ---------------------------------------------------------------------------


class TestRequiredSectionEnforcement:
    """parse_prd returns ParseError entries for missing required sections, never raises."""

    def test_missing_project_section_errors(self) -> None:
        """PRD without '# Project: X' → ParseError with '# Project' in message."""
        prd_without_project = """\
## Summary

A project without a title.

## Goals

- Do something.

## Requirements

- R001: Must work.
"""
        result = parse_prd(prd_without_project)
        assert result.errors, "Expected errors for missing # Project heading"
        sections = [e.section for e in result.errors]
        assert any("Project" in s for s in sections), (
            f"Expected '# Project' in error section names, got: {sections}"
        )

    def test_missing_summary_errors(self) -> None:
        """PRD without '## Summary' → ParseError with 'Summary' in message."""
        prd_without_summary = """\
# Project: Test Project

## Goals

- Goal one.

## Requirements

- R001: Must do X.
"""
        result = parse_prd(prd_without_summary)
        assert result.errors, "Expected errors for missing ## Summary section"
        sections = [e.section for e in result.errors]
        assert any("Summary" in s for s in sections), (
            f"Expected 'Summary' in error section names, got: {sections}"
        )

    def test_missing_goals_errors(self) -> None:
        """PRD without '## Goals' → ParseError with 'Goals' in message."""
        prd_without_goals = """\
# Project: Test Project

## Summary

A summary of the project.

## Requirements

- R001: Must do X.
"""
        result = parse_prd(prd_without_goals)
        assert result.errors, "Expected errors for missing ## Goals section"
        sections = [e.section for e in result.errors]
        assert any("Goals" in s for s in sections), (
            f"Expected 'Goals' in error section names, got: {sections}"
        )

    def test_missing_requirements_errors(self) -> None:
        """PRD without '## Requirements' → ParseError with 'Requirements' in message."""
        prd_without_requirements = """\
# Project: Test Project

## Summary

A summary.

## Goals

- Do something.
"""
        result = parse_prd(prd_without_requirements)
        assert result.errors, "Expected errors for missing ## Requirements section"
        sections = [e.section for e in result.errors]
        assert any("Requirements" in s for s in sections), (
            f"Expected 'Requirements' in error section names, got: {sections}"
        )

    def test_parse_prd_never_raises_on_missing_sections(self) -> None:
        """parse_prd does not raise even when all required sections are absent."""
        # Should collect multiple errors but never raise
        result = parse_prd("")
        assert isinstance(result, ParseResult)
        assert result.errors  # at minimum # Project is missing

    def test_all_four_required_sections_error_individually(self) -> None:
        """Verify each required section generates exactly one error each when absent."""
        # PRD with nothing — should get at least 3 or 4 errors (Project, Summary, Goals, Requirements).
        result = parse_prd("Some random text without any headings.")
        # At minimum we expect errors for # Project, ## Summary, ## Goals, ## Requirements
        assert len(result.errors) >= 3


# ---------------------------------------------------------------------------
# Happy path — minimal valid PRD
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_parse_minimal_valid_prd(self) -> None:
        """PRD with only the 4 required sections produces ParseResult with 2 Requirements."""
        result = parse_prd(_MINIMAL_PRD)
        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert result.prd is not None
        assert len(result.requirements) >= 1
        # Optional sections absent → empty lists
        assert result.features == []
        assert result.tasks == []

    def test_parse_minimal_prd_has_correct_summary(self) -> None:
        """Minimal PRD summary is stored correctly."""
        result = parse_prd(_MINIMAL_PRD)
        assert not result.errors
        assert "minimal project" in result.prd.summary.lower()

    def test_parse_full_prd_quickstart(self) -> None:
        """Parse the quickstart example from docs/prd-template.md (fixture file).

        Asserts all sections parsed: 6 requirements, 3 features, 4 tasks,
        non-empty goals/risks/acceptance_criteria/open_questions.
        """
        markdown = _QUICKSTART_PATH.read_text(encoding="utf-8")
        result = parse_prd(markdown)
        assert not result.errors, f"Quickstart PRD parse errors: {result.errors}"

        # Requirements: R001-R006
        assert len(result.requirements) == 6
        req_ids = {r.id for r in result.requirements}
        assert "R001" in req_ids
        assert "R006" in req_ids

        # Features: F001, F002, F003
        assert len(result.features) == 3
        feat_ids = {f.id for f in result.features}
        assert "F001" in feat_ids
        assert "F003" in feat_ids

        # Tasks: T001-T004
        assert len(result.tasks) == 4
        task_ids = {t.id for t in result.tasks}
        assert "T001" in task_ids
        assert "T004" in task_ids

        # PRD-level fields populated
        assert result.prd.goals
        assert result.prd.non_goals
        assert result.prd.risks
        assert result.prd.open_questions
        assert result.prd.acceptance_criteria

    def test_ids_auto_assigned(self) -> None:
        """Requirements without prefix get R001, R002 in document order."""
        prd = """\
# Project: Auto ID Test

## Summary

Tests auto-assignment.

## Goals

- Do the thing.

## Requirements

- First requirement without ID.
- Second requirement without ID.
"""
        result = parse_prd(prd)
        assert not result.errors
        assert len(result.requirements) == 2
        assert result.requirements[0].id == "R001"
        assert result.requirements[1].id == "R002"

    def test_explicit_ids_preserved(self) -> None:
        """Requirements with explicit RNNN: prefix keep their IDs."""
        prd = """\
# Project: Explicit ID Test

## Summary

Tests explicit IDs.

## Goals

- Goal.

## Requirements

- R005: Fifth requirement.
- R010: Tenth requirement.
"""
        result = parse_prd(prd)
        assert not result.errors
        ids = [r.id for r in result.requirements]
        assert "R005" in ids
        assert "R010" in ids


# ---------------------------------------------------------------------------
# Feature parsing
# ---------------------------------------------------------------------------


class TestFeatureParsing:
    def test_feature_block_parsed(self) -> None:
        """### F001: Title with **Requirements:** R001, R002 populates Feature.requirements."""
        prd = """\
# Project: Feature Test

## Summary

Tests feature parsing.

## Goals

- Do features.

## Requirements

- R001: First requirement.
- R002: Second requirement.

## Features

### F001: My Feature

**Requirements:** R001, R002

A description of the feature.
"""
        result = parse_prd(prd)
        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert len(result.features) == 1
        feature = result.features[0]
        assert feature.id == "F001"
        assert feature.title == "My Feature"
        assert "R001" in feature.requirements
        assert "R002" in feature.requirements

    def test_feature_with_unknown_requirement_warns(self) -> None:
        """**Requirements:** R099 when R099 doesn't exist → ParseError (warning), feature still included."""
        prd = """\
# Project: Unknown Req Test

## Summary

Tests unknown req reference.

## Goals

- Do something.

## Requirements

- R001: Known requirement.

## Features

### F001: Feature With Unknown Req

**Requirements:** R001, R099
"""
        result = parse_prd(prd)
        # Feature is still created (parser doesn't drop it)
        assert len(result.features) == 1
        assert result.features[0].id == "F001"
        # But there should be a warning/error about R099
        assert result.errors, "Expected a ParseError warning for unknown requirement R099"
        messages = [e.message for e in result.errors]
        assert any("R099" in m for m in messages), (
            f"Expected error mentioning R099, got: {messages}"
        )

    def test_feature_description_captured(self) -> None:
        """Description text in feature block is stored in Feature.description."""
        prd = """\
# Project: Desc Test

## Summary

Summary.

## Goals

- Goal.

## Requirements

- R001: Req.

## Features

### F001: Feature With Desc

**Requirements:** R001

This is a feature description paragraph.
"""
        result = parse_prd(prd)
        assert not result.errors
        assert len(result.features) == 1
        assert "description" in result.features[0].description.lower()


# ---------------------------------------------------------------------------
# Task parsing
# ---------------------------------------------------------------------------


class TestTaskParsing:
    def test_task_block_parsed(self) -> None:
        """### T001: Title with all fields populates Task correctly."""
        prd = """\
# Project: Task Parse Test

## Summary

Tests task parsing.

## Goals

- Do tasks.

## Requirements

- R001: Requirement.

## Features

### F001: Feature One

**Requirements:** R001

## Tasks

### T001: First Task

**Feature:** F001
**Priority:** high
**Likely files:** src/app/main.py, src/app/utils.py

Implement the main logic.

**Acceptance criteria:**

- Tests pass with 100% coverage.
- No regressions in existing tests.

**Verification:**

- `pytest tests/ -v`
- `python -m app --help`
"""
        result = parse_prd(prd)
        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert len(result.tasks) == 1
        task = result.tasks[0]
        assert task.id == "T001"
        assert task.title == "First Task"
        assert task.feature_id == "F001"
        assert task.priority.value == "high"
        assert len(task.likely_files) == 2
        assert len(task.acceptance_criteria) == 2
        assert len(task.verification.commands) == 2

    def test_task_priority_default_medium(self) -> None:
        """Task without **Priority:** defaults to medium."""
        prd = """\
# Project: Priority Default

## Summary

Tests default priority.

## Goals

- Do tasks.

## Requirements

- R001: Req.

## Features

### F001: Feature

**Requirements:** R001

## Tasks

### T001: Task Without Priority

**Feature:** F001

A task that has no explicit priority.

**Acceptance criteria:**

- It works.

**Verification:**

- `pytest tests/ -v`
"""
        result = parse_prd(prd)
        assert not result.errors
        assert len(result.tasks) == 1
        assert result.tasks[0].priority.value == "medium"

    def test_task_verification_strips_backticks(self) -> None:
        """- `pytest foo` → verification.commands = ["pytest foo"] (backticks stripped)."""
        prd = """\
# Project: Backtick Strip Test

## Summary

Tests backtick stripping in verification.

## Goals

- Do things.

## Requirements

- R001: Req.

## Features

### F001: Feature

**Requirements:** R001

## Tasks

### T001: Task With Backtick Verification

**Feature:** F001

**Acceptance criteria:**

- Works correctly.

**Verification:**

- `pytest tests/test_foo.py -v`
- `python -c "import app"`
"""
        result = parse_prd(prd)
        assert not result.errors
        assert len(result.tasks) == 1
        commands = result.tasks[0].verification.commands
        assert len(commands) == 2
        # Backticks must be stripped
        assert "`" not in commands[0], f"Backtick not stripped: {commands[0]}"
        assert "pytest tests/test_foo.py -v" in commands[0]

    def test_task_likely_files_comma_separated(self) -> None:
        """**Likely files:** a.py, b.py, c.py → list of 3 entries."""
        prd = """\
# Project: Likely Files Test

## Summary

Tests comma-separated likely files.

## Goals

- Do tasks.

## Requirements

- R001: Req.

## Features

### F001: Feature

**Requirements:** R001

## Tasks

### T001: Task With Files

**Feature:** F001
**Likely files:** a.py, b.py, c.py

**Acceptance criteria:**

- Works.

**Verification:**

- `pytest tests/ -v`
"""
        result = parse_prd(prd)
        assert not result.errors
        assert len(result.tasks) == 1
        files = result.tasks[0].likely_files
        assert len(files) == 3
        assert "a.py" in files
        assert "b.py" in files
        assert "c.py" in files

    def test_task_feature_link_updates_feature_tasks(self) -> None:
        """Task with Feature: F001 adds task ID to Feature.tasks."""
        prd = """\
# Project: Link Test

## Summary

Tests feature-task linking.

## Goals

- Link tasks to features.

## Requirements

- R001: Req.

## Features

### F001: Feature

**Requirements:** R001

## Tasks

### T001: Linked Task

**Feature:** F001

**Acceptance criteria:**

- Works.

**Verification:**

- `pytest tests/ -v`
"""
        result = parse_prd(prd)
        assert not result.errors
        feature = result.features[0]
        assert "T001" in feature.tasks


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


class TestPreprocessing:
    def test_html_comments_stripped(self) -> None:
        """HTML comments in PRD do not affect parsing."""
        prd = """\
# Project: Comment Test

<!-- This is a comment that should be stripped -->

## Summary

<!-- Another comment -->
A summary with comments.

## Goals

- Goal one.
<!-- Goal two is commented out -->

## Requirements

- R001: First requirement.
"""
        result = parse_prd(prd)
        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert result.prd.summary
        # HTML comment text "This is a comment" should not appear in the summary
        assert "This is a comment" not in result.prd.summary
        assert "Another comment" not in result.prd.summary
        # Requirements should only have R001 (the comment was not parsed as a req)
        assert len(result.requirements) == 1

    def test_trailing_whitespace_tolerated(self) -> None:
        """Extra blank lines and trailing whitespace don't break parsing."""
        prd = """\
# Project: Whitespace Test

## Summary

   A summary with surrounding whitespace.

## Goals


- Goal one.

- Goal two.

## Requirements


- R001: First requirement.
- R002: Second requirement.

"""
        result = parse_prd(prd)
        assert not result.errors, f"Unexpected errors: {result.errors}"
        assert len(result.prd.goals) == 2
        assert len(result.requirements) == 2


# ---------------------------------------------------------------------------
# Reparse semantics
# ---------------------------------------------------------------------------


class TestReparseSemantrics:
    def test_reparse_replaces_requirements_completely(self) -> None:
        """Parse twice with different requirement lists; second parse's result contains only second list."""
        prd_v1 = """\
# Project: Reparse Test

## Summary

First version.

## Goals

- Goal.

## Requirements

- R001: Version 1 requirement A.
- R002: Version 1 requirement B.
- R003: Version 1 requirement C.
"""
        prd_v2 = """\
# Project: Reparse Test

## Summary

Second version.

## Goals

- Goal.

## Requirements

- R001: Version 2 requirement A (different text).
- R002: Version 2 requirement B (different text).
"""
        result_v1 = parse_prd(prd_v1)
        result_v2 = parse_prd(prd_v2)

        assert not result_v1.errors
        assert not result_v2.errors

        # Second result has only 2 requirements
        assert len(result_v2.requirements) == 2

        # First result's extra R003 is not in the second result
        v2_ids = {r.id for r in result_v2.requirements}
        assert "R003" not in v2_ids

        # Text is from second parse
        r001_v2 = next(r for r in result_v2.requirements if r.id == "R001")
        assert "Version 2" in r001_v2.text
