#!/usr/bin/env python3
"""Edit an existing note by appending an ``edit`` operation.

Usage:
    python3 edit-note.py <id> "the new note text"
    echo "new text" | python3 edit-note.py <id>     # reads stdin if no text arg

The original add line is never rewritten; the edit is a new appended op
that the reader folds in (replacing the target's text). #hashtags in the
new text are re-extracted.
"""
import sys

import notes_lib


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("Usage: edit-note.py <id> <new text...>", file=sys.stderr)
        return 1

    target = args[0]
    new_text = notes_lib.read_text_arg(args[1:])
    if not new_text:
        print("Nothing to record (empty new text).", file=sys.stderr)
        return 1

    # Only allow editing a note that currently exists (live, not deleted).
    live_ids = {n["id"] for n in notes_lib.current_notes()}
    if target not in live_ids:
        print(f"No live note with id [{target}].", file=sys.stderr)
        return 1

    op = notes_lib.edit_note(target, new_text)
    print(f"Edited [{target}] at {op['ts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
