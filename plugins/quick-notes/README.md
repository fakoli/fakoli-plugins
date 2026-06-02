# quick-notes

Dictation-friendly personal notes for Claude Code. Speak (or type) a thought — *"jot down that the deploy is flaky #ops"* — and it's captured. Ask later — *"show my notes from today"*, *"find notes about deploy"* — and it's retrieved. Notes live in a durable, append-only log that survives crashes and plugin updates.

## What you get

- **Two skills** that trigger on natural language:
  - `take-note` — capture a thought ("note that…", "jot down…", "remember this…").
  - `find-notes` — read back, search, filter, get stats, export ("show my notes", "find notes about X", "how many notes…").
- **A `/note` command** for explicit quick capture: `/note pick up milk #errands`.
- **A small stdlib-only Python toolkit** (`scripts/`) you can also call directly.

## How it works

Notes are stored as an **append-only, event-sourced JSON Lines op-log**. Every change is one appended line — `add`, `edit`, or `delete` — and existing lines are never rewritten. Reading "folds" the log into the current live set (edits apply, deletes drop). This is why it's durable: a crash mid-write can at most lose the last line, never corrupt earlier notes. `#hashtags` in note text are auto-indexed as tags.

## Where your notes live

The **data** is deliberately separate from the **plugin code**, so updating or reinstalling the plugin never touches your notes:

- Default: `~/technical-notes/notes.jsonl` (created on your first note)
- Override: set `NOTES_LOG=/path/to/notes.jsonl`

## CLI reference (direct use)

All scripts are in `scripts/` (use `${CLAUDE_PLUGIN_ROOT}/scripts/...` from within Claude Code):

| Action | Command |
|---|---|
| Add | `add-note.py "text"` or `echo "text" \| add-note.py` |
| Read / search | `read-notes.py [-n N] [keywords...] [--tag NAME] [--today] [--since YYYY-MM-DD] [--stats]` |
| Edit | `edit-note.py <id> "new text"` or stdin |
| Delete | `delete-note.py <id>` |
| Export | `export-notes.py` → writes `notes.md` beside the log |

`read-notes.py` flags: `-n N` (most recent N), bare words (AND keyword search), `--tag NAME`, `--today`, `--since YYYY-MM-DD`, `--stats` (total + last-7-days + top tags). Unknown `--flags` are rejected rather than silently treated as search terms.

## Data format

Each line is one operation object:

```json
{"ts":"2026-06-02T14:30:00+00:00","id":"a1b2c3d4","op":"add","note":"deploy is flaky #ops","tags":["ops"]}
{"ts":"2026-06-02T15:00:00+00:00","id":"e5f6a7b8","op":"edit","target":"a1b2c3d4","note":"deploy is flaky on Mondays #ops"}
{"ts":"2026-06-02T16:00:00+00:00","id":"c9d0e1f2","op":"delete","target":"a1b2c3d4"}
```

Backward compatible: a legacy line with no `"op"` key is treated as an `add`.

## Design highlights

- **Append-only durability** with `fsync` on every write — survives power loss, not just clean exits.
- **Concurrency-safe** appends via `fcntl.flock`, degrading gracefully where unavailable.
- **Corrupt-line tolerance** — a malformed line is skipped, never fatal to a read or export.
- **UTC-normalized timestamps** so search filters and export date-headings always agree.

## Tests

```bash
python3 scripts/test_notes.py    # 24 unittest cases, on a temp log (never your real notes)
```

Covers add/edit/delete folding, legacy compatibility, keyword/tag/date filters, stats, Markdown export (including malformed-timestamp and non-UTC cases), tag-boundary/Unicode extraction, and the `source` field.

---

Single-user, local-first, no dependencies. Your notes are just a text file you fully own.
