# Changelog

## [1.0.1] - 2026-06-26

### Fixed
- `export-notes.py` now writes `notes.md` next to the active notes log (`$NOTES_LOG` or `~/technical-notes/notes.jsonl`) instead of inside the plugin code directory.
- Added a regression test proving the wrapper preserves the data/code separation guarantee.

## [1.0.0] - 2026-06-02

### Added
- Initial release.
- `take-note` skill — capture a note by dictation ("jot down…", "note that…"); appends via stdin so dictation punctuation survives. `#hashtags` are auto-extracted as tags.
- `find-notes` skill — read back, keyword/`--tag`/`--today`/`--since` search, `--stats`, and Markdown export, triggered by natural phrasing ("show my notes", "find notes about X").
- `/note <text>` slash command for explicit quick capture.
- Stdlib-only Python toolkit (`scripts/`): `notes_lib.py` core plus `add-note.py`, `read-notes.py`, `edit-note.py`, `delete-note.py`, `export-notes.py`.
- Append-only, event-sourced JSON Lines op-log (add/edit/delete; existing lines never rewritten; readers fold the log into the current live set). Backward compatible with legacy no-`op` lines.
- Durability: `fsync` on every append; `fcntl.flock`-guarded writes with graceful degradation; corrupt-line tolerance on read.
- UTC-normalized timestamps so search filters and export date-headings always agree.
- Data/code separation: notes are stored at `$NOTES_LOG` or `~/technical-notes/notes.jsonl`, outside the plugin, so updates never touch your notes.
- 24 unit tests (`scripts/test_notes.py`) covering folding, legacy compatibility, filters, stats, export (incl. malformed-timestamp and non-UTC cases), tag-boundary/Unicode extraction, and the `source` field.
