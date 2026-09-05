#!/usr/bin/env python3
"""Scaffold a plugin directory and optionally update marketplace.json."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from identifier_validation import validate_marketplace_name, validate_plugin_identifier
from json_io import load_json, local_source_path, marketplace_root, write_json

MAX_PLUGIN_NAME_LENGTH = 64
DEFAULT_INSTALL_POLICY = "AVAILABLE"
DEFAULT_AUTH_POLICY = "ON_INSTALL"
DEFAULT_CATEGORY = "Productivity"
DEFAULT_MARKETPLACE_NAME = "personal"
VALID_INSTALL_POLICIES = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
VALID_AUTH_POLICIES = {"ON_INSTALL", "ON_USE"}
DEFAULT_PLUGIN_PARENT = Path.home() / "plugins"
DEFAULT_MARKETPLACE_PATH = Path.home() / ".agents" / "plugins" / "marketplace.json"


def normalize_plugin_name(plugin_name: str) -> str:
    """Normalize a plugin name to lowercase hyphen-case."""
    normalized = plugin_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized


def validate_plugin_name(plugin_name: str) -> None:
    if not plugin_name:
        raise ValueError("Plugin name must include at least one letter or digit.")
    if len(plugin_name) > MAX_PLUGIN_NAME_LENGTH:
        raise ValueError(
            f"Plugin name '{plugin_name}' is too long ({len(plugin_name)} characters). "
            f"Maximum is {MAX_PLUGIN_NAME_LENGTH} characters."
        )


def display_name_from_plugin_name(plugin_name: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", plugin_name))


def build_plugin_json(
    plugin_name: str, *, with_mcp: bool, with_apps: bool, with_skills: bool = True
) -> dict[str, Any]:
    display_name = display_name_from_plugin_name(plugin_name)
    payload: dict[str, Any] = {
        "name": plugin_name,
        "version": "0.1.0",
        "description": f"{display_name} plugin",
        "author": {
            "name": "Local developer",
        },
        "interface": {
            "displayName": display_name,
            "shortDescription": f"Use {display_name} in Codex.",
            "longDescription": f"{display_name} adds a local Codex plugin scaffold.",
            "developerName": "Local developer",
            "category": DEFAULT_CATEGORY,
            "capabilities": [],
            "defaultPrompt": [f"Help me use {display_name}."],
        },
    }
    if with_skills:
        payload["skills"] = "./skills/"
    if with_mcp:
        payload["mcpServers"] = "./.mcp.json"
    if with_apps:
        payload["apps"] = "./.app.json"
    return payload


def build_marketplace_entry(
    plugin_name: str,
    install_policy: str,
    auth_policy: str,
    category: str,
    source_path: str | None = None,
) -> dict[str, Any]:
    return {
        "name": plugin_name,
        "source": {
            "source": "local",
            "path": source_path or f"./plugins/{plugin_name}",
        },
        "policy": {
            "installation": install_policy,
            "authentication": auth_policy,
        },
        "category": category,
    }


def build_default_marketplace(marketplace_name: str) -> dict[str, Any]:
    return {
        "name": marketplace_name,
        "interface": {
            "displayName": display_name_from_plugin_name(marketplace_name),
        },
        "plugins": [],
    }


def validate_marketplace_interface(payload: dict[str, Any]) -> None:
    interface = payload.get("interface")
    if interface is not None and not isinstance(interface, dict):
        raise ValueError("marketplace.json field 'interface' must be an object.")


def load_validated_marketplace(
    marketplace_path: Path,
    marketplace_name: str | None,
    plugin_name: str,
    force: bool,
) -> dict[str, Any]:
    if marketplace_path.exists():
        payload = load_json(marketplace_path)
    else:
        payload = build_default_marketplace(
            marketplace_name or DEFAULT_MARKETPLACE_NAME
        )

    if not isinstance(payload, dict):
        raise ValueError(f"{marketplace_path} must contain a JSON object.")

    validate_marketplace_interface(payload)

    existing_marketplace_name = payload.get("name")
    if (
        not isinstance(existing_marketplace_name, str)
        or not existing_marketplace_name.strip()
    ):
        raise ValueError(f"{marketplace_path} must contain a non-empty string 'name'.")
    validate_marketplace_name(existing_marketplace_name)

    if marketplace_name is not None:
        if existing_marketplace_name != marketplace_name:
            raise ValueError(
                f"{marketplace_path} already uses marketplace name "
                f"'{existing_marketplace_name}'. Create a new marketplace file to use "
                f"'{marketplace_name}' instead."
            )

    plugins = payload.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError(f"{marketplace_path} field 'plugins' must be an array.")
    matches = [
        entry
        for entry in plugins
        if isinstance(entry, dict) and entry.get("name") == plugin_name
    ]
    if len(matches) > 1:
        raise ValueError(
            f"Duplicate marketplace entries for '{plugin_name}'. Resolve them before updating."
        )
    if not force and any(
        isinstance(entry, dict) and entry.get("name") == plugin_name
        for entry in plugins
    ):
        raise FileExistsError(
            f"Marketplace entry '{plugin_name}' already exists in {marketplace_path}. "
            "Use --force to overwrite that entry."
        )

    return payload


def update_marketplace_json(
    marketplace_path: Path,
    marketplace_name: str | None,
    plugin_name: str,
    install_policy: str | None,
    auth_policy: str | None,
    category: str | None,
    force: bool,
    plugin_root: Path | None = None,
) -> None:
    payload = load_validated_marketplace(
        marketplace_path, marketplace_name, plugin_name, force
    )
    plugins = payload["plugins"]

    new_entry = build_marketplace_entry(
        plugin_name,
        install_policy or DEFAULT_INSTALL_POLICY,
        auth_policy or DEFAULT_AUTH_POLICY,
        category or DEFAULT_CATEGORY,
        local_source_path(plugin_root, marketplace_path)
        if plugin_root is not None
        else None,
    )

    for index, entry in enumerate(plugins):
        if isinstance(entry, dict) and entry.get("name") == plugin_name:
            # Preserve source selectors, product policy, metadata, and list order.
            # --force permits adding missing fields, not repointing a live entry.
            expected_root = (
                plugin_root
                or marketplace_root(marketplace_path) / "plugins" / plugin_name
            )
            validate_existing_source(entry, expected_root, marketplace_path)
            policy = entry.setdefault("policy", {})
            if not isinstance(policy, dict):
                raise ValueError(
                    f"Marketplace entry '{plugin_name}' policy must be an object."
                )
            for key, explicit, default in (
                ("installation", install_policy, DEFAULT_INSTALL_POLICY),
                ("authentication", auth_policy, DEFAULT_AUTH_POLICY),
            ):
                if explicit is not None or key not in policy:
                    policy[key] = explicit or default
            if category is not None or "category" not in entry:
                entry["category"] = category or DEFAULT_CATEGORY
            break
    else:
        plugins.append(new_entry)

    write_json(marketplace_path, payload, force=True)


def validate_existing_source(
    entry: dict[str, Any], plugin_root: Path, marketplace_path: Path
) -> None:
    source = entry.get("source")
    raw_path = (
        source
        if isinstance(source, str)
        else (
            source.get("path")
            if isinstance(source, dict) and source.get("source") == "local"
            else None
        )
    )
    if (
        not isinstance(raw_path, str)
        or (marketplace_root(marketplace_path) / raw_path).resolve()
        != plugin_root.resolve()
    ):
        raise ValueError(
            f"Existing marketplace entry '{entry.get('name')}' points to a different source. "
            "Refusing to repoint it, including with --force."
        )


def create_stub_file(path: Path, payload: dict, force: bool) -> None:
    # Existing companion configuration is user-authored, even under --force.
    if path.exists():
        return
    write_json(path, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a plugin skeleton with a validation-ready plugin.json."
    )
    parser.add_argument("plugin_name")
    parser.add_argument(
        "--path",
        default=str(DEFAULT_PLUGIN_PARENT),
        help=(
            "Parent directory for plugin creation (defaults to <home>/plugins). "
            "Pass an explicit repo path only when a repo/team plugin is intended."
        ),
    )
    parser.add_argument(
        "--with-skills", action="store_true", help="Create skills/ directory"
    )
    parser.add_argument(
        "--with-hooks",
        action="store_true",
        help="Create an empty hooks/hooks.json (no commands)",
    )
    parser.add_argument(
        "--with-scripts", action="store_true", help="Create scripts/ directory"
    )
    parser.add_argument(
        "--with-assets", action="store_true", help="Create assets/ directory"
    )
    parser.add_argument(
        "--with-mcp", action="store_true", help="Create .mcp.json placeholder"
    )
    parser.add_argument(
        "--with-apps", action="store_true", help="Create .app.json placeholder"
    )
    parser.add_argument(
        "--with-marketplace",
        action="store_true",
        help=(
            "Create or update <home>/.agents/plugins/marketplace.json by default. "
            "Derive source.path from the actual plugin location relative to the marketplace root."
        ),
    )
    parser.add_argument(
        "--marketplace-path",
        default=str(DEFAULT_MARKETPLACE_PATH),
        help=(
            "Path to marketplace.json (defaults to <home>/.agents/plugins/marketplace.json). "
            "Pass a repo-rooted marketplace path only when a repo/team plugin is intended."
        ),
    )
    parser.add_argument(
        "--marketplace-name",
        help=(
            "Marketplace name to seed into a new marketplace.json. Use this only when the default "
            "'personal' marketplace name is already taken and you need a different new marketplace."
        ),
    )
    parser.add_argument(
        "--install-policy",
        default=None,
        choices=sorted(VALID_INSTALL_POLICIES),
        help="Marketplace policy.installation value",
    )
    parser.add_argument(
        "--auth-policy",
        default=None,
        choices=sorted(VALID_AUTH_POLICIES),
        help="Marketplace policy.authentication value",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Marketplace category value",
    )
    parser.add_argument(
        "--marketplace-only",
        action="store_true",
        help="Register an existing plugin without changing its files; requires --with-marketplace",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Extend an existing scaffold/marketplace entry; preserve existing metadata, sources, and companion files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_plugin_name = args.plugin_name
    plugin_name = (
        raw_plugin_name
        if args.marketplace_only
        else normalize_plugin_name(raw_plugin_name)
    )
    if plugin_name != raw_plugin_name:
        print(
            f"Note: Normalized plugin name from '{raw_plugin_name}' to '{plugin_name}'."
        )
    if args.marketplace_only:
        validate_plugin_identifier(plugin_name)
        if not args.with_marketplace:
            raise ValueError("--marketplace-only requires --with-marketplace.")
    else:
        validate_plugin_name(plugin_name)
    marketplace_name = None
    if args.marketplace_name is not None:
        marketplace_name = args.marketplace_name.strip()
        validate_marketplace_name(marketplace_name)

    plugin_root = Path(args.path).expanduser().resolve() / plugin_name
    plugin_json_path = plugin_root / ".codex-plugin" / "plugin.json"
    if plugin_root.is_symlink() or plugin_json_path.parent.is_symlink():
        raise ValueError(
            "Refusing to scaffold through a symlinked plugin or manifest directory."
        )
    if plugin_json_path.parent.exists() and not plugin_json_path.parent.is_dir():
        raise ValueError(
            f"Manifest parent must be a directory: {plugin_json_path.parent}"
        )
    manifest = None
    if args.marketplace_only or plugin_json_path.exists():
        manifest = load_json(plugin_json_path)
        if manifest.get("name") != plugin_name:
            raise ValueError(
                "Existing plugin manifest name does not match the selected plugin name."
            )
        if not args.marketplace_only and not args.force:
            raise FileExistsError(
                f"{plugin_json_path} already exists. Use --force to extend it."
            )
    if plugin_json_path.is_symlink():
        raise ValueError(f"Refusing to write through symlink: {plugin_json_path}")

    if args.with_marketplace:
        marketplace_path = Path(args.marketplace_path).expanduser().absolute()
        if marketplace_path.is_symlink():
            raise ValueError(f"Refusing to overwrite symlink: {marketplace_path}")
        local_source_path(plugin_root, marketplace_path)
        marketplace = load_validated_marketplace(
            marketplace_path, marketplace_name, plugin_name, args.force
        )
        for entry in marketplace["plugins"]:
            if isinstance(entry, dict) and entry.get("name") == plugin_name:
                validate_existing_source(entry, plugin_root, marketplace_path)
                if "policy" in entry and not isinstance(entry["policy"], dict):
                    raise ValueError(
                        "Existing marketplace entry policy must be an object."
                    )

    optional_directories = {
        "skills": args.with_skills,
        "hooks": args.with_hooks,
        "scripts": args.with_scripts,
        "assets": args.with_assets,
    }
    if not args.marketplace_only:
        # Check directory conflicts before any writes.
        for folder, enabled in optional_directories.items():
            target = plugin_root / folder
            if enabled and (
                target.is_symlink() or (target.exists() and not target.is_dir())
            ):
                raise ValueError(f"Cannot create scaffold directory: {target}")
        for relative, enabled in (
            (".mcp.json", args.with_mcp),
            (".app.json", args.with_apps),
            ("hooks/hooks.json", args.with_hooks),
        ):
            target = plugin_root / relative
            if enabled and (
                target.is_symlink() or (target.exists() and not target.is_file())
            ):
                raise ValueError(f"Cannot create scaffold companion file: {target}")
        for folder, enabled in optional_directories.items():
            if enabled:
                (plugin_root / folder).mkdir(parents=True, exist_ok=True)
        if args.with_mcp:
            create_stub_file(plugin_root / ".mcp.json", {"mcpServers": {}}, args.force)
        if args.with_apps:
            create_stub_file(plugin_root / ".app.json", {"apps": {}}, args.force)
        if args.with_hooks:
            create_stub_file(
                plugin_root / "hooks" / "hooks.json", {"hooks": {}}, args.force
            )
        if manifest is None:
            manifest = build_plugin_json(
                plugin_name,
                with_mcp=args.with_mcp,
                with_apps=args.with_apps,
                with_skills=args.with_skills,
            )
        else:
            for field, enabled, path in (
                ("skills", args.with_skills, "./skills/"),
                ("mcpServers", args.with_mcp, "./.mcp.json"),
                ("apps", args.with_apps, "./.app.json"),
            ):
                if enabled:
                    manifest.setdefault(field, path)
        write_json(plugin_json_path, manifest, args.force)

    if args.with_marketplace:
        update_marketplace_json(
            marketplace_path,
            marketplace_name,
            plugin_name,
            args.install_policy,
            args.auth_policy,
            args.category,
            args.force,
            plugin_root,
        )

    print(
        f"{'Registered' if args.marketplace_only else 'Created or extended'} plugin: {plugin_root}"
    )
    print(f"plugin manifest: {plugin_json_path}")
    if args.with_marketplace:
        print(f"marketplace manifest: {marketplace_path}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
