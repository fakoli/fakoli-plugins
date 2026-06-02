---
description: Save a quick note to your personal notes log
argument-hint: <note text>
---

The user wants to save this note, verbatim:

$ARGUMENTS

Save it by piping the exact text via stdin to the notes toolkit (a heredoc, so apostrophes/quotes/punctuation survive):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/add-note.py" <<'NOTE'
<the note text above, unchanged>
NOTE
```

Any `#hashtags` in the text become tags automatically. After it runs, confirm with the returned 8-char id and a one-line echo of what was saved.

If the note text above is empty, ask the user what they'd like to record instead of saving a blank entry. To read or search notes later, the user can just ask ("show my notes", "find notes about X") — the **find-notes** skill handles retrieval.
