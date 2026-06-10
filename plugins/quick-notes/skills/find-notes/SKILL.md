---
name: find-notes
description: Read back, search, browse, or get stats on the user's existing personal notes. Use when the user wants to retrieve or explore notes — e.g. "what notes do I have", "show my notes", "show me my recent notes", "find my notes about X", "read back my notes", "search my notes for…", "show notes from today", "notes tagged #work", "notes since last week", "how many notes do I have", "give me a summary of my notes", "export my notes", "save my notes to markdown". This skill is for RETRIEVING and SUMMARIZING existing notes, NOT for saving a new note (use take-note for that).
---

# Find Notes

Retrieve, search, and summarize the user's notes from the append-only log.

## Storage

- **Toolkit (bundled in this plugin):** `${CLAUDE_PLUGIN_ROOT}/scripts/`
- **Log location:** `$NOTES_LOG` if set, otherwise `~/technical-notes/notes.jsonl`.

The reader folds the op-log (add/edit/delete, plus legacy lines) into the current live set before filtering, so deleted notes never show and edits show their latest text.

## Map the request to a command

Run `read-notes.py` for reading/searching, `export-notes.py` for "export/save to markdown":

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/read-notes.py" [options]
```

| User intent | Command |
|---|---|
| Show everything (newest first) | `read-notes.py` |
| Most recent N | `read-notes.py -n 10` |
| Search (matches ALL keywords) | `read-notes.py deploy retry` |
| By tag | `read-notes.py --tag work` |
| From today | `read-notes.py --today` |
| Since a date | `read-notes.py --since 2026-06-01` |
| Combine N most recent matches | `read-notes.py -n 5 deploy` |
| Counts + last-7-days + top tags | `read-notes.py --stats` |
| Export to Markdown | `export-notes.py` (writes `notes.md` beside the log) |

For relative dates like "last week," compute the `YYYY-MM-DD` yourself and pass it to `--since`. For "today," prefer `--today`.

## Presenting results

After running the command, present the output **readably** — a short list with each note's text, date, and 8-char id (the id is what the user needs to edit or delete a note). Do not dump raw JSON. If `--stats`, summarize the totals in a sentence. If nothing matches, say so plainly.

## Cross-reference

To *capture* a new note, use the **take-note** skill. To edit/delete, find the id here first, then use `edit-note.py <id>` / `delete-note.py <id>` (see take-note).
