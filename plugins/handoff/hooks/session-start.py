#!/usr/bin/env python3
"""SessionStart hook for the handoff plugin.

Emits Codex/Claude SessionStart JSON. Quietly returns an empty JSON object when
there is no handoff note or when the resolver cannot inspect the current repo.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def write_empty() -> None:
    print("{}")


def write_context(text: str) -> None:
    if not text.strip():
        write_empty()
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": text,
                }
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def normalize_remote(url: str) -> str:
    value = url.rstrip("\r").rstrip("/")
    host = ""
    path = ""
    if value.startswith("git@") and ":" in value:
        rest = value[4:]
        host, path = rest.split(":", 1)
    elif value.startswith("ssh://git@") and "/" in value[10:]:
        rest = value[10:]
        host, path = rest.split("/", 1)
    elif value.startswith(("http://", "https://")):
        rest = value.split("://", 1)[1]
        rest = rest.split("@", 1)[-1]
        if "/" not in rest:
            return value
        host, path = rest.split("/", 1)
    else:
        return value

    host = host.lower()
    path = path.rstrip("/").removesuffix(".git")
    if host == "github.com":
        path = path.lower()
    return f"{host}/{path}"


def git_blob_sha1_prefix(text: str) -> str:
    body = text.encode("utf-8")
    data = b"blob " + str(len(body)).encode("ascii") + b"\0" + body
    return hashlib.sha1(data).hexdigest()[:12]


def handoff_key(hint: str, source: str) -> str:
    safe_hint = "".join(ch if ch.isalnum() else "-" for ch in hint)
    return f"{safe_hint}-{git_blob_sha1_prefix(source)}"


def git_stdout(project_dir: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()[0].strip() if result.stdout.strip() else None


def file_has_content(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def main() -> None:
    project_dir = Path.cwd().resolve()
    base = Path.home() / ".claude" / "handoff"
    legacy_source = str(project_dir)
    legacy_hint = project_dir.name

    common = git_stdout(project_dir, "rev-parse", "--git-common-dir")
    if common:
        common_path = Path(common)
        if not common_path.is_absolute():
            common_path = project_dir / common_path
        repo_root = common_path.parent
        try:
            legacy_source = str(repo_root.resolve())
        except OSError:
            legacy_source = str(repo_root)
        legacy_hint = Path(legacy_source).name

    source = legacy_source
    hint = legacy_hint
    remote = git_stdout(project_dir, "remote", "get-url", "origin")
    if remote:
        remote_id = normalize_remote(remote)
        if remote_id:
            source = f"remote:{remote_id}"
            hint = remote_id.rsplit("/", 1)[-1]

    key = handoff_key(hint, source)
    handoff_dir = base / key
    handoff_dir.mkdir(parents=True, exist_ok=True)
    handoff = handoff_dir / "handoff.md"

    legacy_key = handoff_key(legacy_hint, legacy_source)
    legacy_handoff = base / legacy_key / "handoff.md"
    if legacy_key != key and not file_has_content(handoff) and file_has_content(legacy_handoff):
        shutil.copy2(legacy_handoff, handoff)

    if file_has_content(handoff):
        content = handoff.read_text(encoding="utf-8", errors="replace")
        write_context(
            "HANDOFF - resume point for this project (from the last session):\n\n"
            f"{content}\n"
            "(Refresh it with /handoff:handoff; show it with /handoff:recall.)"
        )
        return

    write_empty()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        write_empty()
