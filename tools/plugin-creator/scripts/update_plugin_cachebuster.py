#!/usr/bin/env python3
"""Rewrite a local plugin version to a single Codex cachebuster suffix."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from identifier_validation import SEMVER_RE, validate_plugin_identifier
from json_io import write_json

CACHEBUSTER_PREFIX = "codex"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite a local plugin's version so it preserves everything before '+' and uses "
            "a single +codex.<cachebuster> suffix."
        )
    )
    parser.add_argument("plugin_path", help="Path to the plugin root directory")
    parser.add_argument(
        "--cachebuster",
        help="Optional cachebuster token to embed in the plugin version",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the proposed version without changing files",
    )
    parser.add_argument(
        "--allow-non-semver",
        action="store_true",
        help="Preserve an intentional legacy non-semver base version",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plugin_root = Path(args.plugin_path).expanduser().resolve()
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = load_manifest(manifest_path)

    plugin_name = manifest.get("name")
    if not isinstance(plugin_name, str) or not plugin_name.strip():
        raise ValueError(f"{manifest_path} must contain a non-empty string 'name'.")
    validate_plugin_identifier(plugin_name)

    version = manifest.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"{manifest_path} must contain a non-empty string 'version'.")
    if not args.allow_non_semver and SEMVER_RE.fullmatch(version) is None:
        raise ValueError(
            "Existing version must be semver; use --allow-non-semver only for an intentional legacy version."
        )
    cachebuster = sanitize_cachebuster(
        default_cachebuster() if args.cachebuster is None else args.cachebuster
    )
    next_version = with_cachebuster(version, cachebuster)
    manifest["version"] = next_version
    if not args.dry_run:
        write_json(manifest_path, manifest, force=True)

    print(
        f"{'Would update' if args.dry_run else 'Updated'} plugin version: {version} -> {next_version}"
    )


def load_manifest(manifest_path: Path) -> dict[str, object]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path} must contain a JSON object.")
    return payload


def sanitize_cachebuster(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower())
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")
    if not sanitized:
        raise ValueError("Cachebuster must contain at least one letter or digit.")
    return sanitized


def default_cachebuster() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")


def with_cachebuster(version: str, cachebuster: str) -> str:
    version_prefix = version.split("+", 1)[0]
    return f"{version_prefix}+{CACHEBUSTER_PREFIX}.{cachebuster}"


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001 - CLI should surface a single clear message.
        print(str(err), file=sys.stderr)
        raise SystemExit(1) from err
