#!/usr/bin/env python3
"""Bump linked release versions, regenerate, verify, and optionally stage.

Requires Python 3.11+. Existing generator/validator dependencies still apply.
All edits and generated outputs are restored on a failed command. Git add runs
against a temporary index, preserving the real index on failure. Like git add,
default staging includes existing changes throughout the plugin and catalogs;
use --no-stage to retain control of staging. No commit is created.

Python projects are linked when their normalized project name matches the
plugin, or their static version equals the current plugin version. Local uv
packages, static __version__ assignments, and VERSION files follow that release.
Independent projects, dependency versions, and virtualenvs are left alone.
SemVer alpha/beta/rc prereleases map to PEP 440 for Python metadata; other
prerelease labels are accepted only for plugins without linked Python metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
GENERATED = (
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    "registry/index.json",
    "registry/categories.json",
    "registry/tags.json",
)
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)
SKIP_DIRS = {"node_modules", "vendor", "dist", "build", "__pycache__"}


class BumpError(Exception):
    """An actionable release failure."""


def semver(value: str) -> tuple:
    match = SEMVER.fullmatch(value)
    if not match:
        raise BumpError(f"invalid semantic version: {value!r}")
    major, minor, patch, pre, build = match.groups()
    if pre and any(p.isdigit() and len(p) > 1 and p.startswith("0") for p in pre.split(".")):
        raise BumpError(f"numeric prerelease identifiers cannot have leading zeros: {value}")
    # A final release sorts after every prerelease with the same numeric base.
    precedence = (
        (1,)
        if pre is None
        else (0, tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split(".")))
    )
    return (int(major), int(minor), int(patch), precedence, pre, build)


def next_version(current: str, spec: str, allow_downgrade: bool = False) -> str:
    parsed = semver(current)
    major, minor, patch = parsed[:3]
    # Keywords advance the numeric component and clear prerelease/build labels;
    # use an explicit version to promote an RC to the same numeric release.
    new = {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }.get(spec, spec)
    target = semver(new)
    if target[:4] < parsed[:4] and not allow_downgrade:
        raise BumpError(f"refusing downgrade {current} -> {new}; use --allow-downgrade explicitly")
    return new


def python_version(value: str) -> str:
    parsed = semver(value)
    version = ".".join(str(part) for part in parsed[:3])
    if parsed[4]:
        match = re.fullmatch(r"(alpha|a|beta|b|rc)[.-]?([0-9]+)", parsed[4])
        if not match:
            raise BumpError(
                f"{value!r} cannot map to Python metadata; use alpha.N, beta.N, or rc.N"
            )
        label = {"alpha": "a", "beta": "b"}.get(match[1], match[1])
        version += label + str(int(match[2]))
    if parsed[5]:
        local = re.sub(r"[-.]", ".", parsed[5]).lower()
        if any(not p or not p.isalnum() for p in local.split(".")):
            raise BumpError(f"{value!r} cannot map to a Python local version")
        version += "+" + ".".join(str(int(p)) if p.isdigit() else p for p in local.split("."))
    return version


def normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def confined(root: Path, path: Path) -> Path:
    """Reject traversal, symlink ancestors/targets, and non-regular targets."""
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise BumpError(f"path outside repository: {path}") from exc
    if ".." in relative.parts:
        raise BumpError(f"path traversal: {path}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise BumpError(f"refusing symlink: {cursor}")
    if path.exists() and not path.is_file():
        raise BumpError(f"expected a regular file: {path}")
    return path


def read_text(root: Path, path: Path) -> str:
    return confined(root, path).read_text(encoding="utf-8")


def json_version(text: str, current: str, new: str, path: Path, plugin: str) -> str:
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("name") != plugin or data.get("version") != current:
        raise BumpError(f"manifest name/version drift in {path}; expected {plugin} {current}")
    # Walk top-level tokens so nested version fields and formatting survive.
    decoder = json.JSONDecoder()
    offset = text.index("{") + 1
    while True:
        offset += len(text[offset:]) - len(text[offset:].lstrip())
        key, offset = decoder.raw_decode(text, offset)
        offset = text.index(":", offset) + 1
        offset += len(text[offset:]) - len(text[offset:].lstrip())
        start = offset
        _, offset = decoder.raw_decode(text, offset)
        if key == "version":
            return text[:start] + json.dumps(new) + text[offset:]
        offset += len(text[offset:]) - len(text[offset:].lstrip())
        offset += 1  # comma (a validated version key is still ahead)


def replace_assignment(text: str, key: str, old: str, new: str, path: Path) -> str:
    pattern = rf"(?m)^(\s*{re.escape(key)}\s*=\s*)(['\"]){re.escape(old)}\2"
    updated, count = re.subn(pattern, lambda m: m[1] + m[2] + new + m[2], text)
    if count != 1:
        raise BumpError(f"expected one static {key} = {old!r} assignment in {path}")
    return updated


def project_version(text: str, old: str, new: str, path: Path) -> str:
    match = re.search(r"(?m)^\s*\[project\]\s*(?:#.*)?$", text)
    if not match:
        raise BumpError(f"unsupported [project] table layout in {path}")
    following = re.search(r"(?m)^\s*\[", text[match.end() :])
    end = match.end() + following.start() if following else len(text)
    return (
        text[: match.end()]
        + replace_assignment(text[match.end() : end], "version", old, new, path)
        + text[end:]
    )


def lock_version(text: str, name: str, old: str, new: str, path: Path) -> str:
    blocks = re.split(r"(?m)(?=^\[\[package\]\]\s*(?:#.*)?$)", text)
    count = 0
    for index, block in enumerate(blocks[1:], 1):
        package = tomllib.loads(block)["package"][0]
        if normalized_name(package["name"]) != normalized_name(name):
            continue
        if not any(key in package.get("source", {}) for key in ("editable", "virtual", "path")):
            continue
        if package.get("version") != old:
            raise BumpError(f"local package version drift in {path}: {name}")
        end = re.search(r"(?m)^\[package\.", block)
        split = end.start() if end else len(block)
        blocks[index] = replace_assignment(block[:split], "version", old, new, path) + block[split:]
        count += 1
    if count != 1:
        raise BumpError(f"expected one local package {name!r} in {path}; found {count}")
    result = "".join(blocks)
    tomllib.loads(result)
    return result


def files_under(plugin: Path) -> list[Path]:
    files = []
    for directory, dirs, names in os.walk(plugin):
        dirs[:] = sorted(
            d
            for d in dirs
            if not d.startswith(".")
            and d not in SKIP_DIRS
            and not (Path(directory) / d).is_symlink()
        )
        files.extend(Path(directory) / name for name in sorted(names))
    return files


def plan_edits(root: Path, plugin: str, current: str, new: str) -> dict[Path, bytes]:
    plugin_root = root / "plugins" / plugin
    edits = {}
    for host in ("claude", "codex", "cursor"):
        path = plugin_root / f".{host}-plugin/plugin.json"
        confined(root, path)
        if path.exists():
            edits[path] = json_version(read_text(root, path), current, new, path, plugin).encode()

    files = files_under(plugin_root)
    projects = {}
    try:
        old_python = python_version(current)
    except BumpError:
        old_python = current  # A plugin without Python may use any SemVer label.
    for path in (p for p in files if p.name == "pyproject.toml"):
        source = read_text(root, path)
        project = tomllib.loads(source).get("project", {})
        version, name = project.get("version"), project.get("name", "")
        if version is None:
            continue  # Dynamic metadata is not a static release source.
        if normalized_name(name) != normalized_name(plugin) and version not in (
            current,
            old_python,
        ):
            continue
        if version not in (current, old_python):
            raise BumpError(f"Python project version drift in {path}: {version} != {current}")
        new_python = python_version(new)
        edits[path] = project_version(source, version, new_python, path).encode()
        projects[path.parent] = (version, new_python)
        lock = path.parent / "uv.lock"
        confined(root, lock)
        if lock.exists():
            edits[lock] = lock_version(
                read_text(root, lock), name, old_python, new_python, lock
            ).encode()

    for path in files:
        if path.name not in ("__init__.py", "VERSION"):
            continue
        containing = [p for p in projects if path.is_relative_to(p)]
        project_root = max(containing, key=lambda p: len(p.parts)) if containing else None
        # A nested independent project must not inherit its parent's release.
        if project_root and any(
            (p / "pyproject.toml").exists() and p not in projects
            for p in path.parents
            if p != project_root and p.is_relative_to(project_root)
        ):
            continue
        if not project_root and path != plugin_root / "VERSION":
            continue
        source = read_text(root, path)
        old, target = projects[project_root] if project_root else (current, new)
        if path == plugin_root / "VERSION":
            old, target = current, new
        if path.name == "VERSION":
            if source.strip() != old:
                raise BumpError(f"VERSION drift in {path}: expected {old}")
            edits[path] = source.replace(old, target, 1).encode()
        else:
            match = re.search(r"(?m)^__version__\s*=\s*(['\"])([^'\"]+)\1", source)
            if match:
                if match[2] != old:
                    raise BumpError(f"__version__ drift in {path}: expected {old}")
                edits[path] = replace_assignment(source, "__version__", old, target, path).encode()
    return edits


def snapshot(path: Path) -> tuple[bytes, int] | None:
    if not path.exists():
        return None
    return path.read_bytes(), stat.S_IMODE(path.stat().st_mode)


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.bump-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def command(root: Path, argv: list[str], env: dict | None = None) -> str:
    result = subprocess.run(argv, cwd=root, env=env, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise BumpError(
            f"{Path(argv[0]).name} failed ({result.returncode})"
            + (f":\n{detail}" if detail else "")
        )
    return result.stdout.strip()


def stage(root: Path, paths: list[str]) -> None:
    git_env = os.environ.copy()
    # Honor a caller's deliberate GIT_INDEX_FILE, like ordinary `git add`.
    index = Path(command(root, ["git", "rev-parse", "--git-path", "index"], git_env))
    if not index.is_absolute():
        index = root / index
    if any(path.is_symlink() for path in (index, *index.parents)):
        raise BumpError(f"refusing symlink Git index: {index}")
    original = snapshot(index)
    fd, temporary = tempfile.mkstemp(prefix="bump-index-", dir=index.parent)
    os.close(fd)
    temp_index = Path(temporary)
    lock = index.with_name(index.name + ".lock")
    owns_lock = False
    try:
        if original:
            temp_index.write_bytes(original[0])
            temp_index.chmod(original[1])
        else:
            temp_index.unlink()  # Git initializes an absent index, not an empty file.
        git_env["GIT_INDEX_FILE"] = str(temp_index)
        command(root, ["git", "add", "--", *paths], git_env)
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        owns_lock = True
        os.close(lock_fd)
        if snapshot(index) != original:
            raise BumpError(
                "Git index changed concurrently; release rolled back; retry after staging finishes"
            )
        os.replace(temp_index, lock)
        os.replace(lock, index)
        owns_lock = False
    finally:
        temp_index.unlink(missing_ok=True)
        temp_index.with_name(temp_index.name + ".lock").unlink(missing_ok=True)
        if owns_lock:
            lock.unlink(missing_ok=True)


def apply_release(root: Path, plugin: str, edits: dict[Path, bytes], should_stage: bool) -> None:
    paths = list(edits) + [root / p for p in GENERATED]
    for path in paths:
        confined(root, path)
    # Serialize this helper, including its shared generated files. Other tools
    # should not edit those same release files during this invocation.
    lock = root / ".bump-plugin.lock"
    confined(root, lock)
    lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(lock_fd)
    originals = {}
    absent_dirs = set()
    try:
        originals = {path: snapshot(path) for path in paths}
        for path in paths:
            absent_dirs.update(p for p in path.parents if p.is_relative_to(root) and not p.exists())
        for path, data in edits.items():
            atomic_write(path, data, originals[path][1])
        command(root, [str(root / "scripts/generate-index.sh")])
        command(root, [str(root / "scripts/check-registry-drift.sh")])
        command(root, [str(root / "scripts/validate.sh"), f"plugins/{plugin}"])
        if (root / "scripts/validate.py").is_file():
            command(root, ["uv", "run", "--script", "scripts/validate.py", f"plugins/{plugin}"])
        if should_stage:
            stage(
                root,
                [
                    f"plugins/{plugin}",
                    ".claude-plugin/marketplace.json",
                    ".agents/plugins/marketplace.json",
                    "registry",
                ],
            )
    except BaseException:
        for path, original in originals.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, *original)
        for directory in sorted(absent_dirs, key=lambda p: len(p.parts), reverse=True):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
        raise
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("plugin", help="plugin directory name (lowercase kebab-case)")
    parser.add_argument(
        "spec", help="major, minor, patch, or an explicit SemVer (including prerelease/build)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preflight and print the plan without writing or staging",
    )
    parser.add_argument(
        "--no-stage",
        action="store_true",
        help="edit/regenerate/verify; leave the Git index untouched",
    )
    parser.add_argument(
        "--allow-downgrade", action="store_true", help="explicitly allow a lower SemVer"
    )
    args = parser.parse_args(argv)
    try:
        if not NAME.fullmatch(args.plugin):
            raise BumpError("plugin must be a lowercase kebab-case directory name (no paths)")
        manifest = ROOT / "plugins" / args.plugin / ".claude-plugin/plugin.json"
        data = json.loads(read_text(ROOT, manifest))
        if not isinstance(data, dict):
            raise BumpError(f"manifest must be a JSON object: {manifest}")
        current = data.get("version")
        if not isinstance(current, str):
            raise BumpError(f"missing string version in {manifest}")
        new = next_version(current, args.spec, args.allow_downgrade)
        edits = plan_edits(ROOT, args.plugin, current, new)
        for relative in GENERATED:
            confined(ROOT, ROOT / relative)
        if new == current:
            print(f"bump: {args.plugin} already at {current}; nothing to do")
            return 0
        print(
            f"bump: {args.plugin} {current} -> {new}" + (" [DRY RUN]" if args.dry_run else ""),
            flush=True,
        )
        if args.dry_run:
            for path in edits:
                print(f"  would edit {path.relative_to(ROOT)}")
            print("  would run scripts/generate-index.sh (both marketplaces + registry)")
            print(
                f"  would verify scripts/check-registry-drift.sh + scripts/validate.sh plugins/{args.plugin}"
            )
            if (ROOT / "scripts/validate.py").is_file():
                print(f"  would verify uv run --script scripts/validate.py plugins/{args.plugin}")
            print(
                "  staging skipped (--no-stage)"
                if args.no_stage
                else f"  would stage plugins/{args.plugin} .claude-plugin/marketplace.json .agents/plugins/marketplace.json registry/"
            )
            return 0
        apply_release(ROOT, args.plugin, edits, not args.no_stage)
        print(
            f"bump: verified {args.plugin} {new}; "
            + ("not staged (--no-stage)" if args.no_stage else "staged")
        )
        print(f"  next: add a plugins/{args.plugin}/CHANGELOG.md entry for {new}, then commit.")
        return 0
    except (BumpError, OSError, ValueError, TypeError) as exc:
        print(f"bump-plugin: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
