#!/usr/bin/env python3
"""Shared core for the note-taking toolkit (v2).

The on-disk format is an append-only operation log (one JSON object per
line in ``notes.jsonl``). Nothing is ever rewritten or deleted in place;
edits and deletes are new operations that *reference* an earlier add.

Operation schema (one per line)::

    add:    {"ts","id","op":"add","note","tags":[...],"source":<optional>}
    edit:   {"ts","id","op":"edit","target":<id-of-add>,"note":<new text>}
    delete: {"ts","id","op":"delete","target":<id-of-add>}

Backward compatibility: a legacy line with no ``"op"`` key is treated as
``op:"add"`` (the original v1 schema was ``{"ts","id","note"}``).

Readers *fold* the op-log into the current state: edits replace the note
text of their target, deletes drop the target, and what remains is the
live set of notes. This module owns that logic; the CLI scripts are thin
wrappers around it.
"""
import json
import os
import re
import sys
import uuid
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The notes log is the user's *data* and is kept separate from this plugin's
# *code* so reinstalling/updating the plugin never touches notes. Resolution:
#   1. $NOTES_LOG  (explicit override; ~ is expanded)
#   2. ~/technical-notes/notes.jsonl  (portable default)
# Callers (tests, CLIs) may still pass an explicit ``log=`` path to override.
def _default_log() -> Path:
    env = os.environ.get("NOTES_LOG")
    if env:
        return Path(env).expanduser()
    return Path.home() / "technical-notes" / "notes.jsonl"


DEFAULT_LOG = _default_log()

# Matches "#hashtag" tokens: a '#' at the start of the string or right after
# whitespace, then a word char followed by word/hyphen chars. ``\w`` is
# Unicode-aware, so "#café" and "#日本語" tag correctly, while mid-token cases
# like "C#sharp" or "a#b" are deliberately NOT treated as tags.
_TAG_RE = re.compile(r"(?:^|(?<=\s))#(\w[\w-]*)", re.UNICODE)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """A short, unique-enough id (8 hex chars), matching the v1 format."""
    return uuid.uuid4().hex[:8]


def extract_tags(text: str) -> list[str]:
    """Return lowercased, de-duplicated #hashtags found in ``text``.

    Tags stay in the note text; this is purely an index extracted on add.
    Order of first appearance is preserved so output is stable.
    """
    seen = []
    for match in _TAG_RE.findall(text):
        tag = match.lower()
        if tag not in seen:
            seen.append(tag)
    return seen


# --------------------------------------------------------------------------
# Append (the only writer)
# --------------------------------------------------------------------------
@contextmanager
def write_lock(log: Path):
    """Cross-platform, bounded lock; never silently write without exclusion."""
    log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = log.with_name(log.name + ".lock")
    deadline = time.monotonic() + 5
    while True:
        try:
            lock.mkdir(mode=0o700)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise OSError("Notes writer is locked; if it crashed, confirm it stopped before removing " + str(lock))
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.rmdir()


def append_op(op: dict, log: Path = DEFAULT_LOG, require_existing: bool = False) -> None:
    """Append one complete record under the writer lock, preserving damaged tails."""
    line = (json.dumps(op, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with write_lock(log):
        if require_existing and op.get("target") not in {n["id"] for n in current_notes(log)}:
            raise ValueError("No live note with the requested id")
        # A valid final JSON object without a newline is a legal legacy log.
        # Separate it before appending; never glue a new operation to its tail.
        prefix = b""
        if log.exists() and log.stat().st_size:
            with log.open("rb") as check:
                check.seek(-1, 2)
                if check.read(1) != b"\n":
                    prefix = b"\n"
        fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "ab") as stream:
            stream.write(prefix + line)
            stream.flush()
            os.fsync(stream.fileno())


def add_note(text: str, source: str | None = None, log: Path = DEFAULT_LOG) -> dict:
    """Append an ``add`` op for ``text`` and return the stored op."""
    op = {
        "ts": _now_iso(),
        "id": _new_id(),
        "op": "add",
        "note": text,
        "tags": extract_tags(text),
    }
    if source is not None:
        op["source"] = source
    append_op(op, log)
    return op


def edit_note(target: str, new_text: str, log: Path = DEFAULT_LOG, require_existing: bool = False) -> dict:
    """Append an ``edit`` op pointing at the add identified by ``target``."""
    op = {
        "ts": _now_iso(),
        "id": _new_id(),
        "op": "edit",
        "target": target,
        "note": new_text,
    }
    append_op(op, log, require_existing=require_existing)
    return op


def delete_note(target: str, log: Path = DEFAULT_LOG, require_existing: bool = False) -> dict:
    """Append a ``delete`` op pointing at the add identified by ``target``."""
    op = {
        "ts": _now_iso(),
        "id": _new_id(),
        "op": "delete",
        "target": target,
    }
    append_op(op, log, require_existing=require_existing)
    return op


# --------------------------------------------------------------------------
# Read + fold
# --------------------------------------------------------------------------
def load_ops(log: Path = DEFAULT_LOG) -> list[dict]:
    """Read raw operations from the log, tolerating blank/corrupt lines.

    A legacy line with no ``"op"`` key is normalized to ``op:"add"`` here so
    the rest of the code never has to special-case it. Tags are also
    backfilled for legacy adds that predate tag extraction.
    """
    if not log.exists():
        return []
    ops = []
    skipped = 0
    for line in log.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or not obj["id"]:
            skipped += 1
            continue
        if obj.get("op", "add") in ("add", "edit") and not isinstance(obj.get("note"), str):
            skipped += 1
            continue
        if obj.get("op") in ("edit", "delete") and not isinstance(obj.get("target"), str):
            skipped += 1
            continue
        if "tags" in obj and (not isinstance(obj["tags"], list) or not all(isinstance(tag, str) for tag in obj["tags"])):
            skipped += 1
            continue
        if "op" not in obj:
            # Legacy v1 line: {"ts","id","note"} -> treat as an add.
            obj["op"] = "add"
        if obj["op"] == "add" and "tags" not in obj:
            obj["tags"] = extract_tags(obj.get("note", ""))
        ops.append(obj)
    if skipped:
        print(f"notes: skipped {skipped} malformed operation(s); original log preserved", file=sys.stderr)
    return ops


def fold(ops: list[dict]) -> list[dict]:
    """Fold an op-log into the current set of live notes (oldest-first).

    - ``add`` creates a note keyed by its id.
    - ``edit`` replaces the note text of its target (if the target lives).
    - ``delete`` drops its target.

    Returns a list of note dicts ``{"ts","id","note","tags","source"?}``
    in original add order; callers reverse for newest-first display.
    """
    notes: dict[str, dict] = {}
    order: list[str] = []  # preserve add order for stable output

    for op in ops:
        kind = op.get("op", "add")
        if kind == "add":
            nid = op.get("id")
            if nid is None:
                continue
            note = {
                "ts": op.get("ts", ""),
                "id": nid,
                "note": op.get("note", ""),
                "tags": op.get("tags", []),
            }
            if "source" in op:
                note["source"] = op["source"]
            if nid in notes or nid in order:
                continue  # Duplicate add IDs must not duplicate or resurrect notes.
            notes[nid] = note
            order.append(nid)
        elif kind == "edit":
            target = op.get("target")
            if target in notes:
                notes[target]["note"] = op.get("note", "")
                # Re-extract tags so edits keep the tag index accurate.
                notes[target]["tags"] = extract_tags(op.get("note", ""))
        elif kind == "delete":
            target = op.get("target")
            if target in notes:
                del notes[target]
        # Unknown op kinds are ignored (forward compatibility).

    return [notes[nid] for nid in order if nid in notes]


def current_notes(log: Path = DEFAULT_LOG) -> list[dict]:
    """Load the log and fold it into live notes (oldest-first)."""
    return fold(load_ops(log))


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------
def _parse_ts(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None if unparseable."""
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    # Normalize to UTC so every downstream comparison, date-grouping and
    # rendering agrees: naive timestamps are assumed UTC; aware ones (e.g. a
    # "-05:00" offset) are converted, so export headings match the filters.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def filter_notes(
    notes: list[dict],
    keywords: list[str] | None = None,
    tag: str | None = None,
    today: bool = False,
    since: str | None = None,
) -> list[dict]:
    """Apply AND-keyword search, tag, today and since filters.

    All filters are conjunctive (a note must satisfy every active filter).
    Keyword and tag matching are case-insensitive.
    """
    result = notes

    if keywords:
        lowered = [k.lower() for k in keywords]
        result = [
            n for n in result
            if all(k in n.get("note", "").lower() for k in lowered)
        ]

    if tag:
        want = tag.lstrip("#").lower()
        result = [n for n in result if want in n.get("tags", [])]

    if today:
        start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = [
            n for n in result
            if (dt := _parse_ts(n.get("ts", ""))) is not None and dt >= start
        ]

    if since:
        # since is YYYY-MM-DD, interpreted as midnight UTC that day.
        try:
            start = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError(f"--since expects YYYY-MM-DD, got {since!r}")
        result = [
            n for n in result
            if (dt := _parse_ts(n.get("ts", ""))) is not None and dt >= start
        ]

    return result


def newest_first(notes: list[dict]) -> list[dict]:
    """Return notes ordered newest-first (the display order)."""
    return list(reversed(notes))


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------
def stats(notes: list[dict], top_n: int = 5) -> dict:
    """Compute summary stats over live notes.

    Returns ``{"total", "last_7_days", "top_tags": [(tag, count), ...]}``.
    """
    total = len(notes)

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    last_7 = sum(
        1 for n in notes
        if (dt := _parse_ts(n.get("ts", ""))) is not None and dt >= cutoff
    )

    counts: dict[str, int] = {}
    for n in notes:
        for tag in n.get("tags", []):
            counts[tag] = counts.get(tag, 0) + 1
    # Sort by count desc, then tag name for deterministic ties.
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]

    return {"total": total, "last_7_days": last_7, "top_tags": top}


# --------------------------------------------------------------------------
# Markdown export
# --------------------------------------------------------------------------
def render_markdown(notes: list[dict]) -> str:
    """Render live notes as Markdown grouped by date, newest day first.

    Each day is an H2 ``## YYYY-MM-DD`` heading; within a day notes are
    listed newest-first with their time, id, and text.
    """
    # Group by date string. Use a dict keyed by YYYY-MM-DD.
    by_day: dict[str, list[dict]] = {}
    for n in notes:
        dt = _parse_ts(n.get("ts", ""))
        day = dt.date().isoformat() if dt else "unknown-date"
        by_day.setdefault(day, []).append((dt, n))

    lines = ["# Notes", ""]
    for day in sorted(by_day, reverse=True):
        lines.append(f"## {day}")
        lines.append("")
        # Newest note first within the day. Fall back to datetime.min for
        # unparseable timestamps so the sort key never compares None < None
        # (which would raise TypeError and abort the whole export).
        _floor = datetime.min.replace(tzinfo=timezone.utc)
        entries = sorted(
            by_day[day],
            key=lambda pair: (pair[0] is not None, pair[0] or _floor),
            reverse=True,
        )
        for dt, n in entries:
            time_str = dt.strftime("%H:%M:%S") if dt else "??:??:??"
            nid = n.get("id", "????????")
            text = n.get("note", "")
            lines.append(f"- **{time_str}** `[{nid}]` {text}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def export_markdown(out: Path, log: Path = DEFAULT_LOG) -> int:
    """Write the Markdown export to ``out``; return the note count."""
    if out.resolve() == log.resolve():
        raise ValueError("Export destination cannot replace the operation log")
    notes = current_notes(log)
    out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    out.write_text(render_markdown(notes), encoding="utf-8")
    return len(notes)


# --------------------------------------------------------------------------
# Small shared CLI helper
# --------------------------------------------------------------------------
def read_text_arg(argv: list[str]) -> str:
    """Join CLI args into text, or read stdin if none were given.

    Shared by add-note.py and edit-note.py so dictation can pipe in.
    """
    if argv:
        return " ".join(argv).strip()
    return sys.stdin.read().strip()
