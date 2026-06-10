# Notes Toolkit v2 — Design

A personal, stdlib-only note-taking toolkit built on an append-only
**event-sourced operation log**. Nothing on disk is ever rewritten or
deleted in place; every change is a new line appended to `notes.jsonl`.

## Storage: the op-log

`notes.jsonl` is JSON Lines — one operation object per line.

| op | shape |
|----|-------|
| `add`    | `{"ts","id","op":"add","note","tags":[...],"source":<optional>}` |
| `edit`   | `{"ts","id","op":"edit","target":<id-of-add>,"note":<new text>}` |
| `delete` | `{"ts","id","op":"delete","target":<id-of-add>}` |

- `ts` — ISO-8601 UTC timestamp of the operation.
- `id` — 8 hex chars, unique per operation. For an `add`, this id is the
  note's permanent identity; `edit`/`delete` carry their own op id and
  point at an add via `target`.
- `tags` — lowercased, de-duplicated `#hashtags` extracted from the note
  text on add (the tags stay in the text too).

**Backward compatibility:** a legacy v1 line with no `"op"` key
(`{"ts","id","note"}`) is normalized to `op:"add"` at read time, and its
tags are backfilled. Old logs keep working unchanged.

## Folding: op-log → current state

Readers never trust a single line; they replay the whole log in order
(`notes_lib.fold`):

1. `add` creates a live note keyed by its id (add order remembered).
2. `edit` replaces the target's note text (and re-extracts tags), if the
   target is still live.
3. `delete` drops the target.
4. Edits/deletes against an unknown or already-deleted target are no-ops.

The result is the live set, presented **newest-first**.

### Why event-sourcing

- **Append-only is crash-safe and concurrency-friendly** — writers only
  ever append; there is no read-modify-write race on the file body.
- **Full history is preserved** — nothing is destructively lost; a delete
  is just another fact in the log.
- **Simple writers, smart reader** — all interpretation lives in one place
  (`fold`), so the CLIs stay thin.

## Concurrency

Appends take an exclusive `fcntl.flock` around the write
(`notes_lib.append_op`). If `fcntl` is unavailable (non-POSIX) or the
filesystem rejects the lock, the write still proceeds unlocked — degrade,
don't fail.

## Module layout

`notes_lib.py` owns append + load + fold + filter + stats + export. Every
CLI script is a thin wrapper that imports it:

| Command | Usage | Notes |
|---------|-------|-------|
| `add-note.py`    | `add-note.py "text"` or stdin | v1-compatible; extracts `#tags` |
| `read-notes.py`  | `read-notes.py [-n N] [keywords...] [--tag NAME] [--today] [--since YYYY-MM-DD] [--stats]` | v1-compatible; folds then filters |
| `edit-note.py`   | `edit-note.py <id> "new text"` or `<id>` + stdin | appends an `edit` op |
| `delete-note.py` | `delete-note.py <id>` | appends a `delete` op |
| `export-notes.py`| `export-notes.py` | writes `notes.md`, live notes grouped by date |

`read-notes.py` and `add-note.py` keep their exact v1 CLI because an
existing Claude Code skill invokes them that way.

## Filters (all conjunctive, case-insensitive where it applies)

- **keywords** — AND match: note must contain every keyword.
- **`--tag NAME`** — note must carry tag `NAME` (leading `#` optional).
- **`--today`** — ts on/after midnight UTC today.
- **`--since YYYY-MM-DD`** — ts on/after that date (midnight UTC).
- **`-n N`** — limit to N most recent (applied after filtering).
- **`--stats`** — total notes, notes in the last 7 days, top tags.

## Markdown export

`notes.md` is regenerated from the folded live set: an `# Notes` title,
then `## YYYY-MM-DD` headings newest-day-first, each note listed
newest-first within its day as `- **HH:MM:SS** \`[id]\` text`.

## Tests

`test_notes.py` (stdlib `unittest`) runs entirely against a temp log — the
real `notes.jsonl` is never touched. Coverage: tag extraction, edit fold,
delete fold, legacy no-`op` lines, corrupt-line skipping, keyword AND
search, tag/since filters, stats, and export output/ordering.
