#!/usr/bin/env python3
"""Read back notes from notes.jsonl, newest first.

Usage (v1-compatible plus new filters):
    python3 read-notes.py                     # all notes, newest first
    python3 read-notes.py -n 10               # the 10 most recent
    python3 read-notes.py retry backoff       # notes matching ALL keywords (case-insensitive)
    python3 read-notes.py -n 5 deploy         # 5 most recent matches for "deploy"
    python3 read-notes.py --tag work          # notes carrying #work
    python3 read-notes.py --today             # notes from today (UTC)
    python3 read-notes.py --since 2026-06-01  # notes on/after that date
    python3 read-notes.py --stats             # totals, last-7-days, top tags

The reader folds the op-log (add/edit/delete, plus legacy no-op lines) into
the current set of live notes before filtering. See notes_lib.py.
"""
import sys

import notes_lib


def main() -> int:
    args = sys.argv[1:]
    limit = None
    tag = None
    since = None
    today = False
    show_stats = False
    keywords = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-n", "--limit"):
            i += 1
            if i >= len(args) or not args[i].isdigit():
                print("Expected a number after -n", file=sys.stderr)
                return 1
            limit = int(args[i])
        elif arg == "--tag":
            i += 1
            if i >= len(args):
                print("Expected a tag name after --tag", file=sys.stderr)
                return 1
            tag = args[i]
        elif arg == "--since":
            i += 1
            if i >= len(args):
                print("Expected YYYY-MM-DD after --since", file=sys.stderr)
                return 1
            since = args[i]
        elif arg == "--today":
            today = True
        elif arg == "--stats":
            show_stats = True
        elif arg.startswith("--"):
            # Reject unknown long flags instead of silently treating a typo
            # like "--tags" as a search keyword.
            print(f"Unknown flag: {arg}", file=sys.stderr)
            return 1
        else:
            keywords.append(arg)
        i += 1

    notes = notes_lib.current_notes()

    try:
        notes = notes_lib.filter_notes(
            notes, keywords=keywords, tag=tag, today=today, since=since
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # --stats summarizes the (filtered) set instead of listing notes.
    if show_stats:
        s = notes_lib.stats(notes)
        print(f"Total notes:        {s['total']}")
        print(f"Last 7 days:        {s['last_7_days']}")
        if s["top_tags"]:
            print("Top tags:")
            for tag_name, count in s["top_tags"]:
                print(f"    #{tag_name}: {count}")
        else:
            print("Top tags:           (none)")
        return 0

    notes = notes_lib.newest_first(notes)
    if limit is not None:
        notes = notes[:limit]

    if not notes:
        any_filter = bool(keywords or tag or today or since)
        print("No matching notes." if any_filter else "No notes yet.")
        return 0

    for n in notes:
        nid = n.get("id", "????????")
        ts = n.get("ts", "?")
        note = n.get("note", "")
        print(f"[{nid}] {ts}\n    {note}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
