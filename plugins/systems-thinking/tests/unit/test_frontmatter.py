"""Tests for YAML frontmatter in agent and skill Markdown files."""

import re

import pytest

from tests.conftest import PLUGIN_ROOT, parse_frontmatter

AGENTS_DIR = PLUGIN_ROOT / "agents"
SKILLS_DIR = PLUGIN_ROOT / "skills"

AGENT_FILES = sorted(AGENTS_DIR.glob("*.md"))
SKILL_FILES = sorted(SKILLS_DIR.glob("*/SKILL.md"))

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _ids_agents(paths):
    return [p.stem for p in paths]


def _ids_skills(paths):
    return [p.parent.name for p in paths]


# ── Frontmatter presence ─────────────────────────────────────────────────────


def test_all_agents_have_frontmatter():
    for path in AGENT_FILES:
        fm, _ = parse_frontmatter(path)
        assert fm, f"{path.name} has no YAML frontmatter"


def test_all_skills_have_frontmatter():
    for path in SKILL_FILES:
        fm, _ = parse_frontmatter(path)
        assert fm, f"{path.parent.name}/SKILL.md has no YAML frontmatter"


# ── Required fields ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=_ids_agents(AGENT_FILES))
def test_agent_frontmatter_has_required_fields(agent_file):
    fm, _ = parse_frontmatter(agent_file)
    assert "name" in fm, f"{agent_file.name} missing 'name'"
    assert "description" in fm, f"{agent_file.name} missing 'description'"


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=_ids_skills(SKILL_FILES))
def test_skill_frontmatter_has_required_fields(skill_file):
    fm, _ = parse_frontmatter(skill_file)
    assert "description" in fm, f"{skill_file.parent.name}/SKILL.md missing 'description'"


# ── Naming conventions ───────────────────────────────────────────────────────


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=_ids_agents(AGENT_FILES))
def test_agent_names_are_kebab_case(agent_file):
    """Agent frontmatter 'name' must be kebab-case."""
    fm, _ = parse_frontmatter(agent_file)
    name = fm.get("name", "")
    assert KEBAB_RE.match(name), f"{agent_file.name}: name '{name}' is not kebab-case"


# ── Description quality ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "md_file",
    AGENT_FILES + SKILL_FILES,
    ids=_ids_agents(AGENT_FILES) + _ids_skills(SKILL_FILES),
)
def test_frontmatter_descriptions_are_nonempty(md_file):
    fm, _ = parse_frontmatter(md_file)
    desc = fm.get("description", "")
    assert desc and str(desc).strip(), f"{md_file.name} has an empty description"


# ── Tool scoping ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=_ids_agents(AGENT_FILES))
def test_agent_frontmatter_has_allowed_tools(agent_file):
    """Each agent must declare its allowed tools as a list under 'allowed-tools'."""
    fm, _ = parse_frontmatter(agent_file)
    tools_key = next(
        (k for k in ("allowed-tools", "allowed_tools", "tools") if k in fm),
        None,
    )
    assert tools_key is not None, f"{agent_file.name} missing 'allowed-tools', 'allowed_tools', or 'tools'"
    assert isinstance(fm[tools_key], list), f"{agent_file.name}: {tools_key} should be a list"


# ── Regression: no non-standard fields ──────────────────────────────────────


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=_ids_skills(SKILL_FILES))
def test_skill_frontmatter_has_no_trigger_field(skill_file):
    """trigger is non-standard and silently ignored by Claude Code."""
    fm, _ = parse_frontmatter(skill_file)
    assert "trigger" not in fm, (
        f"{skill_file.parent.name}/SKILL.md has non-standard 'trigger' field — "
        "move trigger phrases into the 'description' field"
    )


# ── Description quality: minimum length ─────────────────────────────────────


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=_ids_skills(SKILL_FILES))
def test_skill_descriptions_are_long_enough(skill_file):
    """Skill descriptions must be >= 250 chars for reliable auto-matching."""
    fm, _ = parse_frontmatter(skill_file)
    desc = str(fm.get("description", "")).strip()
    assert len(desc) >= 250, (
        f"{skill_file.parent.name}: description is {len(desc)} chars, need >= 250 for reliable triggering"
    )
