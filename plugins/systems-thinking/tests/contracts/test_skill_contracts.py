"""Tests that skill files meet the systems-thinking spec."""

import re

import pytest

from tests.conftest import PLUGIN_ROOT, parse_frontmatter

SKILLS_DIR = PLUGIN_ROOT / "skills"

SKILL_DIRS = [
    "pattern-remix",
    "complexity-mapper",
    "context-sharding",
    "decision-brief",
    "architecture-risk-review",
]

AGENT_NAMES = [
    "doc-indexer",
    "doc-reader",
    "caveat-extractor",
    "cost-capacity-analyst",
    "architecture-dependency-mapper",
    "pattern-remix-planner",
    "synthesis-brief-writer",
]


def _skill_path(skill_dir):
    return SKILLS_DIR / skill_dir / "SKILL.md"


def _read_body(skill_dir):
    _, body = parse_frontmatter(_skill_path(skill_dir))
    return body


# ── When-to-use guidance ─────────────────────────────────────────────────────


@pytest.mark.parametrize("skill_dir", SKILL_DIRS)
def test_skills_have_when_to_use(skill_dir):
    body = _read_body(skill_dir).lower()
    assert "when to use" in body or "## when" in body, f"{skill_dir} missing 'When to Use' section"


# ── Inputs section ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("skill_dir", SKILL_DIRS)
def test_skills_have_inputs_section(skill_dir):
    body = _read_body(skill_dir).lower()
    assert "input" in body, f"{skill_dir} does not mention inputs"


# ── Process steps ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("skill_dir", SKILL_DIRS)
def test_skills_have_process_steps(skill_dir):
    """Skills should describe their process as numbered steps or a Process section."""
    body = _read_body(skill_dir)
    has_numbered_steps = bool(re.search(r"^\s*\d+\.\s", body, re.MULTILINE))
    has_process_heading = bool(re.search(r"^#{2,3}\s+(Process|Steps)", body, re.MULTILINE))
    assert has_numbered_steps or has_process_heading, (
        f"{skill_dir} missing numbered steps or ## Process/Steps section"
    )


# ── Output format ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("skill_dir", SKILL_DIRS)
def test_skills_have_output_format(skill_dir):
    """Skills should specify their output format or reference an output contract."""
    body = _read_body(skill_dir).lower()
    assert "output" in body, f"{skill_dir} does not mention output format or output contract"


# ── Failure modes ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("skill_dir", SKILL_DIRS)
def test_skills_have_failure_modes(skill_dir):
    """Skills should mention failure modes, cautions, or warnings."""
    body = _read_body(skill_dir).lower()
    keywords = ["failure", "caution", "warning"]
    found = [kw for kw in keywords if kw in body]
    assert found, f"{skill_dir} should mention at least one of: {keywords}"


# ── Agent references ────────────────────────────────────────────────────────


@pytest.mark.parametrize("skill_dir", SKILL_DIRS)
def test_skills_reference_agents(skill_dir):
    """Every skill should reference at least one agent by name."""
    body = _read_body(skill_dir).lower()
    referenced = [name for name in AGENT_NAMES if name in body]
    assert referenced, (
        f"{skill_dir} does not reference any agent. Expected at least one of: {AGENT_NAMES}"
    )
