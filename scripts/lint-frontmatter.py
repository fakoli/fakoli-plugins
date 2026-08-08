#!/usr/bin/env python3
"""Validate the YAML frontmatter of a skill or command markdown file.

Catches the class of bug that `validate.sh`'s JSON/path checks miss entirely:
a SKILL.md or command `.md` whose `--- ... ---` frontmatter is not valid YAML
(e.g. `argument-hint: "PR title" [--flag]` — a quoted scalar followed by junk),
which makes Claude Code silently ignore the whole block.

For files named exactly `SKILL.md`, also enforces that the frontmatter `name`
is present, matches the parent directory name, and is a valid slug
(`^[a-z0-9]+(-[a-z0-9]+)*$`, 1-64 chars) — otherwise a rename of the skill
directory silently orphans the advertised name.

Usage:  lint-frontmatter.py <file.md> [<file.md> ...]
Exit:   0 all frontmatter valid · 1 one or more invalid · prints one line per
        offending file. Requires PyYAML for authoritative parsing; without it,
        falls back to a conservative structural + quote-balance heuristic and
        says so on stderr (never a false ERROR, only reduced coverage). The
        SKILL.md name checks are plain-regex and run identically either way.
"""

from __future__ import annotations

import os
import re
import sys

try:
    import yaml  # type: ignore
    _HAVE_YAML = True
except Exception:  # pragma: no cover - environment without PyYAML
    _HAVE_YAML = False

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_NAME_LINE_RE = re.compile(r"^name:\s*(.*)$")


def _extract(text: str) -> str | None:
    """Return the frontmatter body, or None if the file has no `---` block."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None  # opening fence but no closing fence
    return parts[1]


def _heuristic_error(body: str) -> str | None:
    """Dependency-free fallback: flag the common footguns only."""
    for i, raw in enumerate(body.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        _, _, value = line.partition(":")
        value = value.strip()
        # A scalar that opens with a quote must close with the matching quote
        # as its final character — otherwise there is trailing junk (the exact
        # `argument-hint: "x" [y]` bug).
        if value[:1] in ("'", '"'):
            q = value[0]
            if not (len(value) >= 2 and value[-1] == q and value.count(q) % 2 == 0):
                return f"line {i}: quoted value not closed cleanly — {line.strip()!r}"
    return None


def _frontmatter_name(body: str) -> str | None:
    """Best-effort `name:` value from a frontmatter body, without needing YAML."""
    for raw in body.splitlines():
        m = _NAME_LINE_RE.match(raw.strip())
        if m:
            value = m.group(1).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            return value
    return None


def _skill_name_error(path: str, body: str) -> str | None:
    """SKILL.md-only: name must be present, match its directory, and be a valid slug."""
    name = _frontmatter_name(body)
    if not name:
        return "SKILL.md frontmatter has no name field"
    dirname = os.path.basename(os.path.dirname(os.path.abspath(path)))
    if name != dirname:
        return f"SKILL.md name '{name}' does not match directory name '{dirname}'"
    if not (1 <= len(name) <= 64) or not _SLUG_RE.match(name):
        return (
            f"SKILL.md name '{name}' is not a valid skill name "
            "(lowercase alphanumerics and single hyphens, 1-64 chars)"
        )
    return None


def check(path: str) -> str | None:
    """Return an error string, or None if the frontmatter is valid/absent."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return f"unreadable: {exc}"
    is_skill = os.path.basename(path) == "SKILL.md"
    body = _extract(text)
    if body is None:
        if text.startswith("---"):
            return "frontmatter opened with '---' but never closed"
        if is_skill:
            return _skill_name_error(path, "")  # no frontmatter → undiscoverable
        return None  # no frontmatter block at all — not this check's concern
    if _HAVE_YAML:
        try:
            loaded = yaml.safe_load(body)
        except yaml.YAMLError as exc:
            return f"invalid YAML: {str(exc).splitlines()[0]}"
        if loaded is not None and not isinstance(loaded, dict):
            return "frontmatter is not a key/value mapping"
    else:
        err = _heuristic_error(body)
        if err:
            return err
    return _skill_name_error(path, body) if is_skill else None


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: lint-frontmatter.py <file.md> ...", file=sys.stderr)
        return 2
    if not _HAVE_YAML:
        print(
            "lint-frontmatter: PyYAML not available — using reduced heuristic "
            "checks (install pyyaml for full validation)",
            file=sys.stderr,
        )
    bad = 0
    for path in argv:
        err = check(path)
        if err:
            bad += 1
            print(f"{path}: {err}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
