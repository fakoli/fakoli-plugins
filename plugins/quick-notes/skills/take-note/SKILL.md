---
name: take-note
description: Save a quick personal note to the user's notes log. Use whenever the user dictates or types something they want recorded as a note — e.g. "save a note…", "jot down…", "note that…", "take a note…", "remember this…", "add to my notes…", "log this thought…". Captures the spoken/typed content verbatim and appends it to the log. Use for capturing a thought, NOT for the user asking to read, search, or summarize existing notes (use find-notes for that).
---

# Take Note

Append a quick personal note to the user's append-only notes log.

## Storage

- **Toolkit (bundled in this plugin):** `${CLAUDE_PLUGIN_ROOT}/scripts/`
- **Log location:** `$NOTES_LOG` if set, otherwise `~/technical-notes/notes.jsonl`. The directory is created automatically on first note.

The log is JSON Lines: one operation object per line (`add`/`edit`/`delete`). Appending never rewrites existing lines.

## How to save a note

1. Take the note content — the user's words, minus the trigger phrase. (If they say "note that the deploy failed," the note is "the deploy failed.") Keep it verbatim; do not summarize, expand, or correct unless asked.
2. Append it by piping the text via **stdin** (never as a shell argument — stdin avoids quoting/escaping problems with the apostrophes, quotes, and punctuation common in dictation):

   ```bash
   printf '%s' "the note text here" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add-note.py"
   ```

   For multi-sentence or multi-line dictation, a heredoc is safest:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add-note.py" <<'NOTE'
   the full note text,
   possibly spanning lines
   NOTE
   ```

3. The script prints `Saved [id] at <timestamp>` (plus `tags=…` if any). Confirm to the user with the id and a one-line echo of what was saved, so they know it landed.

## Hashtag auto-tagging

Any `#hashtag` tokens in the dictated text are automatically extracted as tags by `add-note.py` — no extra flags needed. If the user says "note that the build is flaky #ci", save the text exactly as spoken; `#ci` becomes a searchable tag. (Mid-token `#`, e.g. `C#`, is not treated as a tag.)

## Editing and deleting notes

Notes can be corrected or removed after the fact:

- **Edit:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/edit-note.py" <id> "corrected text"` — or pipe new text via stdin.
- **Delete:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delete-note.py" <id>`

To edit or delete, first look up the note's 8-char id with `read-notes.py` (see the **find-notes** skill). Both operations append a new record; the original line is never rewritten.

## Notes

- Just append — do not create new files or change the log format.
- If the note is empty after removing the trigger phrase, ask the user what they'd like to record rather than saving a blank entry.
- This skill is for *capturing* notes. To read back, search, filter, or export, use the **find-notes** skill.
