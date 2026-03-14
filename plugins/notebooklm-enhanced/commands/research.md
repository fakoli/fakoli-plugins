---
description: Run an end-to-end research workflow — create notebook, find sources via web research, wait for indexing, query, and generate a report
allowed-tools: Bash
---

# NotebookLM Research Workflow

Run a multi-step research workflow: create a notebook, add web-researched sources, query the content, and generate a report.

## Arguments

Parse from: `$ARGUMENTS`

Required:
- Research topic (the main argument)

Options:
- `--notebook <id>`: Use an existing notebook instead of creating a new one
- `--mode <fast|deep>`: Research depth (default: `deep`)
- `--output <type>`: Final artifact type to generate (default: `report`). Options: `report`, `audio`, `slide-deck`, `quiz`, `flashcards`
- `--download <path>`: Download the final artifact to this path
- `--sources-only`: Only add research sources, skip query and generation
- `--report-format <fmt>`: Report format: `briefing-doc`, `study-guide`, `blog-post` (default: `briefing-doc`)

## Workflow

1. **Create or select notebook**:
   ```bash
   # Create new notebook for the research topic
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm create "Research: TOPIC" --json

   # Set as active
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm use NOTEBOOK_ID
   ```
   Or if `--notebook` was provided, use that existing notebook.

2. **Add web research sources**:
   ```bash
   # Deep research (recommended for thorough analysis)
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source add-research "RESEARCH TOPIC" --mode deep --no-wait

   # Fast research (for quick overviews)
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source add-research "RESEARCH TOPIC"
   ```

3. **Wait for research and import**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm research wait --import-all
   ```
   This waits for all research results to be found and imported as notebook sources.

4. **Verify sources were added**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source list --json
   ```
   If `--sources-only` was specified, stop here and report the sources.

5. **Synthesize with a query**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "Provide a comprehensive analysis of TOPIC. Cover key findings, different perspectives, and implications." --json
   ```

6. **Generate output artifact**:
   ```bash
   # Report (default)
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate report --format briefing-doc --json

   # Or other artifact types based on --output flag
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate audio --json
   ```

7. **Wait for artifact** (if async):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm artifact wait TASK_ID
   ```

8. **Download** (if `--download` specified):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm download report ./research-output.md
   ```

9. **Report**: Provide a summary including:
   - Notebook ID and title
   - Number of research sources found and imported
   - Key findings from the synthesis query
   - Artifact status and download location (if applicable)

## Example Usage

```
/notebooklm-enhanced:research quantum computing applications in drug discovery
/notebooklm-enhanced:research "climate change mitigation strategies" --mode fast
/notebooklm-enhanced:research transformer architectures --output slide-deck --download ./slides.pdf
/notebooklm-enhanced:research "CRISPR gene editing ethics" --sources-only
/notebooklm-enhanced:research "renewable energy 2025" --report-format study-guide --download ./study.md
```

## Timing Expectations

| Step | Estimated Time |
|------|---------------|
| Create notebook | 1-2 seconds |
| Web research (fast) | 30s-2 min |
| Web research (deep) | 15-30+ min |
| Source indexing | 30s-10 min |
| Query synthesis | 5-15 seconds |
| Report generation | 5-15 min |
| Audio generation | 10-20 min |

## Notes

- Deep research mode finds more diverse sources but takes longer.
- The `research wait --import-all` command automatically imports discovered sources into the notebook.
- For more control, use individual commands: `/notebooklm-enhanced:create-notebook`, `/notebooklm-enhanced:add-source`, `/notebooklm-enhanced:query`, `/notebooklm-enhanced:generate`.
