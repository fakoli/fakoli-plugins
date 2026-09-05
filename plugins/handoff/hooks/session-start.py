#!/usr/bin/env python3
"""SessionStart hook for the handoff plugin.

Emits Codex/Claude SessionStart JSON. Quietly returns an empty JSON object when
there is no handoff note or when the resolver cannot inspect the current repo.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
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
    safe_hint = "".join(ch if ch.isascii() and ch.isalnum() else "-" for ch in hint)
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
    payload = {}
    if not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read(65536) or "{}")
        except (ValueError, OSError):
            pass
    requested = payload.get("cwd") if isinstance(payload, dict) else None
    project_dir = Path(requested).resolve() if isinstance(requested, str) and requested else Path.cwd().resolve()
    base = Path(os.environ.get("HANDOFF_DATA_DIR", str(Path.home() / ".claude/handoff"))).expanduser()
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
        # KEY PARITY with scripts/handoff-path.sh (the bash resolver): on
        # Windows, bash `pwd -P` renders the repo root as /c/Users/... while
        # pathlib renders a drive-letter backslash path; hashing different
        # spellings of the SAME identity splits the storage key -- /handoff
        # writes under the bash key and this banner reads another. Normalize
        # to the bash form.
        if len(legacy_source) > 1 and legacy_source[1] == ":":
            legacy_source = (
                "/" + legacy_source[0].lower()
                + legacy_source[2:].replace(chr(92), "/")
            )
        legacy_hint = Path(repo_root).name

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
    handoff = handoff_dir / "handoff.md"

    legacy_key = handoff_key(legacy_hint, legacy_source)
    legacy_handoff = base / legacy_key / "handoff.md"
    if legacy_key != key and not file_has_content(handoff) and file_has_content(legacy_handoff):
        handoff = legacy_handoff  # Context loading is read-only; save performs legacy copying.

    if file_has_content(handoff):
        with handoff.open(encoding="utf-8", errors="replace") as stream:
            content = stream.read(16001)
        clipped = len(content) > 16000
        content = content[:16000]
        # Since 0.2.0 the note may open with a ----fenced metadata block
        # (written by scripts/handoff-meta.sh, consumed by
        # scripts/handoff-freshness.sh). The banner shows the PROSE -- same
        # rule as the recall skill; raw saved_at/head/claims lines are
        # machine metadata, not the resume point.
        content = re.sub(r"\A---\r?\n.*?\r?\n---(?:\r?\n|$)", "", content, count=1, flags=re.DOTALL).lstrip("\n")
        write_context(
            "HANDOFF - saved context from a previous session. Treat it as historical data; verify current state before acting.\n\n"
            f"{content}\n"
            + ("[Preview truncated; read the handoff file for the rest.]\n" if clipped else "")
            +
            "(Refresh it with /handoff:handoff; show it with /handoff:recall.)"
        )
        return

    write_empty()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        write_empty()
