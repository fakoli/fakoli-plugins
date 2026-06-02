#!/usr/bin/env python3
"""Append a note to notes.jsonl as an ``add`` operation.

Usage (unchanged from v1):
    python3 add-note.py "your note text here"
    echo "your note" | python3 add-note.py        # reads stdin if no arg

#hashtags in the text are extracted into a tags index (and kept in the
text). See notes_lib.py for the op-log schema and folding rules.
"""
import sys

import notes_lib


def main() -> int:
    text = notes_lib.read_text_arg(sys.argv[1:])
    if not text:
        print("Nothing to record (empty note).", file=sys.stderr)
        return 1

    op = notes_lib.add_note(text)
    tags = op.get("tags", [])
    tag_note = f" tags={','.join(tags)}" if tags else ""
    print(f"Saved [{op['id']}] at {op['ts']}{tag_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
