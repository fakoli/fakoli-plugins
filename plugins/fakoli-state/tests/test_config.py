"""Tests for fakoli_state.config — Config loading, validation, and template generation.

Coverage targets:
- load_config() happy path with defaults
- load_config() missing required fields raises ValueError
- load_config() invalid literal field raises ValueError
- config_template() returns parseable YAML
- write_default_config() creates a valid config file
- write_default_config() raises FileExistsError on existing file
- Path resolution for db_path and events_path
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from fakoli_state.config import Config, config_template, load_config, write_default_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(path: Path, content: str) -> Path:
    """Write a YAML string to path and return the path."""
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_yaml(
    project_name: str = "Test Project",
    project_id: str = "test-id",
) -> str:
    return f"""\
project_name: {project_name!r}
project_id: {project_id!r}
"""


# ---------------------------------------------------------------------------
# load_config — happy path
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_default_config(self, tmp_path: Path) -> None:
        """write_default_config then load_config returns Config with expected fields."""
        config_path = tmp_path / "config.yaml"
        write_default_config(config_path, project_name="My Project")
        cfg = load_config(config_path)

        assert isinstance(cfg, Config)
        assert cfg.project_name == "My Project"
        assert isinstance(cfg.project_id, str)
        # The project_id should be a UUID4
        uuid.UUID(cfg.project_id)  # raises ValueError if not valid UUID
        assert cfg.default_lease_minutes == 60
        assert cfg.default_heartbeat_minutes == 5
        assert cfg.git_ops_mode == "auto"
        assert cfg.sync_github_enabled is False
        assert cfg.sync_github_conflict_strategy == "prompt"

    def test_load_config_with_minimal_yaml(self, tmp_path: Path) -> None:
        """Minimal config (only required fields) loads with defaults applied."""
        config_path = _write_config(tmp_path / "config.yaml", _minimal_yaml())
        cfg = load_config(config_path)
        assert cfg.project_name == "Test Project"
        assert cfg.project_id == "test-id"
        assert cfg.llm_provider is None
        assert cfg.llm_model is None

    def test_load_config_returns_frozen_config(self, tmp_path: Path) -> None:
        """Config is frozen (dataclass frozen=True) — assignment raises FrozenInstanceError."""
        import dataclasses

        config_path = _write_config(tmp_path / "config.yaml", _minimal_yaml())
        cfg = load_config(config_path)
        assert dataclasses.is_dataclass(cfg)
        # frozen=True means __setattr__ raises FrozenInstanceError (subclass of AttributeError)
        with pytest.raises((AttributeError, TypeError)):
            # setattr bypasses mypy's assignment check and triggers the frozen guard
            cfg.project_name = "mutate me"

    def test_load_config_accepts_path_object(self, tmp_path: Path) -> None:
        """load_config accepts a pathlib.Path argument."""
        config_path = _write_config(tmp_path / "config.yaml", _minimal_yaml())
        cfg = load_config(config_path)  # Path object, not str
        assert cfg.project_name == "Test Project"

    def test_load_config_accepts_string_path(self, tmp_path: Path) -> None:
        """load_config accepts a string path argument."""
        config_path = _write_config(tmp_path / "config.yaml", _minimal_yaml())
        cfg = load_config(str(config_path))  # string, not Path
        assert cfg.project_name == "Test Project"

    def test_load_config_resolves_db_path_relative(self, tmp_path: Path) -> None:
        """db_path is resolved relative to the config file's directory."""
        yaml_content = _minimal_yaml() + "db_path: my_state.db\n"
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        cfg = load_config(config_path)
        expected = str(tmp_path / "my_state.db")
        assert cfg.db_path == expected

    def test_load_config_resolves_events_path_relative(self, tmp_path: Path) -> None:
        """events_path is resolved relative to the config file's directory."""
        yaml_content = _minimal_yaml() + "events_path: my_events.jsonl\n"
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        cfg = load_config(config_path)
        expected = str(tmp_path / "my_events.jsonl")
        assert cfg.events_path == expected

    def test_load_config_all_fields(self, tmp_path: Path) -> None:
        """Config with all optional fields set loads correctly."""
        yaml_content = """\
project_name: 'Full Config Project'
project_id: 'full-config-id'
llm_provider: 'anthropic'
llm_model: 'claude-sonnet-4-6'
default_lease_minutes: 120
default_heartbeat_minutes: 10
git_ops_mode: record_only
sync_github_enabled: true
sync_github_conflict_strategy: local_wins
"""
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        cfg = load_config(config_path)
        assert cfg.llm_provider == "anthropic"
        assert cfg.llm_model == "claude-sonnet-4-6"
        assert cfg.default_lease_minutes == 120
        assert cfg.default_heartbeat_minutes == 10
        assert cfg.git_ops_mode == "record_only"
        assert cfg.sync_github_enabled is True
        assert cfg.sync_github_conflict_strategy == "local_wins"


# ---------------------------------------------------------------------------
# load_config — validation failures
# ---------------------------------------------------------------------------


class TestLoadConfigErrors:
    def test_load_config_missing_project_name(self, tmp_path: Path) -> None:
        """YAML with missing project_name raises ValueError."""
        yaml_content = "project_id: 'some-id'\n"
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        with pytest.raises(ValueError, match="project_name"):
            load_config(config_path)

    def test_load_config_missing_project_id(self, tmp_path: Path) -> None:
        """YAML with missing project_id raises ValueError."""
        yaml_content = "project_name: 'Some Project'\n"
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        with pytest.raises(ValueError, match="project_id"):
            load_config(config_path)

    def test_load_config_blank_project_name_raises(self, tmp_path: Path) -> None:
        """Blank project_name ('') raises ValueError."""
        yaml_content = "project_name: ''\nproject_id: 'some-id'\n"
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        with pytest.raises(ValueError, match="project_name"):
            load_config(config_path)

    def test_load_config_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        """Non-existent config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_config_invalid_git_ops_mode(self, tmp_path: Path) -> None:
        """Invalid git_ops_mode value raises ValueError."""
        yaml_content = _minimal_yaml() + "git_ops_mode: invalid_mode\n"
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        with pytest.raises(ValueError, match="git_ops_mode"):
            load_config(config_path)

    def test_load_config_invalid_conflict_strategy(self, tmp_path: Path) -> None:
        """Invalid sync_github_conflict_strategy raises ValueError."""
        yaml_content = _minimal_yaml() + "sync_github_conflict_strategy: bad_strategy\n"
        config_path = _write_config(tmp_path / "config.yaml", yaml_content)
        with pytest.raises(ValueError, match="sync_github_conflict_strategy"):
            load_config(config_path)

    def test_load_config_non_dict_yaml_raises(self, tmp_path: Path) -> None:
        """YAML that is not a mapping (e.g. a list) raises ValueError."""
        config_path = _write_config(tmp_path / "config.yaml", "- item1\n- item2\n")
        with pytest.raises(ValueError, match="mapping"):
            load_config(config_path)


# ---------------------------------------------------------------------------
# write_default_config
# ---------------------------------------------------------------------------


class TestWriteDefaultConfig:
    def test_write_creates_valid_config(self, tmp_path: Path) -> None:
        """write_default_config creates a YAML file that load_config can read."""
        config_path = tmp_path / "config.yaml"
        write_default_config(config_path, project_name="Written Project")
        assert config_path.exists()
        cfg = load_config(config_path)
        assert cfg.project_name == "Written Project"

    def test_write_generates_unique_project_id(self, tmp_path: Path) -> None:
        """write_default_config generates a UUID4 project_id."""
        config_path = tmp_path / "config.yaml"
        write_default_config(config_path, project_name="UUID Test")
        cfg = load_config(config_path)
        # Should be a valid UUID
        parsed = uuid.UUID(cfg.project_id)
        assert parsed.version == 4

    def test_write_raises_if_file_exists(self, tmp_path: Path) -> None:
        """write_default_config raises FileExistsError if file already exists."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("existing content", encoding="utf-8")
        with pytest.raises(FileExistsError):
            write_default_config(config_path, project_name="Test")

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """write_default_config creates parent directories if they don't exist."""
        config_path = tmp_path / "nested" / "dir" / "config.yaml"
        write_default_config(config_path, project_name="Deep Project")
        assert config_path.exists()


# ---------------------------------------------------------------------------
# config_template
# ---------------------------------------------------------------------------


class TestConfigTemplate:
    def test_config_template_yaml_valid(self) -> None:
        """config_template() returns parseable YAML."""
        template = config_template()
        parsed = yaml.safe_load(template)
        assert isinstance(parsed, dict)

    def test_config_template_default_project_name(self) -> None:
        """config_template() uses default project_name='my-project'."""
        template = config_template()
        parsed = yaml.safe_load(template)
        assert parsed.get("project_name") == "my-project"

    def test_config_template_custom_project_name(self) -> None:
        """config_template(project_name=...) uses the given name."""
        template = config_template(project_name="Custom Name")
        parsed = yaml.safe_load(template)
        assert parsed.get("project_name") == "Custom Name"

    def test_config_template_has_required_fields(self) -> None:
        """Template YAML includes project_name and project_id."""
        template = config_template()
        parsed = yaml.safe_load(template)
        assert "project_name" in parsed
        assert "project_id" in parsed

    def test_config_template_generates_fresh_uuid_each_call(self) -> None:
        """config_template() generates a different project_id each call."""
        t1 = yaml.safe_load(config_template())
        t2 = yaml.safe_load(config_template())
        # UUIDs should differ
        assert t1.get("project_id") != t2.get("project_id")

    def test_config_template_can_be_loaded_by_load_config(self, tmp_path: Path) -> None:
        """A template written to disk can be read by load_config without error."""
        template = config_template(project_name="Template Project")
        config_path = tmp_path / "config.yaml"
        config_path.write_text(template, encoding="utf-8")
        cfg = load_config(config_path)
        assert cfg.project_name == "Template Project"
