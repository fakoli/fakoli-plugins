---
description: Browse and manage your NotebookLM library — list notebooks, sources, artifacts, and set active notebook
allowed-tools: Bash
---

# NotebookLM Library

Browse your NotebookLM library: notebooks, sources, and artifacts.

## Arguments

Parse from: `$ARGUMENTS`

Options:
- `--use <id>`: Set a notebook as active
- `--sources`: Show sources for the active notebook
- `--artifacts`: Show artifacts for the active notebook
- `--all`: Show notebooks, sources, and artifacts together

If no options given, show all notebooks and the current active notebook context.

## Workflow

1. **Show current context**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm status
   ```

2. **List all notebooks**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm list --json
   ```
   Format the output as a table showing notebook ID (first 8 chars), title, and source count.

3. **Set active notebook** (if `--use` specified):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm use NOTEBOOK_ID
   ```

4. **List sources** (if `--sources` or `--all`):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source list --json
   ```

5. **List artifacts** (if `--artifacts` or `--all`):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm artifact list --json
   ```

6. **Report**: Present a clear summary of the library contents. Indicate which notebook is currently active.

## Example Usage

```
/notebooklm-enhanced:library
/notebooklm-enhanced:library --use abc123
/notebooklm-enhanced:library --sources
/notebooklm-enhanced:library --artifacts
/notebooklm-enhanced:library --all
```

## Notes

- The active notebook is stored in `~/.notebooklm/context.json` and persists between commands.
- Use partial IDs (first 6+ characters) for convenience — they must be unambiguous.
- Notebooks are listed in reverse chronological order (newest first).
