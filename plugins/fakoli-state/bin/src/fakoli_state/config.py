"""Config loader for fakoli-state.

Reads a config.yaml file and returns a frozen Config dataclass.
Also provides write_default_config() and config_template() for the
`fakoli-state init` command to scaffold a starter config.

All fields are minimal for Phase 2; extend in later phases without
breaking existing callers (add keyword-only args with defaults only).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass(frozen=True)
class Config:
    """Parsed representation of config.yaml.

    Frozen so that callers cannot accidentally mutate it.  All fields have
    sensible defaults so that minimal configs work without specifying every key.
    """

    project_name: str
    project_id: str

    llm_provider: str | None = None
    llm_model: str | None = None

    default_lease_minutes: int = 60
    default_heartbeat_minutes: int = 5

    git_ops_mode: Literal["auto", "record_only", "off"] = "auto"

    sync_github_enabled: bool = False
    sync_github_conflict_strategy: Literal[
        "local_wins", "remote_wins", "prompt", "manual_merge"
    ] = "prompt"

    # Phase 9 T5 — multi-provider sync.
    #
    # ``sync_providers`` is the contents of the optional top-level
    # ``sync.providers`` YAML key. When ``None`` (key absent), every caller
    # that asks "which providers are configured?" SHOULD fall back to
    # ``sorted(fakoli_state.sync.registry.PROVIDER_REGISTRY)`` — i.e. the
    # full set of registered providers, matching v1.8.0 behaviour. When the
    # operator pins an explicit list, ``ReconciliationEngine`` and the
    # generic ``sync provider`` dispatch scope to that allow-list — useful
    # for projects that have multiple providers registered (github_issues,
    # linear, monday, …) but only want some of them to count toward
    # ``missing_sync_mapping`` discrepancies.
    #
    # An empty list (``sync.providers: []``) is preserved as-is — that
    # explicitly opts out of every provider (e.g. for a frozen project
    # that should no longer surface sync drift). Callers MUST disambiguate
    # ``None`` (use the registry) from ``[]`` (use nothing).
    sync_providers: tuple[str, ...] | None = None

    # Paths (resolved at load time to absolute strings).
    db_path: str = field(default="")
    events_path: str = field(default="")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> Config:
    """Parse config.yaml at *path* and return a Config instance.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If required fields (project_name, project_id) are absent or blank,
        or if an enum-typed field has an invalid value.
    yaml.YAMLError
        If the file is not valid YAML.
    """
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"Config file not found: {resolved}. "
            "Run `fakoli-state init` to create one."
        )

    with resolved.open(encoding="utf-8") as fh:
        raw: object = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Config file {resolved} must be a YAML mapping, got {type(raw).__name__!r}."
        )

    data: dict[str, object] = raw
    _validate_required(data, resolved)

    # Resolve paths relative to the config file's directory.
    config_dir = resolved.parent
    db_path = _resolve_path(data.get("db_path", "state.db"), config_dir)
    events_path = _resolve_path(data.get("events_path", "events.jsonl"), config_dir)

    git_ops_mode = _validate_literal(
        data.get("git_ops_mode", "auto"),
        ("auto", "record_only", "off"),
        "git_ops_mode",
    )

    sync_conflict_strategy = _validate_literal(
        data.get("sync_github_conflict_strategy", "prompt"),
        ("local_wins", "remote_wins", "prompt", "manual_merge"),
        "sync_github_conflict_strategy",
    )

    sync_providers = _parse_sync_providers(data.get("sync"), resolved)

    return Config(
        project_name=str(data["project_name"]),
        project_id=str(data["project_id"]),
        llm_provider=_str_or_none(data.get("llm_provider")),
        llm_model=_str_or_none(data.get("llm_model")),
        default_lease_minutes=int(str(data.get("default_lease_minutes", 60))),
        default_heartbeat_minutes=int(str(data.get("default_heartbeat_minutes", 5))),
        git_ops_mode=git_ops_mode,  # type: ignore[arg-type]
        sync_github_enabled=bool(data.get("sync_github_enabled", False)),
        sync_github_conflict_strategy=sync_conflict_strategy,  # type: ignore[arg-type]
        sync_providers=sync_providers,
        db_path=db_path,
        events_path=events_path,
    )


def write_default_config(path: str | Path, *, project_name: str) -> None:
    """Write a starter config.yaml to *path*.

    Generates a fresh project_id (UUIDv4).  Does NOT overwrite an existing
    file — callers must check first.

    Raises
    ------
    FileExistsError
        If *path* already exists.
    """
    resolved = Path(path).expanduser().resolve()
    if resolved.exists():
        raise FileExistsError(
            f"Config file already exists: {resolved}. "
            "Delete it manually if you want to re-initialise."
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    project_id = str(uuid.uuid4())
    content = _render_template(project_name=project_name, project_id=project_id)
    resolved.write_text(content, encoding="utf-8")


def config_template(*, project_name: str = "my-project") -> str:
    """Return the default config YAML as a string.

    Useful for the `fakoli-state init` command to display what will be written,
    or for tests that want the canonical default shape without touching the disk.
    """
    return _render_template(
        project_name=project_name,
        project_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_required(data: dict[str, object], path: Path) -> None:
    """Raise ValueError if required top-level keys are missing or blank."""
    for key in ("project_name", "project_id"):
        val = data.get(key)
        if not val or not str(val).strip():
            raise ValueError(
                f"Config file {path} is missing required field {key!r}. "
                "Run `fakoli-state init` to generate a valid config."
            )


def _validate_literal(
    value: object,
    allowed: tuple[str, ...],
    field_name: str,
) -> str:
    """Return *value* as str if it is in *allowed*, else raise ValueError."""
    s = str(value)
    if s not in allowed:
        raise ValueError(
            f"Invalid value {s!r} for config field {field_name!r}. "
            f"Allowed values: {allowed}."
        )
    return s


def _str_or_none(value: object) -> str | None:
    """Return None if value is None or empty string, else str(value)."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _resolve_path(value: object, base: Path) -> str:
    """Resolve *value* (str path) relative to *base* directory."""
    p = Path(str(value)).expanduser()
    if p.is_absolute():
        return str(p)
    return str((base / p).resolve())


def _parse_sync_providers(
    sync_block: object,
    config_path: Path,
) -> tuple[str, ...] | None:
    """Parse the optional top-level ``sync:`` block.

    Returns
    -------
    tuple[str, ...] | None
        * ``None`` — the ``sync`` key is absent, OR the ``sync`` block has
          no ``providers`` key. Callers SHOULD fall back to
          ``sorted(PROVIDER_REGISTRY)`` (v1.8.0 behaviour: every
          registered provider counts).
        * ``tuple[str, ...]`` — the operator pinned an explicit list of
          provider ids. May be empty (``sync.providers: []``) to opt out
          of every provider; callers MUST treat that as a no-op rather
          than falling back to the registry.

    Raises
    ------
    ValueError
        If ``sync`` is present but not a mapping, OR ``sync.providers`` is
        present but not a list of strings.
    """
    if sync_block is None:
        return None
    if not isinstance(sync_block, dict):
        raise ValueError(
            f"Config file {config_path}: top-level 'sync' key must be a "
            f"mapping, got {type(sync_block).__name__!r}."
        )
    providers = sync_block.get("providers")
    if providers is None:
        return None
    if not isinstance(providers, list):
        raise ValueError(
            f"Config file {config_path}: 'sync.providers' must be a list, "
            f"got {type(providers).__name__!r}."
        )
    out: list[str] = []
    for idx, item in enumerate(providers):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"Config file {config_path}: 'sync.providers[{idx}]' must "
                f"be a non-empty string, got {item!r}."
            )
        out.append(item.strip())
    return tuple(out)


def _render_template(*, project_name: str, project_id: str) -> str:
    """Render the default config YAML template."""
    return f"""\
# fakoli-state configuration
# Generated by `fakoli-state init`. Edit as needed.

# ---------------------------------------------------------------------------
# Project identity (required)
# ---------------------------------------------------------------------------
project_name: {project_name!r}
project_id: {project_id!r}

# ---------------------------------------------------------------------------
# Storage paths (relative to this file, or absolute)
# ---------------------------------------------------------------------------
db_path: state.db
events_path: events.jsonl

# ---------------------------------------------------------------------------
# LLM integration (optional — leave blank to use CLI without LLM features)
# ---------------------------------------------------------------------------
llm_provider:   # e.g. "anthropic"
llm_model:      # e.g. "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Claim / lease settings
# ---------------------------------------------------------------------------
default_lease_minutes: 60
default_heartbeat_minutes: 5

# ---------------------------------------------------------------------------
# Git operations  (auto | record_only | off)
#   auto        — fakoli-state creates branches and records commits
#   record_only — records what happened; does not drive git
#   off         — no git integration
# ---------------------------------------------------------------------------
git_ops_mode: auto

# ---------------------------------------------------------------------------
# GitHub sync (optional)
# ---------------------------------------------------------------------------
sync_github_enabled: false
sync_github_conflict_strategy: prompt  # local_wins | remote_wins | prompt | manual_merge
"""
