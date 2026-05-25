#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
override.py — Merge an override YAML file into a help-tree dict produced by discover.py.

Usage (Python API):
    from override import merge_override, OverrideError

    tree   = json.load(open("gh-help-tree.json"))
    overrides = yaml.safe_load(open("gh-overrides.yaml"))
    patched = merge_override(tree, overrides)

Override YAML schema (all fields optional):
    meta_skills:
      - name: foo
        description: bar

    groups:
      - name: pr               # must match a group name in tree["groups"]
        skip: true             # omit this group entirely
        description: "new description"   # overrides group["summary"]
        extra_guidance: "text"           # stored on node for downstream use
        commands:
          - name: create       # must match a command name in the group
            skip: true         # omit this command from the group

Delta note: the help-tree uses "summary" for a group's one-liner; the override
YAML field is named "description" to match human-author intent. merge_override
writes the value to group["summary"] so downstream consumers see it there.

"extra_guidance" is written to group["extra_guidance"] for downstream pickup by
the playbook step that writes skills. It has no effect on the tree structure.

Errors:
    OverrideError — raised when an override names an unknown group (with
    "did you mean <closest>?" suggestion) or an unknown command within a group.
    Callers should catch this and report the suggestion to the user.
"""

import argparse
import difflib
import json
import sys
from typing import Any


class OverrideError(ValueError):
    """Raised when an override references an unknown group or command."""


def merge_override(help_tree: dict, override: dict) -> dict:
    """
    Apply override dict to a help-tree and return the modified tree.

    The input tree is shallow-copied at the top level; groups list is rebuilt
    so the original is not mutated.

    Parameters
    ----------
    help_tree : dict
        Output of discover.py — must have a "groups" key with a list of group
        dicts, each having at least "name".
    override : dict
        Parsed override YAML.  All keys are optional.

    Returns
    -------
    dict
        Modified help-tree.  Extra key "warnings" (list[str]) is added to the
        tree (NOT to discovery.warnings) to record non-fatal issues such as
        references to unknown commands within known groups.
    """
    if not override:
        return dict(help_tree)

    result = dict(help_tree)
    groups: list[dict] = [dict(g) for g in help_tree.get("groups", [])]
    warnings: list[str] = []

    # Build lookup: group name → index in groups list
    group_index: dict[str, int] = {g["name"]: i for i, g in enumerate(groups)}

    # --- Process meta_skills ---
    if "meta_skills" in override:
        result["meta_skills"] = list(override["meta_skills"])

    # --- Process group overrides ---
    groups_to_skip: set[str] = set()

    for group_override in override.get("groups", []):
        gname = group_override.get("name")
        if gname is None:
            continue

        if gname not in group_index:
            # Unknown group — raise with suggestion
            known = list(group_index.keys())
            suggestions = difflib.get_close_matches(gname, known, n=1, cutoff=0.6)
            suggestion_msg = (
                f"did you mean '{suggestions[0]}'?" if suggestions else "no close match found"
            )
            raise OverrideError(
                f"override references unknown group '{gname}' ({suggestion_msg})"
            )

        if group_override.get("skip"):
            groups_to_skip.add(gname)
            continue

        idx = group_index[gname]
        group = dict(groups[idx])  # shallow copy the group being modified

        if "description" in group_override:
            group["summary"] = group_override["description"]

        if "extra_guidance" in group_override:
            group["extra_guidance"] = group_override["extra_guidance"]

        # Process command-level overrides
        if "commands" in group_override:
            existing_cmds: list[dict] = list(group.get("commands", []))
            cmd_index: dict[str, int] = {c["name"]: i for i, c in enumerate(existing_cmds)}
            cmds_to_skip: set[str] = set()

            for cmd_override in group_override["commands"]:
                cname = cmd_override.get("name")
                if cname is None:
                    continue
                if cname not in cmd_index:
                    warnings.append(
                        f"override references unknown command '{cname}' "
                        f"in group '{gname}'; ignoring"
                    )
                    continue
                if cmd_override.get("skip"):
                    cmds_to_skip.add(cname)

            if cmds_to_skip:
                group["commands"] = [
                    c for c in existing_cmds if c["name"] not in cmds_to_skip
                ]

        groups[idx] = group

    # Apply group skips
    if groups_to_skip:
        groups = [g for g in groups if g["name"] not in groups_to_skip]

    result["groups"] = groups
    result["warnings"] = warnings
    return result


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(
        description="Merge an override YAML into a help-tree JSON; emit merged JSON to stdout."
    )
    parser.add_argument("--tree", required=True, help="Path to help-tree JSON.")
    parser.add_argument("--override", required=True, dest="override_path", help="Path to override YAML.")
    args = parser.parse_args()

    try:
        import yaml
    except ImportError:
        print("error: pyyaml required. Invoke with: uv run --with pyyaml --script", file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.tree, encoding="utf-8") as f:
            tree = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read tree '{args.tree}': {e}", file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.override_path, encoding="utf-8") as f:
            override = yaml.safe_load(f) or {}
    except OSError as e:
        print(f"error: cannot read override '{args.override_path}': {e}", file=sys.stderr)
        sys.exit(2)
    except yaml.YAMLError as e:
        print(f"error: malformed override YAML '{args.override_path}': {e}", file=sys.stderr)
        sys.exit(2)

    try:
        result = merge_override(tree, override)
    except OverrideError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":  # pragma: no cover
    main()
