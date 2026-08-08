#!/usr/bin/env python3
"""roster-audit.py - measure the fixed per-session context cost of a Claude Code roster.

Every installed skill, plugin command, and plugin agent is listed in the system
prompt of EVERY session, whether or not it is ever used. That listing is a fixed
tax paid before any work happens. This script enumerates the roster, joins it
against real usage, scans for cross-references, and nominates never-used units
as prune CANDIDATES.

The unit of pruning is a PLUGIN or a standalone global skill -- not an
individual entry. You cannot disable one skill of a plugin; `enabledPlugins`
toggles the whole plugin. So entries are grouped into units, and a dependency
edge only counts when it crosses a unit boundary (sibling skills inside one
plugin cite each other constantly and that says nothing about prunability).

It nominates only. It never says ARCHIVE and never moves a file: usage is not
value (a disaster-recovery skill used never is priceless), so the bucket
decision stays human. A wrong prune breaks a session; a kept dud costs ~40
tokens -- when the signal is ambiguous the unit is KEPT.

Usage:
    python scripts/roster-audit.py --roster-root ~/.claude
    python scripts/roster-audit.py --roster-root ~/.claude \\
        --usage session-report.json --project ~/code/my-repo --json

The --usage file is the JSON emitted by the `session-report` skill's bundled
analyzer (`node analyze-sessions.mjs --json`). Without it every unit reads as
unused, so the report is inventory-and-dependencies only.

Stdlib only. Runs the same on Windows and Linux.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

# A bare name shorter than this produces false-positive dependency edges when
# searched as a word ("pdf", "run", "note" appear in ordinary prose).
MIN_BARE_NAME_LEN = 6

# Characters per token. A documented estimate, not a measurement -- the real
# figure depends on the tokenizer. Used only for relative before/after deltas.
CHARS_PER_TOKEN = 4


class Entry:
    """One roster listing: a skill, a plugin command, or a plugin agent."""

    def __init__(self, ident, kind, unit, source, path, description, mtime, enabled):
        self.id = ident
        self.kind = kind
        self.unit = unit
        self.source = source
        self.path = path
        self.description = description
        self.mtime = mtime
        self.enabled = enabled
        self.body = ""

    @property
    def bare(self):
        """The id without its `plugin:` namespace."""
        return self.id.split(":", 1)[-1]

    def age_days(self, today):
        return (today - self.mtime).days

    def cost_tokens(self):
        return math.ceil((len(self.id) + len(self.description)) / CHARS_PER_TOKEN)


class Unit:
    """A prune unit: one plugin, one standalone global skill, or one project."""

    def __init__(self, name, scope):
        self.name = name
        self.scope = scope  # plugin | global | project
        self.entries = []
        self.enabled = True
        self.referenced_by = []
        self.weak_referenced_by = []
        self.uses = 0
        self.bucket = ""
        self.reason = ""

    def cost_tokens(self):
        return sum(e.cost_tokens() for e in self.entries)

    def age_days(self, today):
        """Age of the most recently touched entry -- a unit is as new as its newest part."""
        return min(e.age_days(today) for e in self.entries)

    def as_dict(self, today):
        return {
            "unit": self.name,
            "scope": self.scope,
            "enabled": self.enabled,
            "entries": [e.id for e in self.entries],
            "entry_count": len(self.entries),
            "age_days": self.age_days(today),
            "cost_tokens_est": self.cost_tokens(),
            "uses": self.uses,
            "referenced_by": sorted(self.referenced_by),
            "weak_referenced_by": sorted(self.weak_referenced_by),
            "bucket": self.bucket,
            "reason": self.reason,
        }


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_frontmatter(text, path=None):
    """Return (fields, body). Handles quoted, unquoted, and folded descriptions."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    # The closing fence is a line that is exactly `---`. Searching for the
    # substring "\n---" instead truncates any folded description whose
    # continuation line happens to start with three hyphens.
    close = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if close is None:
        if path:
            print(f"warning: {path} has an unclosed frontmatter fence; "
                  "description unreadable", file=sys.stderr)
        return {}, text
    raw_lines, body = lines[1:close], "\n".join(lines[close + 1 :])
    fields, key = {}, None
    for line in raw_lines:
        match = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            # A folded/literal block (`description: >-`) carries its text on the
            # following indented lines, not on the key line.
            fields[key] = "" if value in (">", ">-", "|", "|-") else value
        elif key and line.startswith((" ", "\t")):
            fields[key] = (fields[key] + " " + line.strip()).strip()
        elif line.strip():
            key = None
    for key, value in fields.items():
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            unquoted = value[1:-1]
            # YAML escapes a single quote inside a single-quoted scalar by
            # doubling it.
            fields[key] = unquoted.replace("''", "'") if value[0] == "'" else unquoted
    return fields, body


def load_entry(path, namespace, kind, unit, source, enabled):
    """Build an Entry from a SKILL.md / command .md / agent .md file.

    The session addresses a skill by its DIRECTORY name, not by frontmatter
    `name:` -- systems-thinking's skills carry display titles there while the
    real id is the slug. Directory name wins.
    """
    text = read_text(path)
    fields, body = parse_frontmatter(text, path)
    name = path.parent.name if path.name == "SKILL.md" else path.stem
    ident = f"{namespace}:{name}" if namespace else name
    entry = Entry(
        ident,
        kind,
        unit,
        source,
        path,
        " ".join((fields.get("description") or "").split()),
        dt.date.fromtimestamp(path.stat().st_mtime),
        enabled,
    )
    entry.body = body
    for ref in sorted(path.parent.glob("references/*.md")):
        entry.body += "\n" + read_text(ref)
    return entry


def version_key(name):
    """Sort version directory names numerically, not lexicographically.

    String sorting puts '1.9.0' after '1.10.0', so the fallback would audit a
    stale version's skills and descriptions. Non-numeric segments (e.g.
    'unknown') sort below any numbered release.
    """
    parts = []
    for chunk in re.split(r"[._-]", name):
        parts.append((1, int(chunk), "") if chunk.isdigit() else (0, 0, chunk))
    return parts


def plugin_version_dir(plugin_dir, pinned):
    """Pick the installed version directory; fall back to the highest version."""
    versions = sorted((d for d in plugin_dir.iterdir() if d.is_dir()),
                      key=lambda d: version_key(d.name))
    if not versions:
        return None
    if pinned:
        for candidate in versions:
            if candidate.name == pinned:
                return candidate
    return versions[-1]


def load_json(path):
    if not path.is_file():
        return {}
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        print(f"warning: {path} is not valid JSON; ignored", file=sys.stderr)
        return {}


def collect_plugin_entries(root, entries):
    """Walk plugins/cache/<marketplace>/<plugin>/<version>/."""
    cache = root / "plugins" / "cache"
    if not cache.is_dir():
        return

    # If settings.json is missing or unreadable we cannot tell enabled from
    # disabled. Assume enabled: a unit wrongly marked "not loaded" silently
    # drops out of the cost totals and can never be nominated, which is a
    # worse failure than overstating the tax.
    settings = root / "settings.json"
    enabled_map = None
    if settings.is_file():
        parsed = load_json(settings)
        if isinstance(parsed.get("enabledPlugins"), dict):
            enabled_map = parsed["enabledPlugins"]
        else:
            print(f"warning: {settings} has no readable enabledPlugins; "
                  "treating every installed plugin as loaded", file=sys.stderr)
    # installed_plugins.json carries both the pinned version and the real
    # install/update dates. File mtimes here are a shared re-materialisation
    # stamp -- sixteen unrelated plugins read the same age -- so they must not
    # feed the --new-days guard any more than the desktop root's do.
    pinned, updated = {}, {}
    for key, records in (load_json(root / "plugins" / "installed_plugins.json")
                         .get("plugins") or {}).items():
        if not records:
            continue
        pinned[key] = records[0].get("version")
        # installedAt, not lastUpdated. The --new-days guard exists to protect
        # units too recently adopted to have a usage window; lastUpdated is a
        # bulk cache refresh (sixteen unrelated plugins share one date here)
        # and would reset that window for plugins the operator has had for
        # months.
        stamp = records[0].get("installedAt") or records[0].get("lastUpdated")
        if isinstance(stamp, str):
            try:
                updated[key] = dt.date.fromisoformat(stamp[:10])
            except ValueError:
                pass

    for marketplace in sorted(d for d in cache.iterdir() if d.is_dir()):
        for plugin in sorted(d for d in marketplace.iterdir() if d.is_dir()):
            key = f"{plugin.name}@{marketplace.name}"
            version = plugin_version_dir(plugin, pinned.get(key))
            if version is None:
                continue
            source = f"{marketplace.name}/{plugin.name}"
            enabled = True if enabled_map is None else bool(enabled_map.get(key, False))
            found = []
            for skill in sorted(version.glob("skills/*/SKILL.md")):
                found.append(load_entry(skill, plugin.name, "skill", key, source, enabled))
            for kind, sub in (("command", "commands"), ("agent", "agents")):
                for path in sorted(version.glob(f"{sub}/*.md")):
                    found.append(load_entry(path, plugin.name, kind, key, source, enabled))
            for entry in found:
                entry.mtime = updated.get(key, entry.mtime)
            entries.extend(found)


def collect_extra_plugin_root(base, entries):
    """Walk a directory whose immediate children are plugin roots.

    The CLI installs plugins under `plugins/cache/<marketplace>/<plugin>/<ver>/`,
    but that is not the only mechanism: the desktop app materialises its own set
    under a session-scoped runtime directory, one plugin root per child dir with
    a `plugin.json` naming it. Auditing only the CLI cache measures half the
    roster. This option covers any such layout without hardcoding a path.
    """
    if not base.is_dir():
        print(f"warning: plugin root not found: {base}", file=sys.stderr)
        return

    # File mtimes here are the moment the app last materialised the plugin, not
    # the plugin's age -- without this every such unit looks brand new and the
    # --new-days guard protects the whole root. The manifest carries the real
    # update date.
    updated = {}
    for record in (load_json(base / "manifest.json").get("plugins") or []):
        stamp, name = record.get("updatedAt"), record.get("name")
        if not (stamp and name):
            continue
        try:
            updated[name] = dt.date.fromisoformat(stamp[:10])
        except ValueError:
            pass

    for plugin in sorted(d for d in base.iterdir() if d.is_dir()):
        manifest = plugin / "plugin.json"
        if not manifest.is_file():
            manifest = plugin / ".claude-plugin" / "plugin.json"
        name = load_json(manifest).get("name") or plugin.name
        unit = f"{name}@{base.name}"
        source = f"{base.name}/{name}"
        found = []
        for skill in sorted(plugin.glob("skills/*/SKILL.md")):
            found.append(load_entry(skill, name, "skill", unit, source, True))
        for kind, sub in (("command", "commands"), ("agent", "agents")):
            for path in sorted(plugin.glob(f"{sub}/*.md")):
                found.append(load_entry(path, name, kind, unit, source, True))
        for entry in found:
            entry.mtime = updated.get(name, entry.mtime)
        entries.extend(found)


def collect_roster(root, projects, plugin_roots=()):
    entries = []
    for skill in sorted(root.glob("skills/*/SKILL.md")):
        name = skill.parent.name
        entries.append(load_entry(skill, "", "skill", name, "global-user", True))
    for path in sorted(root.glob("commands/*.md")):
        entries.append(load_entry(path, "", "command", path.stem, "global-user", True))
    collect_plugin_entries(root, entries)
    for base in plugin_roots:
        collect_extra_plugin_root(base, entries)
    # Project-scoped entries are inventoried so a dependency edge into them is
    # visible, but they belong to their own repo and are never prune candidates.
    for project in projects:
        unit = f"project:{project.name}"
        for skill in sorted(project.glob(".claude/skills/*/SKILL.md")):
            entries.append(load_entry(skill, "", "skill", unit, unit, True))
        for kind, sub in (("command", "commands"), ("agent", "agents")):
            for path in sorted(project.glob(f".claude/{sub}/*.md")):
                entries.append(load_entry(path, "", kind, unit, unit, True))
    return entries


def build_units(entries):
    units = {}
    for entry in entries:
        unit = units.get(entry.unit)
        if unit is None:
            if entry.unit.startswith("project:"):
                scope = "project"
            elif "@" in entry.unit:
                scope = "plugin"
            else:
                scope = "global"
            unit = units[entry.unit] = Unit(entry.unit, scope)
        unit.entries.append(entry)
        unit.enabled = unit.enabled and entry.enabled
    return list(units.values())


FENCED_BLOCK = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def strip_code_blocks(text):
    """Drop fenced code blocks before reference scanning.

    Sample transcripts and CLI examples routinely print unit names; treating
    those as citations invents dependency edges that make a unit unprunable.
    """
    return FENCED_BLOCK.sub("", text)


def reference_patterns(entry, strict=True):
    """Regex forms that count as one unit pointing at this entry.

    Strict mode drives classification. A bare name is trusted there only when
    it is slug-shaped (hyphenated): units named for a common word -- `update`,
    `analyze`, `runbook` -- otherwise match ordinary prose in dozens of
    unrelated bodies, and every false edge makes a never-used suite
    permanently unprunable.

    That strictness has a cost in the dangerous direction: a real dependency on
    an unhyphenated name (`cloudflare`, `review`) written as plain prose is
    missed. Loose mode drops the slug requirement and feeds
    `weak_referenced_by`, which is reported but never classifies -- so a human
    sees the possible edge before approving an archive.
    """
    ident = re.escape(entry.id)
    # A slash form must open a token: `[docs](/name)` is a link, not a command.
    patterns = [r"(?:(?<=\s)|\A)/" + ident + r"(?![\w-])", "`" + ident + "`"]
    if ":" in entry.id:
        patterns.append(r"(?<![\w:./-])" + ident + r"(?![\w-])")
    if len(entry.bare) >= MIN_BARE_NAME_LEN and ("-" in entry.bare or not strict):
        patterns.append(r"(?<![\w:./-])" + re.escape(entry.bare) + r"(?![\w-])")
    return patterns


def scan_dependencies(units):
    """Fill referenced_by with CROSS-UNIT edges only.

    An archived unit that a kept unit still points at is a broken session, so a
    non-empty referenced_by is a hard KEEP in classify(). Intra-unit references
    are excluded: you archive a whole plugin, so its skills citing each other
    proves nothing.
    """
    bodies = {unit.name: [strip_code_blocks(e.body) for e in unit.entries] for unit in units}

    for target in units:
        strict = re.compile("|".join(
            p for e in target.entries for p in reference_patterns(e, strict=True)))
        loose = re.compile("|".join(
            p for e in target.entries for p in reference_patterns(e, strict=False)))
        target_plugin = target.name.split("@")[0]
        for other in units:
            # Same unit, or the same plugin installed under a second root: a
            # copy of a plugin citing itself is not a dependency on it.
            if other.name.split("@")[0] == target_plugin:
                continue
            texts = bodies[other.name]
            if any(strict.search(text) for text in texts):
                target.referenced_by.append(other.name)
            elif any(loose.search(text) for text in texts):
                target.weak_referenced_by.append(other.name)


def join_usage(units, usage_path):
    """Attach invocation counts from a session-report analyzer JSON."""
    if not usage_path:
        return
    data = load_json(usage_path)
    if not isinstance(data, dict):
        print(f"warning: {usage_path} is not a session-report object; usage ignored",
              file=sys.stderr)
        return

    counts = {}

    def add(key, value):
        if not isinstance(key, str):
            return
        try:
            counts[key] = counts.get(key, 0) + int(value or 0)
        except (TypeError, ValueError):
            pass

    def add_calls(section):
        if not isinstance(section, dict):
            return
        for key, value in section.items():
            add(key, value.get("api_calls") if isinstance(value, dict) else value)

    add_calls(data.get("by_skill"))
    add_calls(data.get("by_subagent_type"))
    overall = data.get("overall")
    if isinstance(overall, dict) and isinstance(overall.get("skill_invocations"), dict):
        for key, value in overall["skill_invocations"].items():
            add(key, value)

    # A usage key that exactly matches some unit's entry id belongs to that
    # unit alone. Without this, a key like "review" is credited to the global
    # `review` skill AND to every plugin owning a `plugin:review` entry, so a
    # dead plugin sharing a bare name with a live skill can never be nominated.
    claimed = {entry.id for unit in units for entry in unit.entries if entry.id in counts}

    for unit in units:
        # Transcripts record both the namespaced and the bare form of the same
        # skill, so both are counted -- but per UNIT, not per entry. A plugin
        # may hold a skill and a command of the same name (identical ids), and
        # a global skill has id == bare; summing per entry double-counts both.
        keys = set()
        for entry in unit.entries:
            keys.add(entry.id)
            if entry.bare not in claimed:
                keys.add(entry.bare)
        unit.uses = sum(counts.get(key, 0) for key in keys)


def classify(unit, today, new_days, protected):
    """The one decision in this script. Mutation-check target.

    Rules apply in order, first match wins. Every rule but the last resolves to
    KEEP, because ambiguity must cost tokens rather than break a session.
    """
    if unit.scope == "project":
        return "KEEP", "project-scoped (out of scope)"
    if not unit.enabled:
        return "KEEP", "not loaded (costs nothing)"
    if unit.name in protected or unit.name.split("@")[0] in protected:
        return "KEEP", "protected"
    if unit.uses > 0:
        return "KEEP", f"used ({unit.uses})"
    if unit.referenced_by:
        return "KEEP", f"dependency of {len(unit.referenced_by)}"
    if unit.age_days(today) < new_days:
        return "KEEP", f"new ({unit.age_days(today)}d)"
    return "CANDIDATE", "no recorded use"


def totals_by_scope(units):
    totals = {"units": len(units), "entries": 0, "cost_tokens": 0, "by_scope": {}}
    for unit in units:
        cost = unit.cost_tokens()
        totals["entries"] += len(unit.entries)
        totals["cost_tokens"] += cost
        count, entries, running = totals["by_scope"].get(unit.scope, (0, 0, 0))
        totals["by_scope"][unit.scope] = (count + 1, entries + len(unit.entries), running + cost)

    # A plugin installed under two roots is listed once in a session, so summing
    # both copies overstates the tax. Deduplicate by plugin name, keeping the
    # dearer copy. Disabled and project-scoped units are excluded: a disabled
    # unit is not listed in any prompt, so charging for it would make the
    # before/after delta of disabling something come out as zero.
    seen = {}
    for unit in units:
        if not unit.enabled or unit.scope == "project":
            continue
        name = unit.name.split("@")[0]
        seen[name] = max(seen.get(name, 0), unit.cost_tokens())
    totals["loaded_units"] = len(seen)
    totals["loaded_cost_tokens"] = sum(seen.values())
    return totals


def render(units, today, totals):
    lines = ["# Roster audit", ""]
    lines.append(f"Generated for {today.isoformat()}. Cost estimate: "
                 f"ceil((len(id) + len(description)) / {CHARS_PER_TOKEN}) tokens per entry.")
    lines.append("")
    lines.append("| unit | scope | enabled | entries | age (d) | est. tokens | uses | referenced by | bucket | reason |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for unit in sorted(units, key=lambda u: (u.scope, u.name)):
        refs = ", ".join(sorted(unit.referenced_by)) or "-"
        lines.append(
            f"| `{unit.name}` | {unit.scope} | {'yes' if unit.enabled else 'no'} | "
            f"{len(unit.entries)} | {unit.age_days(today)} | {unit.cost_tokens()} | "
            f"{unit.uses} | {refs} | {unit.bucket} | {unit.reason} |"
        )
    lines += ["", "## Fixed cost", ""]
    lines.append("| scope | units | entries | est. tokens |")
    lines.append("|---|---|---|---|")
    for scope in sorted(totals["by_scope"]):
        count, entries, cost = totals["by_scope"][scope]
        lines.append(f"| {scope} | {count} | {entries} | {cost} |")
    lines.append(f"| **total** | **{totals['units']}** | **{totals['entries']}** "
                 f"| **{totals['cost_tokens']}** |")
    lines.append("")
    lines.append(f"**Loaded cost: {totals['loaded_units']} units, "
                 f"{totals['loaded_cost_tokens']} est. tokens.** This is the figure a "
                 "prune moves. It counts only enabled, non-project units and "
                 "deduplicates by plugin name, since a plugin installed under two "
                 "roots is listed once per session and a disabled one is not listed "
                 "at all. The totals above are the full inventory, including units "
                 "that cost nothing today.")
    lines += ["", "## Candidates", ""]
    candidates = [u for u in units if u.bucket == "CANDIDATE"]
    if not candidates:
        lines.append("None. Every loaded unit is used, referenced, new, or protected.")
    else:
        lines.append(f"{len(candidates)} nominated, "
                     f"{sum(u.cost_tokens() for u in candidates)} est. tokens. "
                     "Nomination is not a verdict -- a human assigns the bucket.")
        lines.append("")
        for unit in sorted(candidates, key=lambda u: -u.cost_tokens()):
            weak = ", ".join(sorted(unit.weak_referenced_by))
            note = f" — possibly cited by {weak}" if weak else ""
            lines.append(f"- `{unit.name}` ({len(unit.entries)} entries, "
                         f"{unit.cost_tokens()} tok){note}")
        if any(u.weak_referenced_by for u in candidates):
            lines.append("")
            lines.append("\"Possibly cited by\" is a loose prose match on an unhyphenated "
                         "name. It does not classify — check it before archiving.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--roster-root", required=True, type=Path,
                        help="Claude config root, normally ~/.claude")
    parser.add_argument("--usage", type=Path,
                        help="session-report analyzer JSON (node analyze-sessions.mjs --json)")
    parser.add_argument("--project", type=Path, action="append", default=[],
                        help="repo whose .claude/ entries are inventoried (repeatable)")
    parser.add_argument("--plugin-root", type=Path, action="append", default=[],
                        help="directory whose immediate children are plugin roots, "
                             "e.g. the desktop app's runtime plugin dir (repeatable)")
    parser.add_argument("--protect", action="append", default=[],
                        help="unit name that is never a candidate (repeatable)")
    parser.add_argument("--new-days", type=int, default=30,
                        help="units younger than this are always kept (default 30)")
    parser.add_argument("--today", help="override today's date as YYYY-MM-DD (for tests)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = parser.parse_args(argv)

    root = args.roster_root.expanduser()
    if not root.is_dir():
        parser.error(f"roster root not found: {root}")
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    entries = collect_roster(
        root,
        [p.expanduser() for p in args.project],
        [p.expanduser() for p in args.plugin_root],
    )
    if not entries:
        parser.error(f"no roster entries found under {root}")
    units = build_units(entries)
    scan_dependencies(units)
    join_usage(units, args.usage.expanduser() if args.usage else None)

    protected = set(args.protect)
    for unit in units:
        unit.bucket, unit.reason = classify(unit, today, args.new_days, protected)

    totals = totals_by_scope(units)
    if args.json:
        print(json.dumps({
            "generated_for": today.isoformat(),
            "totals": {
                "units": totals["units"],
                "entries": totals["entries"],
                "cost_tokens": totals["cost_tokens"],
                "loaded_units": totals["loaded_units"],
                "loaded_cost_tokens": totals["loaded_cost_tokens"],
                "by_scope": {k: {"units": v[0], "entries": v[1], "cost_tokens": v[2]}
                             for k, v in totals["by_scope"].items()},
            },
            "units": [u.as_dict(today) for u in units],
        }, indent=2))
    else:
        print(render(units, today, totals), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
