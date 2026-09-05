---
description: Ask questions to NotebookLM about your notebook sources — supports citations, follow-ups, and source filtering
allowed-tools: Bash
---

# Query

Read `skills/notebooklm-core/SKILL.md` for workflow boundaries, authentication, and explicit notebook selection. Parse the user’s request from `$ARGUMENTS`.

Run the locked CLI through `bash "${CLAUDE_PLUGIN_ROOT}/scripts/notebooklm.sh" ...`; resolve inputs/outputs against the user’s workspace, not the plugin directory.

Resolve the requested notebook ID and run `ask "QUESTION" --notebook "$NOTEBOOK_ID" --json`. Verify the locked CLI help for source filters and continuation flags. Do not use `--new` unless deletion of existing conversation history was explicitly requested. Return the answer with actual source citations. Save as a note only when requested; preserve the conversation ID for continuation.
