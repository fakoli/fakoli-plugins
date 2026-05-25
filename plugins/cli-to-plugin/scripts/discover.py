#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
discover.py — Walk <cli> --help recursively and emit a canonical JSON help tree to stdout.

Invocation:
    uv run --script discover.py <cli-name> [options]

Output conforms to plugins/cli-to-plugin/schemas/help-tree.schema.json.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# ANSI stripping
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Subprocess invocation
# ---------------------------------------------------------------------------

def run_help(args: list[str], per_call_timeout: float) -> tuple[str, int, bool]:
    """
    Run a CLI help invocation and return (stdout_text, returncode, timed_out).

    Forces LANG/LC_ALL=C.UTF-8. Decodes stdout as UTF-8 with errors="replace".
    """
    env = {**os.environ, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    try:
        result = subprocess.run(
            args,
            env=env,
            capture_output=True,
            timeout=per_call_timeout,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        # Many CLIs write help to stderr when invoked with a bad sub-command.
        # Prefer stdout if it has content; fall back to stderr.
        if not stdout.strip() and stderr.strip():
            stdout = stderr
        return stdout, result.returncode, False
    except subprocess.TimeoutExpired:
        return "", -1, True


# ---------------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------------

# Flag parsing strategy (MUST FIX 6):
#
# CLI help text uses 2+ spaces to separate the argument token from the
# description. The format is:
#   <indent><short>, <long>  [<argument>]  <description>
#
# After extracting the flag names, we split the remaining text on the first
# occurrence of 2+ consecutive spaces. The left part (before the separator)
# is the argument token; the right part is the description.
#
# If there is no 2+ space separator, the whole trailing text is treated as
# the description (the flag takes no argument, like --draft or --verbose).
#
# The argument token is validated against known CLI argument forms:
#   - <angle-bracket>: <name>, <repo>
#   - ALL-CAPS (>= 2 chars): STRING, OWNER/REPO, [HOST/]OWNER/REPO
#     The compound form [HOST/]OWNER/REPO starts with [ and contains
#     uppercase segments — handled by a specific bracket-prefix pattern.
#   - Known lowercase type names: string, int, float, bool, list, strings, etc.
#
# This regex extracts: short, long, and the "remainder" text after the flag.
_FLAG_RE = re.compile(
    r"^\s+"
    r"(?:(-[a-zA-Z])(?:,\s*))?"          # optional short flag
    r"(--[a-zA-Z][a-zA-Z0-9-]*)?"        # optional long flag
    r"\s*(.*?)\s*$"                       # everything after flags (stripped)
)

# Simpler check: does this look like a flag line?
_FLAG_START_RE = re.compile(r"^\s+(-[a-zA-Z]|--[a-zA-Z])")

# Pattern for a valid argument placeholder token.
# Matches (anchored to full token):
#   - <angle-bracket>: <name>, <number>
#   - ALL-CAPS word (>= 2 uppercase chars), e.g. STRING, OWNER
#   - ALL-CAPS compound with / : - e.g. OWNER/REPO, TYPE[.VERSION][.GROUP]
#   - [OPTIONAL]REQUIRED compound form: [HOST/]OWNER/REPO
#   - Known lowercase type names (exact match): string, int, float, bool, etc.
_ARG_PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"<[^>]+>"                                           # <angle-bracket>
    r"|\[[A-Z][A-Z0-9_/:\[\]-]*\][A-Z][A-Z0-9_/:\[\]-]+"  # [OPTIONAL]REQUIRED
    r"|[A-Z][A-Z0-9_/:\[\]-]+"                          # ALL-CAPS >= 2 chars
    r"|string|int|float|bool|list|strings|key=value"
    r"|expression|fields|branch|login|name|number|path|format"
    r")$"
)


def parse_flag_line(line: str) -> Optional[dict]:
    """
    Parse a single flag line.

    Returns a flag dict with at least one of 'short' or 'long', or None if
    the line does not look like a flag.
    """
    if not _FLAG_START_RE.match(line):
        return None

    m = _FLAG_RE.match(line)
    if not m:
        return None

    short, long_, remainder = m.groups()

    flag: dict = {}
    if short:
        flag["short"] = short
    if long_:
        flag["long"] = long_

    if not flag:
        return None

    if not remainder:
        return flag

    # Split on first occurrence of 2+ spaces to separate argument from
    # description. This is the most reliable separator used by CLIs.
    two_space_split = re.split(r"\s{2,}", remainder, maxsplit=1)

    if len(two_space_split) == 2:
        # We have a separator. The left part should be the argument token.
        candidate_arg, description = two_space_split[0].strip(), two_space_split[1].strip()
        # Validate that the left part is actually an argument placeholder.
        # If not, treat the whole remainder as description.
        if candidate_arg and _ARG_PLACEHOLDER_RE.match(candidate_arg):
            flag["argument"] = candidate_arg
            if description:
                flag["description"] = description
        else:
            # Left part is not an argument — whole remainder is description
            full_desc = remainder.strip()
            if full_desc:
                flag["description"] = full_desc
    else:
        # No 2+ space separator. Single-word remainder might be argument;
        # multi-word remainder is description.
        remainder = remainder.strip()
        if not remainder:
            return flag
        # If there are no spaces: single token — check if it's an argument
        if " " not in remainder:
            if _ARG_PLACEHOLDER_RE.match(remainder):
                flag["argument"] = remainder
            else:
                flag["description"] = remainder
        else:
            # Multiple words, no double-space separator: treat as description
            flag["description"] = remainder

    return flag


# ---------------------------------------------------------------------------
# Command-line parsing within a section
# ---------------------------------------------------------------------------

# gh format:  "  pr:            Manage pull requests"
# kubectl:    "  get            Display one or many resources"
# docker:     "  build       Build an image from a Dockerfile"
_CMD_RE = re.compile(
    r"^\s{1,8}"               # 1–8 leading spaces (not too deeply indented)
    r"([a-zA-Z][a-zA-Z0-9_-]*)"  # command name
    r":?"                      # optional colon (gh style)
    r"[ \t]+"                  # separator
    r"(.*?)$"                  # description
)


def parse_command_line(line: str) -> Optional[tuple[str, str]]:
    """
    Parse a command-listing line.

    Returns (name, summary) or None if the line does not look like a command.
    The name has underscores replaced with hyphens per schema convention.
    """
    m = _CMD_RE.match(line)
    if not m:
        return None
    name_raw, summary = m.group(1), m.group(2).strip()
    name = name_raw.replace("_", "-")
    return name, summary


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

# MUST FIX 2: Section headings now match:
#   1. ALL-CAPS headings (gh style): "CORE COMMANDS", "FLAGS"
#   2. Mixed-case headings ending with colon (kubectl, docker style):
#      "Basic Commands (Beginner):", "Available Commands:", "Commands:"
#   3. Title-case section names with optional colon
#
# The pattern captures the heading text (without trailing colon).
_SECTION_RE = re.compile(
    r"^([A-Z][A-Za-z0-9 _/()\-]+?)\s*:?\s*$"
)

# Non-command sections that must NOT be treated as command listings
# even if they match suffix heuristics.
_NON_COMMAND_SECTIONS = {
    "USAGE", "EXAMPLES", "LEARN MORE", "HELP TOPICS",
    "ARGUMENTS", "SEE ALSO", "OPTIONS", "NOTES", "DESCRIPTION",
}

# Sections that contain sub-commands (by suffix or exact name)
_COMMAND_SECTION_KEYWORDS = {
    "COMMANDS", "SUBCOMMANDS", "AVAILABLE COMMANDS", "MANAGEMENT COMMANDS",
    "MANAGEMENT", "OPERATIONS",
}


def _is_command_section(heading: str) -> bool:
    """Return True if this section heading suggests it lists commands."""
    upper = heading.upper().rstrip(":").strip()
    # Explicit exclusions first
    if upper in _NON_COMMAND_SECTIONS:
        return False
    # Ends with COMMANDS or SUBCOMMANDS (e.g. "GITHUB ACTIONS COMMANDS",
    # "Basic Commands (Beginner)", "Available Commands", "Management Commands")
    # Strip parenthetical qualifiers before checking suffix
    core = re.sub(r"\s*\([^)]*\)\s*$", "", upper).strip()
    if core.endswith("COMMANDS") or core.endswith("SUBCOMMANDS"):
        return True
    if upper.endswith("COMMANDS") or upper.endswith("SUBCOMMANDS"):
        return True
    # Exact matches
    return upper in _COMMAND_SECTION_KEYWORDS


def _is_flag_section(heading: str) -> bool:
    """Return True if this section heading suggests it lists flags."""
    upper = heading.upper().rstrip(":").strip()
    return upper in {
        "FLAGS", "OPTIONS", "GLOBAL FLAGS", "GLOBAL OPTIONS",
        "INHERITED FLAGS", "INHERITED OPTIONS",
        "OPTIONAL FLAGS", "REQUIRED FLAGS",
        "GLOBAL OPTIONS",
    }


# ---------------------------------------------------------------------------
# Help-text structured parser
# ---------------------------------------------------------------------------

def parse_help_text(text: str) -> dict:
    """
    Parse raw help text into a structured dict with keys:
      summary, usage, sections: [{heading, kind, entries}]

    kind is one of "commands", "flags", "other".
    entries for commands: list of {name, summary}
    entries for flags:    list of flag dicts
    """
    lines = text.splitlines()
    result: dict = {
        "summary": "",
        "usage": "",
        "sections": [],
    }

    # The very first non-empty line that does not look like a section heading
    # and is not a USAGE line is treated as the CLI summary.
    summary_found = False
    i = 0
    n = len(lines)

    # --- Pass 1: extract summary from leading description lines ---
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            if summary_found:
                break  # blank line after summary text ends it
            continue
        # Skip comment lines (used in pathological test fixtures)
        if stripped.startswith("#"):
            i += 1
            continue
        if _SECTION_RE.match(stripped) or stripped.upper().startswith("USAGE"):
            break
        if not summary_found:
            result["summary"] = stripped
            summary_found = True
        # Continuation lines of a multi-line summary
        i += 1

    # --- Pass 2: scan sections ---
    current_section: Optional[dict] = None

    while i < n:
        line = lines[i]
        stripped = line.strip()
        i += 1

        if not stripped:
            continue

        # Skip comment lines (used in pathological test fixtures)
        if stripped.startswith("#"):
            continue

        # USAGE line — handle both "USAGE" (gh style) and "Usage:" (kubectl style)
        # SHOULD FIX D: Some CLIs put usage inline: "Usage:  docker [OPTIONS] COMMAND"
        # followed by a blank line and then the summary paragraph. When the usage
        # text is inline, extract it directly from the line and then capture the
        # following paragraph as summary (if no summary was found yet).
        if stripped.upper().startswith("USAGE") or stripped.rstrip(":").strip().upper() == "USAGE":
            inline = re.sub(r"^usage:?\s*", "", stripped, flags=re.IGNORECASE).strip()
            if inline:
                # Inline form: "Usage:  docker [OPTIONS] COMMAND"
                result["usage"] = inline
                # Capture the next non-empty paragraph as summary if not yet set.
                # A real section heading ends with ":" or is ALL-CAPS; a prose
                # summary line does not — so we can safely capture it here.
                if not result["summary"]:
                    while i < n and not lines[i].strip():
                        i += 1
                    if i < n:
                        next_line = lines[i].strip()
                        is_section = (
                            next_line.endswith(":")
                            or next_line.upper() == next_line
                            or next_line.upper().startswith("USAGE")
                            or next_line.startswith("#")
                        )
                        if next_line and not is_section:
                            result["summary"] = next_line
                            i += 1
            else:
                # Next non-empty line is the usage string (gh/kubectl style)
                while i < n and not lines[i].strip():
                    i += 1
                if i < n and not lines[i].strip().startswith("#"):
                    result["usage"] = lines[i].strip()
                    i += 1
            continue

        # Section heading?
        m = _SECTION_RE.match(stripped)
        if m:
            heading = m.group(1).strip()
            if _is_command_section(heading):
                kind = "commands"
            elif _is_flag_section(heading):
                kind = "flags"
            else:
                kind = "other"
            current_section = {"heading": heading, "kind": kind, "entries": []}
            result["sections"].append(current_section)
            continue

        # Entry within a section
        if current_section is None:
            continue

        if current_section["kind"] == "commands":
            parsed = parse_command_line(line)
            if parsed:
                name, summary = parsed
                current_section["entries"].append({"name": name, "summary": summary})

        elif current_section["kind"] == "flags":
            parsed_flag = parse_flag_line(line)
            if parsed_flag:
                current_section["entries"].append(parsed_flag)
            elif current_section["entries"] and line.startswith("      "):
                # Continuation of previous flag's description
                last = current_section["entries"][-1]
                if "description" in last:
                    last["description"] += " " + stripped
                else:
                    last["description"] = stripped

    return result


# ---------------------------------------------------------------------------
# Discovery walk state
# ---------------------------------------------------------------------------

@dataclass
class WalkState:
    max_depth: int
    max_commands: int
    per_call_timeout: float
    total_timeout: float
    start_time: float
    warnings: list[str] = field(default_factory=list)
    commands_walked: int = 0
    depth_reached: int = 0
    # MUST FIX 1: Accumulator for all groups produced during the walk
    groups_accumulator: list[dict] = field(default_factory=list)

    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    def timed_out(self) -> bool:
        return self.elapsed() >= self.total_timeout

    def over_limit(self) -> bool:
        return self.commands_walked >= self.max_commands


# ---------------------------------------------------------------------------
# Recursive walk
# ---------------------------------------------------------------------------

def walk(
    cli: str,
    path: list[str],
    depth: int,
    state: WalkState,
) -> Optional[dict]:
    """
    Fetch `<cli> [path...] --help` and return a group dict, or None on fatal error.

    Mutates state.warnings, state.commands_walked, state.depth_reached,
    and state.groups_accumulator (MUST FIX 1: deep groups are pushed here).
    """
    state.depth_reached = max(state.depth_reached, depth)

    if state.timed_out():
        state.warnings.append(
            f"total timeout reached before walking: {cli} {' '.join(path)} --help"
        )
        return None

    if state.over_limit():
        state.warnings.append(
            f"command limit ({state.max_commands}) reached; halting at: "
            f"{cli} {' '.join(path)}"
        )
        return None

    cmd_args = [cli] + path + ["--help"]
    raw, returncode, timed_out = run_help(cmd_args, state.per_call_timeout)

    state.commands_walked += 1

    if timed_out:
        state.warnings.append(f"timeout: {cli} {' '.join(path)} --help")
        return None

    clean = strip_ansi(raw)

    if returncode != 0:
        if not clean.strip():
            # Fatal at root level — handled by caller.
            # At sub-level, just skip.
            state.warnings.append(
                f"non-zero exit, empty stdout: {' '.join(cmd_args)}"
            )
            return None
        else:
            state.warnings.append(
                f"non-zero exit (rc={returncode}), parsing anyway: "
                f"{' '.join(cmd_args)}"
            )

    parsed = parse_help_text(clean)

    # Build the group dict (group name is last path segment, or root)
    if path:
        raw_name = path[-1]
        group_name = raw_name.replace("_", "-")
    else:
        group_name = cli.replace("_", "-")

    group: dict = {
        "name": group_name,
        "path": list(path) if path else [cli],
    }

    if parsed["summary"]:
        group["summary"] = parsed["summary"]

    # MUST FIX 3: Store usage on the group
    if parsed["usage"]:
        group["usage"] = parsed["usage"]

    # Collect subcommands from all command sections
    sub_names: list[tuple[str, str]] = []
    for section in parsed["sections"]:
        if section["kind"] == "commands":
            for entry in section["entries"]:
                sub_names.append((entry["name"], entry["summary"]))

    # Collect flags from flag sections
    # MUST FIX 3: Store flags on the group
    flags: list[dict] = []
    for section in parsed["sections"]:
        if section["kind"] == "flags":
            flags.extend(section["entries"])

    if flags:
        group["flags"] = flags

    # Recurse into subcommands if depth allows
    if depth < state.max_depth and sub_names:
        commands: list[dict] = []
        for sub_name, sub_summary in sub_names:
            if state.timed_out() or state.over_limit():
                break

            sub_path = (list(path) if path else []) + [sub_name]

            if depth + 1 >= state.max_depth:
                # At max depth — record as leaf command, do not recurse
                cmd_path = (list(path) if path else [cli]) + [sub_name]
                if len(cmd_path) < 2:
                    cmd_path = [cli] + cmd_path
                leaf: dict = {
                    "name": sub_name,
                    "path": cmd_path,
                }
                if sub_summary:
                    leaf["summary"] = sub_summary
                commands.append(leaf)
            else:
                # Recurse to get more detail
                sub_group = walk(cli, sub_path, depth + 1, state)
                if sub_group is not None:
                    # MUST FIX 1: The sub_group is already pushed to
                    # groups_accumulator by the recursive call (or will be
                    # promoted here if it has commands — see flatten logic
                    # in discover()). Build a leaf command entry that
                    # references this sub_group's path.
                    cmd_path = (list(path) if path else [cli]) + [sub_name]
                    if len(cmd_path) < 2:
                        cmd_path = [cli] + cmd_path
                    cmd: dict = {
                        "name": sub_name,
                        "path": cmd_path,
                    }
                    if sub_group.get("summary"):
                        cmd["summary"] = sub_group["summary"]
                    elif sub_summary:
                        cmd["summary"] = sub_summary
                    # MUST FIX 3: Transfer usage and flags from sub_group to cmd
                    if sub_group.get("usage"):
                        cmd["usage"] = sub_group["usage"]
                    if sub_group.get("flags"):
                        cmd["flags"] = sub_group["flags"]
                    if sub_group.get("raw_help"):
                        cmd["raw_help"] = sub_group["raw_help"]
                    commands.append(cmd)

                    # MUST FIX 1: If the sub_group itself has commands (i.e., it
                    # is a group, not a leaf), push it as a flat sibling into the
                    # accumulator with a hyphenated name derived from its path.
                    if sub_group.get("commands") and len(sub_path) > 1:
                        flat_name = "-".join(sub_path)
                        # Normalize to match schema: ^[a-z0-9][a-z0-9-]*$
                        flat_name = flat_name.lower()
                        flat_group: dict = {
                            "name": flat_name,
                            "path": list(sub_path),
                        }
                        if sub_group.get("summary"):
                            flat_group["summary"] = sub_group["summary"]
                        if sub_group.get("usage"):
                            flat_group["usage"] = sub_group["usage"]
                        if sub_group.get("flags"):
                            flat_group["flags"] = sub_group["flags"]
                        flat_group["commands"] = sub_group["commands"]
                        state.groups_accumulator.append(flat_group)
                else:
                    # Failed sub-walk; record as bare leaf
                    cmd_path = (list(path) if path else [cli]) + [sub_name]
                    if len(cmd_path) < 2:
                        cmd_path = [cli] + cmd_path
                    bare: dict = {
                        "name": sub_name,
                        "path": cmd_path,
                    }
                    if sub_summary:
                        bare["summary"] = sub_summary
                    commands.append(bare)

        if commands:
            group["commands"] = commands

    elif sub_names:
        # Depth cap reached — record subcommands as bare leaves
        commands = []
        for sub_name, sub_summary in sub_names:
            cmd_path = (list(path) if path else [cli]) + [sub_name]
            if len(cmd_path) < 2:
                cmd_path = [cli] + cmd_path
            leaf = {"name": sub_name, "path": cmd_path}
            if sub_summary:
                leaf["summary"] = sub_summary
            commands.append(leaf)
        if commands:
            group["commands"] = commands

    # If we could not parse any structure, attach raw help for downstream use
    if not sub_names:
        group["raw_help"] = clean

    return group


# ---------------------------------------------------------------------------
# Top-level discover orchestration
# ---------------------------------------------------------------------------

def get_cli_version(cli: str, per_call_timeout: float) -> Optional[str]:
    """Try to get the CLI version string."""
    for flag in ["--version", "version", "-v"]:
        raw, rc, timed_out = run_help([cli, flag], per_call_timeout)
        if not timed_out and raw.strip():
            # Take the first non-empty line
            for line in strip_ansi(raw).splitlines():
                line = line.strip()
                if line:
                    return line
    return None


def discover(cli_name: str, opts: argparse.Namespace) -> dict:
    """
    Orchestrate the full discovery run.

    Returns the complete help-tree dict on success.
    Calls sys.exit(1) if the root help invocation fails fatally.
    """
    binary = shutil.which(cli_name)
    if binary is None:
        print(f"error: '{cli_name}' not found on PATH", file=sys.stderr)
        sys.exit(1)

    state = WalkState(
        max_depth=opts.max_depth,
        max_commands=opts.max_commands,
        per_call_timeout=opts.per_call_timeout,
        total_timeout=opts.total_timeout,
        start_time=time.monotonic(),
    )

    # --- Root help ---
    root_args = [cli_name, "--help"]
    raw_root, root_rc, root_timed_out = run_help(root_args, opts.per_call_timeout)
    state.commands_walked += 1

    if root_timed_out:
        print(
            f"error: root '--help' timed out after {opts.per_call_timeout}s",
            file=sys.stderr,
        )
        sys.exit(1)

    clean_root = strip_ansi(raw_root)

    if root_rc != 0:
        if not clean_root.strip():
            print(
                f"error: '{cli_name} --help' exited {root_rc} with no output",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            state.warnings.append(
                f"root '--help' exited {root_rc} but had output; parsing anyway"
            )

    root_parsed = parse_help_text(clean_root)

    # --- CLI metadata ---
    cli_name_normalized = cli_name.replace("_", "-")
    cli_info: dict = {"name": cli_name_normalized, "binary": binary}

    if root_parsed.get("summary"):
        cli_info["summary"] = root_parsed["summary"]

    # Version (best-effort, non-blocking)
    version = get_cli_version(cli_name, opts.per_call_timeout)
    if version:
        cli_info["version"] = version

    # --- Global flags from root help ---
    # MUST FIX 4: Only extract flags from the root --help FLAGS section.
    # INHERITED FLAGS from sub-group help outputs are not global flags.
    global_flags: list[dict] = []
    for section in root_parsed["sections"]:
        if section["kind"] == "flags" and section["heading"].upper().rstrip(":").strip() in {
            "FLAGS", "OPTIONS", "GLOBAL FLAGS", "GLOBAL OPTIONS",
        }:
            global_flags.extend(section["entries"])

    # --- Walk top-level command groups ---
    top_level_groups: list[dict] = []
    top_commands: list[tuple[str, str]] = []
    for section in root_parsed["sections"]:
        if section["kind"] == "commands":
            for entry in section["entries"]:
                top_commands.append((entry["name"], entry["summary"]))

    for group_name, group_summary in top_commands:
        if state.timed_out():
            state.warnings.append(
                f"total timeout reached; skipping group: {group_name}"
            )
            break
        if state.over_limit():
            state.warnings.append(
                f"command limit reached; skipping group: {group_name}"
            )
            break

        # Reset per-top-level-group accumulator for flat siblings
        state.groups_accumulator = []

        group = walk(cli_name, [group_name], 1, state)
        if group is not None:
            # Ensure summary comes from root if walk didn't capture one
            if "summary" not in group and group_summary:
                group["summary"] = group_summary
            top_level_groups.append(group)
            # MUST FIX 1: Collect any flat deep siblings accumulated during walk
            top_level_groups.extend(state.groups_accumulator)
        else:
            # Bare group entry from root listing
            bare_group: dict = {"name": group_name.replace("_", "-"), "path": [group_name]}
            if group_summary:
                bare_group["summary"] = group_summary
            top_level_groups.append(bare_group)

    elapsed_ms = int(state.elapsed() * 1000)

    tree: dict = {
        "cli": cli_info,
        "groups": top_level_groups,
        "discovery": {
            "depth_reached": state.depth_reached,
            "commands_walked": state.commands_walked,
            "elapsed_ms": elapsed_ms,
            "warnings": state.warnings,
        },
    }
    if global_flags:
        tree["global_flags"] = global_flags

    return tree


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Walk <cli> --help recursively and emit a canonical JSON help tree.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("cli", help="CLI binary name (must be on PATH)")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        metavar="N",
        help="Maximum recursion depth (root = 0, top-level groups = 1)",
    )
    parser.add_argument(
        "--max-commands",
        type=int,
        default=500,
        metavar="N",
        help="Maximum number of --help invocations before halting",
    )
    parser.add_argument(
        "--per-call-timeout",
        type=float,
        default=5.0,
        metavar="SECS",
        help="Per-invocation timeout in seconds",
    )
    parser.add_argument(
        "--total-timeout",
        type=float,
        default=30.0,
        metavar="SECS",
        help="Total wall-clock timeout for the entire discovery run",
    )
    parser.add_argument(
        "--output",
        default="-",
        metavar="PATH",
        help="Output file path (default: stdout)",
    )

    opts = parser.parse_args()

    tree = discover(opts.cli, opts)

    output = json.dumps(tree, indent=2, ensure_ascii=False)

    if opts.output == "-":
        print(output)
    else:
        with open(opts.output, "w", encoding="utf-8") as f:
            f.write(output)
            f.write("\n")


if __name__ == "__main__":
    main()
