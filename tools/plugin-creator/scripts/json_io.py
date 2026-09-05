"""Small UTF-8 JSON helpers for local plugin maintenance."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, data: dict[str, Any], force: bool = False) -> None:
    """Write complete JSON without truncating a file if serialization fails.

    Refuse symlinks; replacing a manifest should not silently replace a link or
    edit a different source. Preserve permissions on intentional replacements.
    """
    contents = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if path.is_symlink():
        raise ValueError(f"Refusing to overwrite symlink: {path}")
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to replace it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(contents)
        if path.exists():
            temporary_path.chmod(path.stat().st_mode & 0o777)
        else:
            temporary_path.chmod(0o644)
        if force:
            temporary_path.replace(path)
        else:
            # link() fails if another writer created the destination meanwhile.
            os.link(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def marketplace_root(marketplace_path: Path) -> Path:
    """Resolve the documented repo/home layouts; direct JSON uses its parent."""
    path = marketplace_path.expanduser().absolute()
    if path.parent.name == "plugins" and path.parent.parent.name == ".agents":
        return path.parent.parent.parent.resolve()
    if path.parent.name == ".claude-plugin":
        return path.parent.parent.resolve()
    return path.parent.resolve()


def local_source_path(plugin_root: Path, marketplace_path: Path) -> str:
    root = marketplace_root(marketplace_path)
    try:
        relative = plugin_root.resolve().relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"Plugin {plugin_root} must be inside marketplace root {root}. "
            "Choose a marketplace in a common parent; no files were relocated."
        ) from error
    return "./" + relative.as_posix()
