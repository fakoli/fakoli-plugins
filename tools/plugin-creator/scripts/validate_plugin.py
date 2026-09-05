#!/usr/bin/env python3
"""Validate local package structure; optionally check richer catalog metadata.

This is a static preflight, not the live service's ingestion schema or runtime.
YAML validation requires PyYAML: uv run --with PyYAML scripts/validate_plugin.py ...
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

from identifier_validation import SEMVER_RE, validate_plugin_identifier

TODO_MARKER = "[TODO:"
HEX_COLOR_RE = re.compile(r"^#[0-9A-F]{6}$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a local Codex plugin.")
    parser.add_argument("plugin_path", help="Path to the plugin root directory")
    parser.add_argument(
        "--profile",
        choices=("runtime", "catalog"),
        default="runtime",
        help="runtime: package preflight; catalog: also require publisher/UI metadata",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plugin_root = Path(args.plugin_path).expanduser().resolve()
    errors = validate_plugin(plugin_root, profile=args.profile)
    if errors:
        print("Plugin validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Plugin validation passed: {plugin_root}")


def validate_plugin(plugin_root: Path, *, profile: str = "runtime") -> list[str]:
    if profile not in {"runtime", "catalog"}:
        raise ValueError(f"Unknown validation profile: {profile}")
    plugin_root = plugin_root.resolve()
    errors: list[str] = []
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = load_json_object(manifest_path, errors)
    if manifest is None:
        return errors

    reject_todo_markers(manifest, "$", errors)
    validate_manifest_shape(plugin_root, manifest, errors, profile=profile)
    return errors


def load_json_object(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append("missing `.codex-plugin/plugin.json`")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        errors.append("unable to read `.codex-plugin/plugin.json`")
        return None
    except json.JSONDecodeError:
        errors.append("`.codex-plugin/plugin.json` must be valid JSON")
        return None
    if not isinstance(payload, dict):
        errors.append("`.codex-plugin/plugin.json` must contain a JSON object")
        return None
    return payload


def reject_todo_markers(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, str):
        if TODO_MARKER in value:
            errors.append(f"{path} still contains a `[TODO: ...]` placeholder")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            reject_todo_markers(item, f"{path}[{index}]", errors)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            reject_todo_markers(item, f"{path}.{key}", errors)


def validate_manifest_shape(
    plugin_root: Path,
    manifest: dict[str, Any],
    errors: list[str],
    *,
    profile: str = "runtime",
) -> None:
    allowed_keys = {
        "id",
        "name",
        "version",
        "description",
        "skills",
        "apps",
        "mcpServers",
        "hooks",
        "interface",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
    }
    for key in sorted(set(manifest) - allowed_keys) if profile == "catalog" else []:
        errors.append(f"plugin.json field `{key}` is not accepted by plugin validation")

    validate_optional_non_empty_string(manifest, "id", errors)
    plugin_name = require_non_empty_string(manifest, "name", errors)
    if plugin_name is not None:
        try:
            validate_plugin_identifier(plugin_name)
        except ValueError as error:
            errors.append(f"plugin.json field `name` is invalid: {error}")
    version = (
        require_non_empty_string(manifest, "version", errors)
        if "version" in manifest or profile == "catalog"
        else None
    )
    if version is not None and SEMVER_RE.fullmatch(version) is None:
        errors.append("plugin.json field `version` must be strict semver")
    if "description" in manifest or profile == "catalog":
        require_non_empty_string(manifest, "description", errors)

    author = (
        require_object(manifest, "author", errors)
        if "author" in manifest or profile == "catalog"
        else None
    )
    if author is not None:
        reject_unknown_fields(author, {"name", "email", "url"}, "author", errors)
        require_non_empty_string(author, "name", errors, prefix="author")
        validate_optional_non_empty_string(author, "email", errors, prefix="author")
        validate_optional_https_url(author, "url", errors, prefix="author")

    for field in ("homepage", "repository"):
        validate_optional_https_url(manifest, field, errors, prefix="plugin")
    validate_optional_non_empty_string(manifest, "license", errors)
    if "keywords" in manifest and (
        not isinstance(manifest["keywords"], list)
        or not all(
            isinstance(item, str) and item.strip() for item in manifest["keywords"]
        )
    ):
        errors.append(
            "plugin.json field `keywords` must be an array of non-empty strings"
        )

    skills_roots = (
        {plugin_root / "skills"} if (plugin_root / "skills").is_dir() else set()
    )
    if "skills" in manifest:
        skills_path = validate_component_path(
            plugin_root, manifest["skills"], "skills", errors, directory=True
        )
        if skills_path is not None:
            skills_roots.add(skills_path)
    validate_manifest_mcp_servers(plugin_root, manifest, errors)
    validate_manifest_hooks(plugin_root, manifest, errors)

    if "apps" in manifest:
        apps_path = validate_component_path(
            plugin_root, manifest["apps"], "apps", errors
        )
        if apps_path is not None:
            validate_app_manifest(apps_path, errors)
    elif (plugin_root / ".app.json").is_file():
        validate_app_manifest(plugin_root / ".app.json", errors)
    for skills_root in sorted(skills_roots):
        validate_skill_manifests(
            plugin_root, errors, skills_root=skills_root, profile=profile
        )

    interface = (
        require_object(manifest, "interface", errors)
        if "interface" in manifest or profile == "catalog"
        else None
    )
    if interface is None:
        return
    reject_unknown_fields(
        interface,
        {
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "capabilities",
            "websiteURL",
            "privacyPolicyURL",
            "termsOfServiceURL",
            "brandColor",
            "composerIcon",
            "logo",
            "logoDark",
            "screenshots",
            "defaultPrompt",
            "default_prompt",
        },
        "interface",
        errors,
    )
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
    ):
        if field in interface or profile == "catalog":
            require_non_empty_string(interface, field, errors, prefix="interface")
    if (
        profile == "catalog"
        and "defaultPrompt" not in interface
        and "default_prompt" not in interface
    ):
        errors.append(
            "plugin.json field `interface.defaultPrompt` or `interface.default_prompt` is required"
        )
    for field in ("defaultPrompt", "default_prompt"):
        if field in interface:
            prompts = interface[field]
            if isinstance(prompts, str):
                prompts = [prompts]  # Existing local plugins use the singular form.
            if (
                not isinstance(prompts, list)
                or not prompts
                or not all(isinstance(item, str) and item.strip() for item in prompts)
            ):
                errors.append(
                    f"plugin.json field `interface.{field}` must be a string or non-empty array of strings"
                )
            elif profile == "catalog" and (
                len(prompts) > 3 or any(len(item) > 128 for item in prompts)
            ):
                errors.append(
                    f"plugin.json field `interface.{field}` must contain at most 3 prompts of at most 128 characters for catalog presentation"
                )
    capabilities = interface.get("capabilities", [] if profile == "runtime" else None)
    if not isinstance(capabilities, list) or not all(
        isinstance(value, str) and value.strip() for value in capabilities
    ):
        errors.append(
            "plugin.json field `interface.capabilities` must be an array of strings"
        )
    for field in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
        validate_optional_https_url(interface, field, errors, prefix="interface")
    brand_color = interface.get("brandColor")
    if brand_color is not None and (
        not isinstance(brand_color, str) or HEX_COLOR_RE.fullmatch(brand_color) is None
    ):
        errors.append("plugin.json field `interface.brandColor` must use `#RRGGBB`")
    for field in ("composerIcon", "logo", "logoDark"):
        validate_optional_asset_path(plugin_root, plugin_root, interface, field, errors)
    screenshots = interface.get("screenshots", [])
    if not isinstance(screenshots, list):
        errors.append("plugin.json field `interface.screenshots` must be an array")
    else:
        for index, raw_path in enumerate(screenshots):
            validate_asset_path(
                plugin_root,
                plugin_root,
                raw_path,
                f"interface.screenshots[{index}]",
                errors,
            )


def require_object(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
) -> dict[str, Any] | None:
    value = payload.get(key)
    if not isinstance(value, dict):
        errors.append(f"plugin.json field `{key}` must be an object")
        return None
    return value


def require_non_empty_string(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> str | None:
    value = payload.get(key)
    field = f"{prefix}.{key}" if prefix is not None else key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"plugin.json field `{field}` must be a non-empty string")
        return None
    return value


def validate_optional_non_empty_string(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = payload.get(key)
    if value is None:
        return
    field = f"{prefix}.{key}" if prefix is not None else key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"plugin.json field `{field}` must be a non-empty string")


def reject_unknown_fields(
    payload: dict[str, Any],
    allowed_keys: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    for key in sorted(set(payload) - allowed_keys):
        errors.append(
            f"plugin.json field `{prefix}.{key}` is not accepted by plugin validation"
        )


def validate_optional_https_url(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str,
) -> None:
    value = payload.get(key)
    if value is None:
        return
    parsed = urlparse(value) if isinstance(value, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        errors.append(
            f"plugin.json field `{prefix}.{key}` must be an absolute `https://` URL"
        )


def validate_optional_contract_path(
    payload: dict[str, Any],
    key: str,
    expected: str,
    errors: list[str],
) -> None:
    value = payload.get(key)
    if value is None:
        return
    normalized = normalize_contract_path(value) if isinstance(value, str) else None
    if normalized != expected:
        errors.append(f"plugin.json field `{key}` must resolve to `{expected}`")


def validate_manifest_mcp_servers(
    plugin_root: Path,
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    value = manifest.get("mcpServers")
    if value is None:
        if (plugin_root / ".mcp.json").is_file():
            value = "./.mcp.json"
        elif "mcpServers" in manifest:
            errors.append(
                "plugin.json field `mcpServers` must be a string path or object"
            )
        else:
            return
    if isinstance(value, str):
        path = validate_component_path(plugin_root, value, "mcpServers", errors)
        if path is not None:
            validate_mcp_manifest(path, errors)
        return
    if isinstance(value, dict):
        validate_mcp_server_entries(
            value,
            "plugin.json field `mcpServers`",
            "plugin.json field `mcpServers`",
            errors,
        )
        return
    errors.append("plugin.json field `mcpServers` must be a string path or object")


def validate_component_path(
    plugin_root: Path,
    value: Any,
    field: str,
    errors: list[str],
    *,
    directory: bool = False,
) -> Path | None:
    if not isinstance(value, str) or not value.startswith("./") or "\\" in value:
        errors.append(
            f"plugin.json field `{field}` must use a ./-prefixed relative path"
        )
        return None
    candidate = PurePosixPath(value)
    resolved = (plugin_root / candidate).resolve()
    if ".." in candidate.parts or not resolved.is_relative_to(plugin_root.resolve()):
        errors.append(f"plugin.json field `{field}` must stay inside the plugin root")
        return None
    if not (resolved.is_dir() if directory else resolved.is_file()):
        errors.append(
            f"plugin.json field `{field}` points to a missing {'directory' if directory else 'file'}"
        )
        return None
    return resolved


def validate_manifest_hooks(
    plugin_root: Path, manifest: dict[str, Any], errors: list[str]
) -> None:
    value = manifest.get("hooks")
    if "hooks" not in manifest:
        if not (plugin_root / "hooks" / "hooks.json").is_file():
            return
        value = "./hooks/hooks.json"
    entries = value if isinstance(value, list) else [value]
    if (
        isinstance(value, list)
        and entries
        and not (
            all(isinstance(item, str) for item in entries)
            or all(isinstance(item, dict) for item in entries)
        )
    ):
        errors.append(
            "plugin.json field `hooks` array must contain only paths or only inline objects"
        )
        return
    for index, entry in enumerate(entries):
        label = f"hooks[{index}]" if isinstance(value, list) else "hooks"
        if isinstance(entry, str):
            path = validate_component_path(plugin_root, entry, label, errors)
            if path is None:
                continue
            entry = load_companion_json_object(path, f"`{label}`", errors)
            if entry is None:
                continue
        if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), dict):
            errors.append(f"`{label}` must contain a hooks object")
            continue
        # Deliberately structural: event support and command trust depend on host version.
        for event, groups in entry["hooks"].items():
            if not isinstance(groups, list):
                errors.append(f"`{label}.{event}` must be an array of hook groups")
                continue
            for group in groups:
                if not isinstance(group, dict) or not isinstance(
                    group.get("hooks"), list
                ):
                    errors.append(
                        f"`{label}.{event}` groups must contain a hooks array"
                    )
                    continue
                for hook in group["hooks"]:
                    if not isinstance(hook, dict) or not isinstance(
                        hook.get("type"), str
                    ):
                        errors.append(
                            f"`{label}.{event}` hook entries must have a type"
                        )
                    elif hook["type"] == "command" and not (
                        isinstance(hook.get("command"), str) and hook["command"].strip()
                    ):
                        errors.append(
                            f"`{label}.{event}` command hooks must contain a command string"
                        )


def normalize_contract_path(raw_path: str) -> str | None:
    path = Path(raw_path)
    if path.is_absolute():
        return None
    normalized = path.as_posix().rstrip("/")
    return normalized or None


def validate_app_manifest(path: Path, errors: list[str]) -> None:
    payload = load_companion_json_object(path, "`.app.json`", errors)
    if payload is None:
        return
    reject_companion_unknown_fields(payload, {"apps"}, "`.app.json`", errors)
    apps = payload.get("apps")
    if not isinstance(apps, dict):
        errors.append("`.app.json` field `apps` must be an object")
        return
    for key, value in apps.items():
        if not isinstance(value, dict):
            errors.append(f"`.app.json` app `{key}` must be an object")
            continue
        reject_companion_unknown_fields(
            value, {"id", "category"}, f"`.app.json` app `{key}`", errors
        )
        app_id = value.get("id")
        if not isinstance(app_id, str) or not app_id.strip():
            errors.append(
                f"`.app.json` app `{key}` field `id` must be a non-empty string"
            )
        category = value.get("category")
        if category is not None and (
            not isinstance(category, str) or not category.strip()
        ):
            errors.append(
                f"`.app.json` app `{key}` field `category` must be a non-empty string"
            )


def validate_mcp_manifest(path: Path, errors: list[str]) -> None:
    payload = load_companion_json_object(path, "`.mcp.json`", errors)
    if payload is None:
        return
    # The native parser's Rust mcp_servers field is renamed to camelCase by
    # serde. Snake case is not a JSON wrapper; direct server names remain free.
    snake_value = payload.get("mcp_servers")
    if isinstance(snake_value, dict) and not ({"command", "url"} & set(snake_value)):
        errors.append(
            "`.mcp.json` does not support the `mcp_servers` wrapper; use `mcpServers` or a direct server map"
        )
        return
    if "mcpServers" in payload:
        if len(payload) != 1:
            errors.append(
                "`.mcp.json` must use one server-map wrapper, without mixed direct entries"
            )
            return
        servers = payload["mcpServers"]
    else:
        servers = payload
    validate_mcp_server_entries(
        servers,
        "`.mcp.json`",
        "`.mcp.json` field `mcpServers`",
        errors,
    )


def validate_mcp_server_entries(
    servers: Any,
    source_label: str,
    field_label: str,
    errors: list[str],
) -> None:
    if not isinstance(servers, dict):
        errors.append(f"{field_label} must be an object")
        return
    for key, value in servers.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{source_label} server names must be non-empty strings")
        if not isinstance(value, dict):
            errors.append(f"{source_label} server `{key}` must be an object")


def load_companion_json_object(
    path: Path,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{label} is required when its plugin.json field is present")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"{label} must contain valid JSON")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must contain a JSON object")
        return None
    return payload


def reject_companion_unknown_fields(
    payload: dict[str, Any],
    allowed_keys: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    for key in sorted(set(payload) - allowed_keys):
        errors.append(f"{prefix} field `{key}` is not accepted by plugin validation")


def validate_skill_manifests(
    plugin_root: Path,
    errors: list[str],
    *,
    skills_root: Path | None = None,
    profile: str = "runtime",
) -> None:
    skills_root = skills_root or plugin_root / "skills"
    if not skills_root.is_dir():
        return
    if not skills_root.resolve().is_relative_to(plugin_root.resolve()):
        errors.append("skills directory must stay inside the plugin root")
        return
    if (skills_root / "SKILL.md").is_file():
        validate_skill_manifest(
            skills_root, errors, plugin_root=plugin_root, profile=profile
        )
        return
    for skill_root in sorted(skills_root.iterdir(), key=lambda path: path.name):
        if skill_root.name.startswith(".") or not skill_root.is_dir():
            continue
        if not skill_root.resolve().is_relative_to(plugin_root.resolve()):
            errors.append(f"skill `{skill_root.name}` must stay inside the plugin root")
            continue
        validate_skill_manifest(
            skill_root, errors, plugin_root=plugin_root, profile=profile
        )


def validate_skill_manifest(
    skill_root: Path,
    errors: list[str],
    *,
    plugin_root: Path | None = None,
    profile: str = "runtime",
) -> None:
    skill_md_path = skill_root / "SKILL.md"
    if plugin_root is not None and not skill_md_path.resolve().is_relative_to(
        plugin_root.resolve()
    ):
        errors.append(
            f"skill `{skill_root.name}` SKILL.md must stay inside the plugin root"
        )
        return
    if not skill_md_path.is_file():
        errors.append(f"skill `{skill_root.name}` is missing `SKILL.md`")
        return
    try:
        contents = skill_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        errors.append(f"unable to read skill `{skill_root.name}`")
        return
    if yaml is None:
        errors.append(
            "Skill validation requires PyYAML; run with `uv run --with PyYAML scripts/validate_plugin.py <plugin-path>`"
        )
        return
    if not contents.startswith("---\n"):
        errors.append(f"skill `{skill_root.name}` must start with YAML frontmatter")
        return
    closing = re.search(r"^---[ \t]*$", contents[4:], re.MULTILINE)
    if closing is None:
        errors.append(f"skill `{skill_root.name}` frontmatter is not closed")
        return
    try:
        frontmatter = yaml.safe_load(contents[4 : 4 + closing.start()])
    except yaml.YAMLError:
        errors.append(f"skill `{skill_root.name}` frontmatter must be valid YAML")
        return
    if not isinstance(frontmatter, dict):
        errors.append(f"skill `{skill_root.name}` frontmatter must be an object")
        return
    skill_name = frontmatter.get("name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        errors.append(
            f"skill `{skill_root.name}` frontmatter field `name` must be non-empty"
        )
    elif (
        len(skill_name) > 64
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name) is None
        or skill_name != skill_root.name
    ):
        errors.append(
            f"skill `{skill_root.name}` name must match its directory and use 1–64 lowercase letters, digits, and single hyphens"
        )
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(
            f"skill `{skill_root.name}` frontmatter field `description` must be non-empty"
        )
    elif len(description) > 1024:
        errors.append(
            f"skill `{skill_root.name}` description must be at most 1024 characters"
        )
    compatibility = frontmatter.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or len(compatibility) > 500
    ):
        errors.append(
            f"skill `{skill_root.name}` compatibility must be a string of at most 500 characters"
        )
    for field in ("license", "allowed-tools"):
        if field in frontmatter and not isinstance(frontmatter[field], str):
            errors.append(f"skill `{skill_root.name}` {field} must be a string")
    metadata = frontmatter.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict)
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in metadata.items()
        )
    ):
        errors.append(f"skill `{skill_root.name}` metadata must map strings to strings")
    disable_model_invocation = frontmatter.get("disable-model-invocation")
    if disable_model_invocation is None:
        disable_model_invocation = frontmatter.get("disable_model_invocation")
    if profile == "catalog" and disable_model_invocation not in (None, False):
        errors.append(
            f"skill `{skill_root.name}` frontmatter field `disable-model-invocation` must be false"
        )
    agent_yaml_path = skill_root / "agents" / "openai.yaml"
    if agent_yaml_path.is_file():
        if plugin_root is not None and not agent_yaml_path.resolve().is_relative_to(
            plugin_root.resolve()
        ):
            errors.append(
                f"skill `{skill_root.name}` agents/openai.yaml must stay inside the plugin root"
            )
            return
        validate_skill_agent_manifest(
            plugin_root=plugin_root or skill_root.parent.parent,
            skill_root=skill_root,
            agent_yaml_path=agent_yaml_path,
            errors=errors,
        )


def validate_skill_agent_manifest(
    *,
    plugin_root: Path,
    skill_root: Path,
    agent_yaml_path: Path,
    errors: list[str],
) -> None:
    try:
        payload = yaml.safe_load(agent_yaml_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        errors.append(f"unable to read skill `{skill_root.name}` agent YAML")
        return
    except yaml.YAMLError:
        errors.append(f"skill `{skill_root.name}` agent YAML must be valid YAML")
        return
    if not isinstance(payload, dict):
        errors.append(f"skill `{skill_root.name}` agent YAML must be an object")
        return

    reject_skill_agent_unknown_fields(
        payload,
        {"interface", "policy", "dependencies"},
        skill_root,
        errors,
    )
    interface = payload.get("interface", {})
    if not isinstance(interface, dict):
        errors.append(
            f"skill `{skill_root.name}` agent field `interface` must be an object"
        )
        return
    reject_skill_agent_unknown_fields(
        interface,
        {
            "display_name",
            "short_description",
            "icon_small",
            "icon_large",
            "brand_color",
            "default_prompt",
        },
        skill_root,
        errors,
        prefix="interface",
    )
    for field in ("display_name", "short_description"):
        value = interface.get(field)
        if field in interface and (not isinstance(value, str) or not value.strip()):
            errors.append(
                f"skill `{skill_root.name}` agent field `interface.{field}` must be non-empty"
            )
    for field in ("icon_small", "icon_large"):
        validate_optional_asset_path(
            skill_root,
            plugin_root,
            interface,
            field,
            errors,
            prefix=f"skill `{skill_root.name}` agent field `interface",
        )
    brand_color = interface.get("brand_color")
    if brand_color is not None and (
        not isinstance(brand_color, str) or HEX_COLOR_RE.fullmatch(brand_color) is None
    ):
        errors.append(
            f"skill `{skill_root.name}` agent field `interface.brand_color` must use `#RRGGBB`"
        )
    default_prompt = interface.get("default_prompt")
    if default_prompt is not None and (
        not isinstance(default_prompt, str) or not default_prompt.strip()
    ):
        errors.append(
            f"skill `{skill_root.name}` agent field `interface.default_prompt` must be non-empty"
        )

    policy = payload.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            errors.append(
                f"skill `{skill_root.name}` agent field `policy` must be an object"
            )
        else:
            reject_skill_agent_unknown_fields(
                policy,
                {"allow_implicit_invocation"},
                skill_root,
                errors,
                prefix="policy",
            )
            allow_implicit_invocation = policy.get("allow_implicit_invocation")
            if allow_implicit_invocation is not None and not isinstance(
                allow_implicit_invocation,
                bool,
            ):
                errors.append(
                    f"skill `{skill_root.name}` agent field "
                    "`policy.allow_implicit_invocation` must be a boolean"
                )

    dependencies = payload.get("dependencies")
    if dependencies is not None:
        if not isinstance(dependencies, dict):
            errors.append(
                f"skill `{skill_root.name}` agent field `dependencies` must be an object"
            )
        else:
            reject_skill_agent_unknown_fields(
                dependencies,
                {"tools"},
                skill_root,
                errors,
                prefix="dependencies",
            )
            if "tools" in dependencies:
                tool_dependencies = dependencies["tools"]
                if not isinstance(tool_dependencies, list):
                    errors.append(
                        f"skill `{skill_root.name}` dependencies.tools must be an array"
                    )
                else:
                    for tool in tool_dependencies:
                        if not isinstance(tool, dict) or not all(
                            isinstance(tool.get(field), str) and tool[field].strip()
                            for field in ("type", "value")
                        ):
                            errors.append(
                                f"skill `{skill_root.name}` tool dependencies require type and value strings"
                            )


def reject_skill_agent_unknown_fields(
    payload: dict[str, Any],
    allowed_keys: set[str],
    skill_root: Path,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    for key in sorted(set(payload) - allowed_keys, key=str):
        field = f"{prefix}.{key}" if prefix is not None else key
        errors.append(
            f"skill `{skill_root.name}` agent field `{field}` is not accepted by plugin validation"
        )


def validate_optional_asset_path(
    base_dir: Path,
    allowed_root: Path,
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str = "interface",
) -> None:
    raw_path = payload.get(key)
    if raw_path is None:
        return
    validate_asset_path(base_dir, allowed_root, raw_path, f"{prefix}.{key}", errors)


def validate_asset_path(
    base_dir: Path,
    allowed_root: Path,
    raw_path: Any,
    field: str,
    errors: list[str],
) -> None:
    label = field if field.startswith("skill `") else f"plugin.json field `{field}`"
    if not isinstance(raw_path, str) or not raw_path.strip():
        errors.append(f"{label} must be a non-empty relative path")
        return
    candidate = PurePosixPath(raw_path.replace("\\", "/"))
    if candidate.is_absolute() or any(
        part in {"", ".", ".."} for part in candidate.parts
    ):
        errors.append(f"{label} must stay inside the plugin archive")
        return
    resolved_path = (base_dir / candidate.as_posix()).resolve()
    if not resolved_path.is_relative_to(allowed_root.resolve()):
        errors.append(f"{label} must stay inside the plugin archive")
        return
    if not resolved_path.is_file():
        errors.append(f"{label} points to a missing file")


if __name__ == "__main__":
    main()
