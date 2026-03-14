---
description: Add a source to a NotebookLM notebook — supports URLs, local files, and YouTube links
allowed-tools: Bash
---

# Add Source to NotebookLM

Add a source (URL, file, or YouTube video) to the active notebook.

## Arguments

Parse from: `$ARGUMENTS`

Required:
- Source location: a URL, file path, or YouTube link

Options:
- `--notebook <id>`: Target a specific notebook instead of the active one
- `--no-wait`: Don't wait for processing to complete
- `--title "Custom Title"`: (informational only — title is auto-detected by NotebookLM)

## Workflow

1. **Detect source type** from the argument:
   - YouTube URL (contains `youtube.com` or `youtu.be`)
   - Web URL (starts with `http://` or `https://`)
   - Local file path (everything else — verify it exists)

2. **Verify active notebook** (if no `--notebook`):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm status
   ```

3. **Add the source**:
   ```bash
   # URL or YouTube
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source add "https://example.com/article" --json

   # Local file
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source add ./document.pdf --json

   # With explicit notebook
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source add "https://..." --notebook NOTEBOOK_ID --json
   ```

4. **Parse response**: Extract `source_id` and `status` from JSON output:
   ```json
   {"source_id": "def456...", "title": "Example", "status": "processing"}
   ```

5. **Wait for processing** (unless `--no-wait`):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source wait SOURCE_ID
   ```
   This blocks until the source is fully indexed and ready for queries.

6. **Report**: Tell the user the source was added, its ID, title, and whether processing is complete.

## Example Usage

```
/notebooklm-enhanced:add-source https://arxiv.org/pdf/2301.00001.pdf
/notebooklm-enhanced:add-source https://www.youtube.com/watch?v=dQw4w9WgXcQ
/notebooklm-enhanced:add-source ./my-research-paper.pdf
/notebooklm-enhanced:add-source https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture) --no-wait
```

## Supported Source Types

| Type | Examples |
|------|----------|
| Web URL | Any `https://` page, PDF link, arXiv paper |
| YouTube | `youtube.com/watch?v=...`, `youtu.be/...` |
| Local file | `.pdf`, `.txt`, `.md`, `.docx`, and other document formats |

## Notes

- Source limits vary by plan: Standard (50), Plus (100), Pro (300), Ultra (600) sources per notebook.
- Processing time varies: web pages take seconds, large PDFs and videos take longer.
- If processing appears stuck, check with `uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source list --json`.
