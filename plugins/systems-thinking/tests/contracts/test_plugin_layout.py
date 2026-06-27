"""Tests that the expected plugin directory structure exists."""

import json

import pytest

EXPECTED_AGENTS = [
    "doc-indexer.md",
    "doc-reader.md",
    "caveat-extractor.md",
    "cost-capacity-analyst.md",
    "architecture-dependency-mapper.md",
    "pattern-remix-planner.md",
    "synthesis-brief-writer.md",
]

EXPECTED_SKILL_DIRS = [
    "pattern-remix",
    "complexity-mapper",
    "context-sharding",
    "decision-brief",
    "architecture-risk-review",
]

EXPECTED_DOCS = [
    "output-contracts.md",
    "agent-design-principles.md",
    "repo-conventions.md",
]

EXPECTED_REFERENCE_SUBDIRS = [
    "previous_designs",
    "vendor_docs",
    "prompts",
    "examples",
]


# ── Marketplace structure ──────────────────────────────────────────────────


def test_plugin_manifest_exists(plugin_root):
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    assert manifest.is_file(), ".claude-plugin/plugin.json is missing"


def test_plugin_manifest_is_valid_json(plugin_root):
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "name" in data, "plugin.json missing 'name'"
    assert "description" in data, "plugin.json missing 'description'"
    assert "version" in data, "plugin.json missing 'version'"


# ── Top-level directories ───────────────────────────────────────────────────


def test_agents_dir_exists(agents_dir):
    assert agents_dir.is_dir()


def test_skills_dir_exists(skills_dir):
    assert skills_dir.is_dir()


def test_hooks_dir_exists(plugin_root):
    assert (plugin_root / "hooks").is_dir()


def test_hooks_json_exists(settings_path):
    assert settings_path.is_file()


def test_claude_md_exists(plugin_root):
    assert (plugin_root / "CLAUDE.md").is_file()


def test_readme_exists(plugin_root):
    assert (plugin_root / "README.md").is_file()


def test_docs_dir_exists(plugin_root):
    assert (plugin_root / "docs").is_dir()


def test_specs_dir_exists(plugin_root):
    assert (plugin_root / "specs").is_dir()


def test_reference_dir_exists(plugin_root):
    assert (plugin_root / "reference").is_dir()


def test_compatibility_notes_exists(plugin_root):
    assert (plugin_root / "COMPATIBILITY_NOTES.md").is_file()


# ── Reference subdirectories ───────────────────────────────────────────────


@pytest.mark.parametrize("subdir", EXPECTED_REFERENCE_SUBDIRS)
def test_reference_subdirs_exist(plugin_root, subdir):
    assert (plugin_root / "reference" / subdir).is_dir(), (
        f"reference/{subdir}/ directory is missing"
    )


# ── Expected files ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("filename", EXPECTED_AGENTS)
def test_expected_agent_files_exist(agents_dir, filename):
    assert (agents_dir / filename).is_file(), f"Agent file {filename} is missing"


@pytest.mark.parametrize("skill_dir", EXPECTED_SKILL_DIRS)
def test_expected_skill_dirs_exist(skills_dir, skill_dir):
    skill_file = skills_dir / skill_dir / "SKILL.md"
    assert skill_file.is_file(), f"Skill file skills/{skill_dir}/SKILL.md is missing"


@pytest.mark.parametrize("filename", EXPECTED_DOCS)
def test_docs_files_exist(plugin_root, filename):
    assert (plugin_root / "docs" / filename).is_file(), f"docs/{filename} is missing"
