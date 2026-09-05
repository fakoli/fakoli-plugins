#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyYAML>=6,<7"]
# ///
"""Validate Agent Skills against the deterministic rules of the spec.

The marketplace's `scripts/validate.sh` already parses each `SKILL.md`'s
frontmatter for YAML validity. This linter covers the *semantic* spec rules it
does not: the `name` charset/length/dir-match, the `description` length bound,
the SKILL.md body line ceiling, and skill placement as an immediate child of
`skills/`. Reference: agentskills.io/specification.

Uses PyYAML for authoritative YAML parsing. Run with uv run --script
so the dependency is isolated; a missing parser is an error, not a partial pass.

Usage:  skill_spec_lint.py [PATH ...]        (default: current directory)
  PATH may be a skill directory (contains SKILL.md), a plugin directory
  (contains skills/), or a repo root (scanned for plugins/*/skills/*/SKILL.md
  and skills/*/SKILL.md).
Exit:   0 no errors · 1 one or more ERROR findings. WARN never fails the run.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore

    _HAVE_YAML = True
except Exception:  # pragma: no cover - environment without PyYAML
    _HAVE_YAML = False

# name: 1-64 chars, lowercase alnum groups joined by single hyphens -- this one
# regex already forbids leading/trailing hyphens and consecutive hyphens.
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NAME_MAX = 64
_DESCRIPTION_MAX = 1024
_COMPATIBILITY_MAX = 500
_BODY_MAX_LINES = 500

_KNOWN_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
    "user-invocable",
    "disable-model-invocation",
    "context",
    "agent",
    "model",
    "argument-hint",
}


class Finding:
    __slots__ = ("path", "level", "message")

    def __init__(self, path: str, level: str, message: str):
        self.path = path
        self.level = level
        self.message = message

    def __str__(self) -> str:
        return "%s: %s: %s" % (self.path, self.level, self.message)


def split_frontmatter(text: str):
    """Return (frontmatter_str, body_str) or (None, whole) if no `--- ... ---`.

    The block must open on the first line -- a `---` further down is a Markdown
    horizontal rule, not frontmatter, and skills that lead with prose are
    exactly the "no discoverable frontmatter" case the spec rejects.
    """
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return None, text  # opened but never closed -> not valid frontmatter


def parse_frontmatter(front: str):
    """Return a fully parsed mapping or an actionable validation error."""
    if not _HAVE_YAML:
        return None, "PyYAML is required; run uv run --script skill_spec_lint.py PATH"
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("mapping keys must be unique strings")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        data = yaml.load(front, Loader=UniqueLoader)
    except (yaml.YAMLError, ValueError):
        return None, "frontmatter is not valid YAML (unique string keys required)"
    if not isinstance(data, dict):
        return None, "frontmatter must be a YAML mapping"
    return data, None


def validate_skill(skill_dir: Path) -> list:
    """Validate one skill directory (must contain SKILL.md). Returns findings."""
    findings = []
    md = skill_dir / "SKILL.md"
    rel = md.as_posix()
    if md.exists() and not md.is_file():
        return [Finding(md.as_posix(), "ERROR", "SKILL.md exists but is not a file")]
    if not md.is_file():
        return [Finding(skill_dir.as_posix(), "ERROR", "no SKILL.md in skill directory")]

    # utf-8-sig transparently drops a leading BOM (a common Windows-editor
    # artifact) so a BOM'd but otherwise valid file is not misread as
    # frontmatter-less.
    try:
        text = md.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return [Finding(rel, "ERROR", "SKILL.md is unreadable or not UTF-8")]
    front, body = split_frontmatter(text)
    if front is None:
        return [Finding(rel, "ERROR", "missing or unterminated `--- ... ---` frontmatter block")]

    mapping, err = parse_frontmatter(front)
    if err:
        return [Finding(rel, "ERROR", err)]

    # name -----------------------------------------------------------------
    name = mapping.get("name")
    if name is None or name == "":
        findings.append(Finding(rel, "ERROR", "frontmatter missing required `name`"))
    elif not isinstance(name, str):
        findings.append(Finding(rel, "ERROR", "name must be a string"))
    else:
        if len(name) > _NAME_MAX:
            findings.append(Finding(rel, "ERROR", "name is %d chars, exceeds %d" % (len(name), _NAME_MAX)))
        if not _NAME_RE.match(name):
            findings.append(
                Finding(
                    rel,
                    "ERROR",
                    "name %r must be lowercase alnum words joined by single hyphens "
                    "(no leading/trailing/consecutive hyphens)" % name,
                )
            )
        if name != skill_dir.name:
            findings.append(
                Finding(rel, "ERROR", "name %r must match its directory name %r" % (name, skill_dir.name))
            )

    # description ----------------------------------------------------------
    description = mapping.get("description")
    if description is None or description == "":
        findings.append(Finding(rel, "ERROR", "frontmatter missing required `description`"))
    elif not isinstance(description, str) or not description.strip():
        findings.append(Finding(rel, "ERROR", "description must be a nonempty string"))
    else:
        dlen = len(description)
        if dlen > _DESCRIPTION_MAX:
            findings.append(
                Finding(rel, "ERROR", "description is %d chars, exceeds %d" % (dlen, _DESCRIPTION_MAX))
            )

    # optional compatibility ----------------------------------------------
    compatibility = mapping.get("compatibility")
    if "compatibility" in mapping and (not isinstance(compatibility, str) or not compatibility.strip()):
        findings.append(Finding(rel, "ERROR", "compatibility must be a nonempty string"))
    elif compatibility is not None:
        clen = len(compatibility)
        if clen > _COMPATIBILITY_MAX:
            findings.append(
                Finding(rel, "ERROR", "compatibility is %d chars, exceeds %d" % (clen, _COMPATIBILITY_MAX))
            )

    metadata = mapping.get("metadata", {})
    if not isinstance(metadata, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()):
        findings.append(Finding(rel, "ERROR", "metadata must map strings to strings"))
    for key in ("license", "allowed-tools"):
        if key in mapping and not isinstance(mapping[key], str):
            findings.append(Finding(rel, "ERROR", f"{key} must be a string"))
    for key in ("user-invocable", "disable-model-invocation"):
        if key in mapping and not isinstance(mapping[key], bool):
            findings.append(Finding(rel, "ERROR", f"{key} must be boolean"))

    # unknown keys (WARN — the spec allows a fixed optional set) ------------
    for key in mapping:
        if key not in _KNOWN_KEYS:
            findings.append(
                Finding(rel, "WARN", "unknown frontmatter key %r (not in the spec's optional set)" % key)
            )

    # body line ceiling ----------------------------------------------------
    body_lines = len(body.splitlines())
    if body_lines > _BODY_MAX_LINES:
        findings.append(
            Finding(
                rel,
                "WARN",
                "SKILL.md body is %d lines, exceeds %d — move detail to references/"
                % (body_lines, _BODY_MAX_LINES),
            )
        )

    return findings


def discover(path: Path) -> tuple:
    """Return (skill_dirs, findings). Finds skill candidates and flags misplaced ones.

    A *candidate* is any immediate child directory of a `skills/` dir, whether or
    not it holds a valid SKILL.md — an empty or SKILL.md-less skill dir is a
    defect to report, not a skill to skip silently. `os.walk(followlinks=False)`
    is used (not `Path.rglob`) so a symlink loop cannot hang the scan on any
    Python version.
    """
    findings = []
    if (path / "SKILL.md").exists() or path.parent.name == "skills":
        return [path], findings

    candidates = []  # ordered, deduped by resolved path
    seen = set()
    md_files = []
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        base = os.path.basename(dirpath)
        if base == "skills":
            for child in sorted(dirnames):
                cd = Path(dirpath) / child
                key = cd.resolve()
                if key not in seen:
                    seen.add(key)
                    candidates.append(cd)
        if "SKILL.md" in filenames:
            md_files.append(Path(dirpath) / "SKILL.md")

    discoverable = {c.resolve() for c in candidates}
    for md in md_files:
        if md.parent.resolve() in discoverable:
            continue  # the normal skills/<name>/SKILL.md case
        if "skills" in md.parts:
            findings.append(
                Finding(
                    md.as_posix(),
                    "WARN",
                    "SKILL.md is not an immediate child of skills/ — it will not be discovered",
                )
            )

    return candidates, findings


def lint(paths) -> tuple:
    """Return (findings, skill_count) across every PATH."""
    all_findings = []
    count = 0
    seen = set()
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            all_findings.append(Finding(str(raw), "ERROR", "path does not exist"))
            continue
        if p.is_file():
            if p.name != "SKILL.md":
                all_findings.append(Finding(str(raw), "ERROR", "expected SKILL.md or a directory"))
                continue
            p = p.parent
        skill_dirs, disc_findings = discover(p)
        all_findings.extend(disc_findings)
        for skill_dir in skill_dirs:
            if skill_dir.resolve() in seen:
                continue
            seen.add(skill_dir.resolve())
            count += 1
            all_findings.extend(validate_skill(skill_dir))
    return all_findings, count


def main(argv) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=["."])
    paths = parser.parse_args(argv).paths or ["."]
    if not _HAVE_YAML:
        print("skill-spec-lint: PyYAML is required; run uv run --script with this script", file=sys.stderr)
        return 2
    findings, count = lint(paths)
    errors = [f for f in findings if f.level == "ERROR"]
    warns = [f for f in findings if f.level == "WARN"]
    for f in findings:
        print(f)
    print(
        "skill-spec-lint: %d skill(s), %d error(s), %d warning(s)"
        % (count, len(errors), len(warns))
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
