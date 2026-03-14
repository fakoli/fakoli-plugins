---
name: notebooklm-research
description: Multi-notebook research synthesis — activates when user needs cross-notebook research, comparative analysis, or deep research workflows combining multiple NotebookLM notebooks
---

# NotebookLM Research Skill

Multi-notebook research synthesis: query across notebooks, compare findings, and produce unified analyses.

## When This Skill Activates

**Explicit triggers:**
- "compare across notebooks"
- "research synthesis"
- "cross-reference my notebooks"
- "deep research on..."
- "multi-notebook analysis"

**Intent detection:**
- "What do my different notebooks say about X?"
- "Compare the findings in notebook A vs notebook B"
- "Synthesize everything I have on this topic"
- "Run a deep research workflow on..."
- "Create a comprehensive research report combining..."

## Prerequisites

- Authenticated with NotebookLM (`/notebooklm-enhanced:setup`)
- At least one notebook with sources (for cross-notebook), or a topic (for new research)

## CLI Prefix

All commands use:
```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ...
```

## Workflows

### Cross-Notebook Research

When the user wants to compare or synthesize across existing notebooks:

1. **List all notebooks**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm list --json
   ```

2. **Identify relevant notebooks** based on the user's topic. Look at titles and source counts.

3. **Query each notebook** individually:
   ```bash
   # Set context to each notebook and query
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm use NOTEBOOK_ID_1
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "RESEARCH QUESTION" --json

   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm use NOTEBOOK_ID_2
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "RESEARCH QUESTION" --json
   ```

4. **Synthesize findings**: Combine answers from all notebooks, noting which notebook each finding came from. Identify:
   - Common themes across notebooks
   - Contradictions or different perspectives
   - Gaps in coverage
   - Unique insights from each notebook

5. **Present the synthesis** in a structured format with attribution to source notebooks.

### Deep Research on a New Topic

When the user wants comprehensive research on a topic they haven't explored yet:

1. **Create a dedicated research notebook**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm create "Research: TOPIC" --json
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm use NOTEBOOK_ID
   ```

2. **Add web research sources**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm source add-research "TOPIC" --mode deep --no-wait
   ```

3. **Wait for research completion**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm research wait --import-all
   ```

4. **Run synthesis queries**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "Comprehensive overview of TOPIC" --json
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "What are the key debates and open questions?" --json
   ```

5. **Generate a report artifact**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate report --format briefing-doc --json
   ```

6. **Present findings** to the user with key takeaways.

### Delegate to Research Agent

For fully autonomous execution of complex research workflows, delegate to the research agent:

> Use the Task tool to launch the `research-agent` with the user's research request. The agent handles the full pipeline (create, source, wait, query, generate, download) without user intervention.

## Output Format

Present research results with:
- **Executive Summary**: 2-3 sentence overview
- **Key Findings**: Numbered list of main insights, attributed to source notebooks
- **Cross-References**: Where multiple notebooks agree or disagree
- **Gaps**: Areas needing further investigation
- **Artifacts**: Links to any generated reports, audio, or other outputs

## Related Commands

- `/notebooklm-enhanced:research` — Single-step research workflow
- `/notebooklm-enhanced:query` — Query a single notebook
- `/notebooklm-enhanced:library` — Browse all notebooks
- `/notebooklm-enhanced:generate` — Generate artifacts from a notebook
