#!/usr/bin/env python3
"""Map changed Git paths to local verification commands. Listing never executes gates."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=30)
    if result.returncode:
        raise ValueError("git " + args[0] + " failed: " + result.stderr.decode(errors="replace").strip())
    return result.stdout


def glob_regex(pattern):
    result, i = "", 0
    while i < len(pattern):
        if pattern[i:i+3] == "**/":
            result += "(?:.*/)?"; i += 3
        elif pattern[i:i+2] == "**":
            result += ".*"; i += 2
        elif pattern[i] == "*":
            result += "[^/]*"; i += 1
        elif pattern[i] == "?":
            result += "[^/]"; i += 1
        else:
            result += re.escape(pattern[i]); i += 1
    return re.compile(result, re.DOTALL)


def read_rules(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError("config needs a closed --- frontmatter block")
    rules, in_rules = [], False
    for line in lines[1:lines.index("---", 1)]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.strip() == "rules:":
            in_rules = True
            continue
        if not in_rules or not re.match(r"^\s+-\s+", line) or "=>" not in line:
            raise ValueError("config rules must use '- glob => command'")
        pattern, command = re.sub(r"^\s+-\s+", "", line).split("=>", 1)
        pattern, command = pattern.strip(), command.strip()
        if pattern[:1] in ("'", '"'):
            if len(pattern) < 2 or pattern[-1] != pattern[0]:
                raise ValueError("unclosed quoted glob")
            pattern = pattern[1:-1]
        if not pattern or not command:
            raise ValueError("empty glob or command")
        # The placeholder is shell syntax, not a substring inside quoted data.
        # Quoting it twice would turn "$@" into an unsafe/unusable expansion.
        masked = command.replace("{files}", "FILES_PLACEHOLDER")
        try:
            lexer = shlex.shlex(masked, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError as exc:
            raise ValueError("unclosed shell quoting in gate command") from exc
        if "{files}" in command and ("'{files}'" in command or '"{files}"' in command or
                                     any("FILES_PLACEHOLDER" in t and t != "FILES_PLACEHOLDER" for t in tokens)):
            raise ValueError("use {files} as a standalone, unquoted argument")
        rules.append((glob_regex(pattern), command))
    if not rules:
        raise ValueError("config has no rules")
    return rules


def route(project, base=None):
    root = Path(os.fsdecode(git(project, "rev-parse", "--show-toplevel")).strip()).resolve()
    config = project / ".claude/gate-router.local.md"
    rules = read_rules(config)
    if base is None:
        probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "origin/main^{commit}"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        base = "origin/main" if probe.returncode == 0 else "HEAD"
    # Resolve to an object ID, preventing option confusion and detecting bad refs.
    revision = git(root, "rev-parse", "--verify", "--end-of-options", base + "^{commit}").strip().decode("ascii")
    paths = set()
    for args in (("diff", "--name-only", "--no-renames", "-z", revision, "--"),
                 ("diff", "--name-only", "--no-renames", "--cached", "-z", "--"),
                 ("diff", "--name-only", "--no-renames", "-z", "--"),
                 ("ls-files", "--others", "--exclude-standard", "-z")):
        paths.update(os.fsdecode(value) for value in git(root, *args).split(b"\0") if value)
    paths.discard(config.relative_to(root).as_posix())
    changed = sorted(paths)
    commands = {}
    for regex, command in rules:
        hits = [name for name in changed if regex.fullmatch(name)]
        if hits:
            current = commands.setdefault(command, [])
            current.extend(name for name in hits if name not in current)
    return root, base, changed, [{"command": command, "files": files} for command, files in commands.items()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", nargs="?", default=".")
    parser.add_argument("--base")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--list", action="store_true")
    modes.add_argument("--run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.run and args.json:
        parser.error("--json is a listing mode; combine it with --list")
    project = Path(args.project_dir).expanduser().resolve()
    if not project.is_dir():
        raise ValueError("project directory does not exist")
    if not (project / ".claude/gate-router.local.md").is_file():
        print("gate-router: no config at .claude/gate-router.local.md (nothing to enforce)", file=sys.stderr)
        if args.json:
            print('{"changed":0,"gates":[]}')
        return 0
    root, base, changed, gates = route(project, args.base)
    if args.json:
        print(json.dumps({"changed": len(changed), "gates": gates}, separators=(",", ":")))
        return 0
    if not changed:
        print("gate-router: no changed files vs " + base)
    elif not gates:
        print("gate-router: changed files match no gates")
    for gate in gates:
        command, files = gate["command"], gate["files"]
        if not args.run:
            print(command.replace("{files}", shlex.join(files)))
            continue
        print("gate-router: RUN " + command, flush=True)
        result = subprocess.run(["bash", "-c", command.replace("{files}", '"$@"'), "gate-router", *files], cwd=root)
        if result.returncode:
            rc = result.returncode if result.returncode > 0 else 128 - result.returncode
            print(f"gate-router: GATE FAILED ({rc}): {command}", file=sys.stderr)
            return rc
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"gate-router: {exc}", file=sys.stderr)
        sys.exit(2)
