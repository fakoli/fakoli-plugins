#!/usr/bin/env python3
"""Delete an existing note by appending a ``delete`` operation.

Usage:
    python3 delete-note.py <id>

The original add line is never removed; the delete is a new appended op
that the reader folds in (dropping the target). Deletes are reversible
only by editing the log directly -- by design nothing is destroyed.
"""
import sys

import notes_lib


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 1:
        print("Usage: delete-note.py <id>", file=sys.stderr)
        return 1

    target = args[0]
    live_ids = {n["id"] for n in notes_lib.current_notes()}
    if target not in live_ids:
        print(f"No live note with id [{target}].", file=sys.stderr)
        return 1

    op = notes_lib.delete_note(target)
    print(f"Deleted [{target}] at {op['ts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
