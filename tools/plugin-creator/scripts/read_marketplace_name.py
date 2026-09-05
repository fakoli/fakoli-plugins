#!/usr/bin/env python3
"""Print the top-level marketplace name from any marketplace.json file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from create_basic_plugin import validate_existing_source
from identifier_validation import validate_marketplace_name, validate_plugin_identifier
from json_io import load_json


def default_marketplace_path() -> Path:
    return Path.home() / ".agents" / "plugins" / "marketplace.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print the top-level marketplace name from marketplace.json. Defaults to the personal "
            "marketplace path under the current home directory."
        )
    )
    parser.add_argument(
        "--marketplace-path",
        default=str(default_marketplace_path()),
        help="Path to marketplace.json",
    )
    parser.add_argument(
        "--plugin-path",
        help="Also verify that the selected marketplace points to this local plugin",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    marketplace_path = Path(args.marketplace_path).expanduser().resolve()
    payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{marketplace_path} must contain a JSON object.")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{marketplace_path} must contain a non-empty string 'name'.")
    validate_marketplace_name(name)
    if args.plugin_path:
        plugin_root = Path(args.plugin_path).expanduser().resolve()
        manifest = load_json(plugin_root / ".codex-plugin" / "plugin.json")
        plugin_name = manifest.get("name")
        if not isinstance(plugin_name, str):
            raise ValueError("Plugin manifest must contain a string name.")
        validate_plugin_identifier(plugin_name)
        entries = payload.get("plugins")
        if not isinstance(entries, list):
            raise ValueError("Marketplace plugins must be an array.")
        matching = [
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("name") == plugin_name
        ]
        if len(matching) != 1:
            raise ValueError(
                f"Expected exactly one marketplace entry for '{plugin_name}'."
            )
        validate_existing_source(matching[0], plugin_root, marketplace_path)
    print(name)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001 - CLI should surface a single clear message.
        print(str(err), file=sys.stderr)
        raise SystemExit(1) from err
