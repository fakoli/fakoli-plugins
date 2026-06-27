"""Shared fixtures for systems-thinking tests."""

from pathlib import Path

import pytest
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def parse_frontmatter(filepath: Path) -> tuple[dict, str]:
    """Read a Markdown file and parse its YAML frontmatter.

    Returns a tuple of (frontmatter_dict, body_text). The frontmatter is the
    YAML content between the first ``---`` and the second ``---``.  The body is
    everything after the closing ``---``.
    """
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text

    # Split on the second occurrence of '---'
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2]
    return frontmatter, body


@pytest.fixture
def plugin_root() -> Path:
    return PLUGIN_ROOT


@pytest.fixture
def agents_dir() -> Path:
    return PLUGIN_ROOT / "agents"


@pytest.fixture
def skills_dir() -> Path:
    return PLUGIN_ROOT / "skills"


@pytest.fixture
def settings_path() -> Path:
    return PLUGIN_ROOT / "hooks" / "hooks.json"


@pytest.fixture
def all_agent_files(agents_dir: Path) -> list[Path]:
    return sorted(agents_dir.glob("*.md"))


@pytest.fixture
def all_skill_files(skills_dir: Path) -> list[Path]:
    return sorted(skills_dir.glob("*/SKILL.md"))
