---
description: Ask questions to NotebookLM about your notebook sources — supports citations, follow-ups, and source filtering
allowed-tools: Bash
---

# Query NotebookLM

Ask a question against notebook sources and get an AI-generated answer with citations.

## Arguments

Parse from: `$ARGUMENTS`

Required:
- Question text (the main argument)

Options:
- `--notebook <id>`: Target a specific notebook (otherwise uses active notebook)
- `--source <id>`: Limit query to specific source(s) — can be repeated
- `--follow-up` or `-c <conversation_id>`: Continue an existing conversation
- `--save`: Save the answer as a note in the notebook

## Workflow

1. **Parse arguments**: Extract the question, optional notebook ID, source IDs, and conversation ID.

2. **Verify context** (if no `--notebook` specified):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm status
   ```
   Ensure there is an active notebook. If not, suggest running `/notebooklm-enhanced:library` first.

3. **Run the query**:
   ```bash
   # Basic query
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "YOUR QUESTION HERE" --json

   # With specific sources
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "YOUR QUESTION" -s SOURCE_ID_1 -s SOURCE_ID_2 --json

   # Follow-up in existing conversation
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "FOLLOW UP QUESTION" -c CONVERSATION_ID --json

   # With explicit notebook
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ask "YOUR QUESTION" --notebook NOTEBOOK_ID --json
   ```

4. **Parse JSON response**: The output contains:
   ```json
   {
     "answer": "The answer text with [1] [2] citation markers...",
     "conversation_id": "...",
     "turn_number": 1,
     "is_follow_up": false,
     "references": [
       {"source_id": "...", "citation_number": 1, "cited_text": "..."},
       {"source_id": "...", "citation_number": 2, "cited_text": "..."}
     ]
   }
   ```

5. **Format output**: Present the answer with properly formatted citations. For each reference, show the citation number and the relevant quoted text.

6. **Report conversation ID**: Always include the `conversation_id` so the user can run follow-up queries with `-c`.

## Example Usage

```
/notebooklm-enhanced:query What are the main findings of this paper?
/notebooklm-enhanced:query --notebook abc123 What methods were used?
/notebooklm-enhanced:query --source def456 Summarize this source
/notebooklm-enhanced:query -c conv789 Can you elaborate on point 3?
```

## Notes

- Use `--json` flag on all `ask` commands to get structured output with citations.
- The `conversation_id` enables multi-turn conversations — always surface it to the user.
- If no sources exist in the notebook, the query will fail. Suggest adding sources first.
