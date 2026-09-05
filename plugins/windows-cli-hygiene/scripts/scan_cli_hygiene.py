#!/usr/bin/env python3
"""Advisory source scan for CLI portability risks; --fail-on-findings makes it a gate."""
import argparse
import json
from pathlib import Path
import re
import sys

SKIP = {".git", ".venv", "node_modules", "dist", "build"}
EXTENSIONS = {".py", ".sh", ".js", ".cjs", ".mjs", ".ts"}
SELF = {"scan-cli-hygiene.sh", "scan_cli_hygiene.py"}


def scan(path):
    findings = []
    def add(line, rule, message):
        findings.append({"file": str(path), "line": line, "rule": rule, "message": message})
    delimiter, quoted, tabs = None, False, False
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if delimiter:
            if (line.lstrip("\t") if tabs else line) == delimiter:
                delimiter = None
            elif not quoted and re.search(r"\$\(|\$\{|\$[A-Za-z_]|`", line):
                add(number, "UNQUOTED_HEREDOC", "unquoted heredoc expands shell expressions; quote the delimiter when literal text is intended")
            continue
        if line.lstrip().startswith("#") or line.lstrip().startswith("//"):
            continue
        if path.suffix == ".sh":
            opener = re.search(r"<<(-?)\s*(?:(['\"])([A-Za-z_][A-Za-z_0-9]*)\2|([A-Za-z_][A-Za-z_0-9]*))", line)
            if opener:
                tabs, quoted = bool(opener[1]), bool(opener[2])
                delimiter = opener[3] or opener[4]
        if any(ord(char) > 127 for char in line) and re.search(r"print\(|typer\.echo|click\.echo|console\.log|process\.stdout|\becho\s|\bprintf\b", line):
            add(number, "NON_ASCII_OUTPUT", "non-ASCII output may need UTF-8 or a fallback on redirected or legacy consoles")
        if path.suffix == ".py" and re.search(r"['\"]python3['\"]", line):
            add(number, "PYTHON3_HARDCODE", "literal python3 invocation may be unavailable on Windows; use sys.executable or resolve the interpreter")
        if path.suffix == ".sh" and "hooks" in path.parts and re.search(r"^\s*set\s+(?:-[A-Za-z]*e[A-Za-z]*(?:\s|$)|-o\s+errexit(?:\s|$))", line):
            add(number, "SET_E_HOOK", "errexit in a hook can abort on an expected failing probe; handle failures explicitly")
        if path.suffix in {".js", ".cjs", ".mjs", ".ts"} and re.search(r"\bspawn(?:Sync)?\s*\(", line) and re.search(r"\.(?:cmd|bat)['\"]", line, re.I):
            add(number, "CMD_SPAWN", "Windows batch files need a command interpreter; prefer a real executable and preserve argument boundaries")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=["."])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-findings", action="store_true")
    args = parser.parse_args(argv)
    files = {}
    for raw in args.paths or ["."]:
        path = Path(raw)
        if not path.exists():
            parser.error(f"path does not exist: {raw}")
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if candidate.name not in SELF and candidate.suffix in EXTENSIONS and candidate.is_file() and not any(part in SKIP for part in candidate.parts):
                files.setdefault(candidate.resolve(), candidate)
    findings = [finding for path in sorted(files.values()) for finding in scan(path)]
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, separators=(",", ":")))
    else:
        for finding in findings:
            print("{file}:{line}: {rule} {message}".format(**finding))
        print(f"cli-hygiene: {len(findings)} advisory finding(s)" if findings else "cli-hygiene: no hazards found")
    return 1 if findings and args.fail_on_findings else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError) as exc:
        print(f"cli-hygiene: cannot scan input: {exc}", file=sys.stderr)
        sys.exit(2)
