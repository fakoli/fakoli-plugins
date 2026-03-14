---
description: Create a new NotebookLM notebook and optionally add initial sources
allowed-tools: Bash
---

# Create NotebookLM Notebook

Create a new notebook and set it as the active context.

## Arguments

Parse from: `$ARGUMENTS`

Required:
- Notebook title (the main argument)

Options:
- `--source <url_or_path>`: Add source(s) immediately after creation — can be repeated
- `--no-activate`: Create the notebook but don't set it as active

## Workflow

1. **Create the notebook**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm create "NOTEBOOK TITLE" --json
   ```

2. **Parse response**: Extract the notebook `id`:
   ```json
   {"id": "abc123de-...", "title": "Research"}
   ```

3. **Set as active notebook** (unless `--no-activate`):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm use NOTEBOOK_ID
   ```

4. **Add initial sources** (if `--source` options provided):
   For each source, run:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source add "SOURCE_URL_OR_PATH" --json
   ```
   Then wait for all sources to finish processing:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source wait SOURCE_ID
   ```

5. **Report**: Tell the user the notebook ID, title, active status, and any added sources.

## Example Usage

```
/notebooklm-enhanced:create-notebook "Machine Learning Research"
/notebooklm-enhanced:create-notebook "Climate Change" --source https://example.com/paper.pdf
/notebooklm-enhanced:create-notebook "Study Notes" --source ./chapter1.pdf --source ./chapter2.pdf
```

## Notes

- Notebook titles don't need to be unique but should be descriptive.
- After creation, the notebook is empty until sources are added.
- Use `/notebooklm-enhanced:add-source` to add more sources later.
- Use `/notebooklm-enhanced:library` to see all notebooks.
