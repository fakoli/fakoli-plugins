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

    # ---------------------------------------------------------------------
    # LLM provider selection (v1.17.0).
    #
    # Precedence applied by ``planning.llm_planner.resolve_planner_provider``:
    #
    # 1. ``llm_provider`` explicit in this config → wins.
    # 2. Env auto-detect when ``llm_provider`` is None:
    #    - ANTHROPIC_API_KEY  → "anthropic"  (direct API, cheapest path)
    #    - AWS_REGION (or AWS_DEFAULT_REGION) with no ANTHROPIC_API_KEY
    #      AND ``anthropic[bedrock]`` installed → "bedrock"
    #    - CUSTOM_LLM_BASE_URL → "custom"
    # 3. Fail loudly.
    #
    # We do NOT silent-fail across providers when one is misconfigured —
    # community consensus (research/2026) is that silent fallback breaks
    # cost predictability and surprises ops teams during incidents. Pick
    # one per process; re-launch to switch.
    # ---------------------------------------------------------------------
    llm_provider: Literal["anthropic", "bedrock", "custom"] | None = None

    # Explicit model id (overrides ``llm_tier``). Pass when you need a
    # specific Anthropic-API id (``claude-opus-4-7-20260124``), a Bedrock
    # inference-profile id (``us.anthropic.claude-opus-4-7``), or a
    # custom-endpoint route name (``anthropic/claude-sonnet-4-6`` on
    # OpenRouter). Leave blank to use ``llm_tier``.
    llm_model: str | None = None

    # Logical tier (``opus``/``sonnet``/``haiku``) used when ``llm_model``
    # is blank. Defaults to None → providers fall back to their own
    # ``DEFAULT_TIER`` (``sonnet``). Set this in config so a project's
    # default tier is stable across provider switches.
    llm_tier: Literal["opus", "sonnet", "haiku"] | None = None

    # Bedrock-specific knobs. Only consulted when ``llm_provider`` resolves
    # to ``bedrock``. ``aws_region`` falls through to AWS_REGION /
    # AWS_DEFAULT_REGION env vars and finally to a clear SDK error — we
    # do NOT pick a silent default like ``us-east-1`` because that would
    # hide latency / billing surprises.
    bedrock_region: str | None = None
    bedrock_profile: str | None = None

    # Custom-endpoint knobs. Only consulted when ``llm_provider`` resolves
    # to ``custom``. ``base_url`` is REQUIRED for the custom path (either
    # here or via CUSTOM_LLM_BASE_URL env). ``api_key_env`` names the env
    # var to read the bearer token from — defaults to ``CUSTOM_LLM_API_KEY``,
    # which the resolver also tries before falling back to ``OPENAI_API_KEY``.
    custom_base_url: str | None = None
    custom_api_key_env: str | None = None

    default_lease_minutes: int = 60
    default_heartbeat_minutes: int = 5

    git_ops_mode: Literal["auto", "record_only", "off"] = "auto"

    # SL1-RR-1 — write-path durability mode.
    #
    # Selects how aggressively the event log is persisted to disk. The write
    # path (see state/sqlite.py append()) reads this to decide whether to
    # fsync the log before COMMIT.
    #
    #   relaxed (DEFAULT) — laptop: synchronous=NORMAL, buffered log, no
    #                       per-event fsync. Correctness does not depend on
    #                       fsync (ordering + log-authority counter + forward
    #                       catch-up guarantee replay determinism); worst case
    #                       on hard power-loss is the last few un-synced events
    #                       drop from log and projection together and the user
    #                       repeats the last action.
    #   strict            — CI/shared/server: synchronous=FULL + fsync(log)
    #                       before COMMIT. Opt-in; the only mode that fsyncs
    #                       per event.
    #
    # Defaults to "relaxed" so a config written before this key existed keeps
    # its prior (un-synced) behaviour without surprise.
    durability: Literal["relaxed", "strict"] = "relaxed"

    # v1.15.0 — host-project branch-naming convention.
    #
    # The CLI's `claim` command creates a git branch per task. By default
    # the branch is `agent/<task_id_lower>-<slug>` — the `agent/` prefix
    # advertises that an agent (not a human) worked the task. But many
    # host projects encode their CI / PR-template / CODEOWNERS automation
    # around a `feature/` or `fix/` prefix, and the `agent/` default
    # silently bypasses those rules.
    #
    # Set this in `.fakoli-state/config.yaml` to match the host project:
    #
    #     branch_prefix: feature   # → feature/<task>-<slug>
    #     branch_prefix: fix       # → fix/<task>-<slug>
    #     branch_prefix: ""        # → <task>-<slug>  (no prefix)
    #     branch_prefix: agent     # default; preserves pre-v1.15.0 behaviour
    #
    # Nested prefixes (e.g. `feature/agent`) are allowed verbatim — git
    # accepts slashes inside branch names. Validation: any string with no
    # whitespace and no leading/trailing slash. An empty string is
    # explicit opt-out and produces an unprefixed `<task>-<slug>` branch.
    branch_prefix: str = "agent"

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

    # SL1-RR-1 — durability mode. Absent key → "relaxed" (back-compat with
    # configs written before this knob existed). An invalid value raises the
    # same ValueError that every other literal-typed field raises.
    durability = _validate_literal(
        data.get("durability", "relaxed"),
        ("relaxed", "strict"),
        "durability",
    )

    # v1.15.0 — branch_prefix. Validate format: no whitespace, no leading
    # or trailing slash. An empty string is acceptable (explicit no-prefix
    # mode). Internal slashes are allowed (nested prefixes like
    # `feature/agent`). Invalid values raise a config-load error so the
    # user sees the problem at init time, not when claim runs.
    branch_prefix_raw = data.get("branch_prefix", "agent")
    if not isinstance(branch_prefix_raw, str):
        raise ValueError(
            f"branch_prefix must be a string, got {type(branch_prefix_raw).__name__} "
            f"({resolved})"
        )
    branch_prefix = branch_prefix_raw
    if branch_prefix and (
        branch_prefix.startswith("/")
        or branch_prefix.endswith("/")
        or any(c.isspace() for c in branch_prefix)
    ):
        raise ValueError(
            f"branch_prefix {branch_prefix!r} has invalid shape: "
            "leading/trailing slashes and whitespace are not allowed "
            f"({resolved}). Use e.g. 'feature' or 'fix' or 'feature/agent'."
        )

    sync_conflict_strategy = _validate_literal(
        data.get("sync_github_conflict_strategy", "prompt"),
        ("local_wins", "remote_wins", "prompt", "manual_merge"),
        "sync_github_conflict_strategy",
    )

    sync_providers = _parse_sync_providers(data.get("sync"), resolved)

    # v1.17.0 — LLM provider / tier validation. Enum-typed fields rejected
    # at load time so misconfigs surface during `init`, not during plan.
    llm_provider_raw = _str_or_none(data.get("llm_provider"))
    if llm_provider_raw is not None:
        llm_provider_value: Literal["anthropic", "bedrock", "custom"] | None = (
            _validate_literal(  # type: ignore[assignment]
                llm_provider_raw,
                ("anthropic", "bedrock", "custom"),
                "llm_provider",
            )
        )
    else:
        llm_provider_value = None

    llm_tier_raw = _str_or_none(data.get("llm_tier"))
    if llm_tier_raw is not None:
        llm_tier_value: Literal["opus", "sonnet", "haiku"] | None = (
            _validate_literal(  # type: ignore[assignment]
                llm_tier_raw,
                ("opus", "sonnet", "haiku"),
                "llm_tier",
            )
        )
    else:
        llm_tier_value = None

    return Config(
        project_name=str(data["project_name"]),
        project_id=str(data["project_id"]),
        llm_provider=llm_provider_value,
        llm_model=_str_or_none(data.get("llm_model")),
        llm_tier=llm_tier_value,
        bedrock_region=_str_or_none(data.get("bedrock_region")),
        bedrock_profile=_str_or_none(data.get("bedrock_profile")),
        custom_base_url=_str_or_none(data.get("custom_base_url")),
        custom_api_key_env=_str_or_none(data.get("custom_api_key_env")),
        default_lease_minutes=int(str(data.get("default_lease_minutes", 60))),
        default_heartbeat_minutes=int(str(data.get("default_heartbeat_minutes", 5))),
        git_ops_mode=git_ops_mode,  # type: ignore[arg-type]
        durability=durability,  # type: ignore[arg-type]
        branch_prefix=branch_prefix,
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
#
# `llm_provider` picks ONE of: anthropic | bedrock | custom. When blank,
# fakoli-state auto-detects from the environment:
#   ANTHROPIC_API_KEY → anthropic    (direct API; cheapest path)
#   AWS_REGION + anthropic[bedrock] installed → bedrock
#   CUSTOM_LLM_BASE_URL → custom     (any OpenAI-compatible /v1 endpoint)
#
# `llm_tier` (opus | sonnet | haiku) sets the default tier across the
# project; per-call overrides win. `llm_model` is an explicit model-id
# override that bypasses tier resolution entirely.
#
# Tier-mapping defaults (refreshed 2026-05-26):
#   opus   → claude-opus-4-7        (us.anthropic.claude-opus-4-7   on Bedrock)
#   sonnet → claude-sonnet-4-6      (us.anthropic.claude-sonnet-4-6 on Bedrock)
#   haiku  → claude-haiku-4-5       (us.anthropic.claude-haiku-4-5  on Bedrock)
#
# See docs/llm-providers.md for the full setup guide.
# ---------------------------------------------------------------------------
llm_provider:                       # anthropic | bedrock | custom (blank = auto)
llm_tier:                           # opus | sonnet | haiku (blank = sonnet)
llm_model:                          # explicit model id (overrides tier)

# Bedrock-only knobs (ignored unless llm_provider resolves to "bedrock").
# Region falls back to AWS_REGION / AWS_DEFAULT_REGION env vars.
bedrock_region:                     # e.g. "us-east-1"
bedrock_profile:                    # named profile from ~/.aws/credentials

# Custom-endpoint knobs (ignored unless llm_provider resolves to "custom").
# `base_url` is REQUIRED for the custom path (either here or via env var
# CUSTOM_LLM_BASE_URL). `api_key_env` names the env var to read for the
# bearer token; defaults to CUSTOM_LLM_API_KEY then OPENAI_API_KEY.
custom_base_url:                    # e.g. "http://localhost:8000/v1"
custom_api_key_env:                 # e.g. "OPENROUTER_API_KEY"

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
# Write-path durability  (relaxed | strict)
#   relaxed — DEFAULT. synchronous=NORMAL, buffered log, no per-event fsync.
#             Fast; correctness does not depend on fsync. Worst case on hard
#             power-loss: the last few un-synced events drop and you repeat
#             the last action. Right choice for a laptop.
#   strict  — synchronous=FULL + fsync(log) before COMMIT. The only mode that
#             fsyncs per event. Use on CI / shared / server storage.
# ---------------------------------------------------------------------------
durability: relaxed

# ---------------------------------------------------------------------------
# Branch naming convention (v1.15.0)
#
# Prefix applied to branches created by `fakoli-state claim`. Defaults to
# `agent` (advertises that an agent worked the task). Override to match
# the host project's convention so PR templates, CODEOWNERS, branch
# protection rules, and CI hooks fire as expected.
#
#   branch_prefix: agent     # default: agent/<task>-<slug>
#   branch_prefix: feature   # feature/<task>-<slug>
#   branch_prefix: fix       # fix/<task>-<slug>
#   branch_prefix: ""        # no prefix: <task>-<slug>
#
# Nested prefixes (e.g. `feature/agent`) are also accepted verbatim.
# ---------------------------------------------------------------------------
branch_prefix: agent

# ---------------------------------------------------------------------------
# GitHub sync (optional)
# ---------------------------------------------------------------------------
sync_github_enabled: false
sync_github_conflict_strategy: prompt  # local_wins | remote_wins | prompt | manual_merge
"""
