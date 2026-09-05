---
description: Add a source to a NotebookLM notebook — supports URLs, local files, and YouTube links
allowed-tools: Bash
---

# Add Source

Read `skills/notebooklm-core/SKILL.md` for workflow boundaries, authentication, and explicit notebook selection. Parse the user’s request from `$ARGUMENTS`.

Run the locked CLI through `bash "${CLAUDE_PLUGIN_ROOT}/scripts/notebooklm.sh" ...`; resolve inputs/outputs against the user’s workspace, not the plugin directory.

Resolve the notebook and the exact requested source URL/file. A local file will be uploaded to Google; it must be within the requested scope. Use `source add --help` to construct the request with an explicit notebook ID, then parse the returned source ID and check processing to completion in bounded intervals. Report failed/incomplete sources rather than treating submission as successful ingestion.
