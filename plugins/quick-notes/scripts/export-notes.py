#!/usr/bin/env python3
"""Export current (non-deleted) notes to notes.md.

Usage:
    python3 export-notes.py            # writes notes.md next to notes.jsonl

Notes are grouped by date (## YYYY-MM-DD), newest day first, each note
listed with its time, id, and text. The op-log is folded first so edits
and deletes are reflected.
"""
from pathlib import Path

import notes_lib

OUT = Path(__file__).with_name("notes.md")


def main() -> int:
    count = notes_lib.export_markdown(OUT)
    print(f"Wrote {count} note(s) to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
