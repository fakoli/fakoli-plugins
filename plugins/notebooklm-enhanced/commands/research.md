---
description: Run an end-to-end research workflow — create notebook, find sources via web research, wait for indexing, query, and generate a report
allowed-tools: Bash
---

# Research

Read `skills/notebooklm-core/SKILL.md` for workflow boundaries, authentication, and explicit notebook selection. Parse the user’s request from `$ARGUMENTS`.

Run the locked CLI through `bash "${CLAUDE_PLUGIN_ROOT}/scripts/notebooklm.sh" ...`; resolve inputs/outputs against the user’s workspace, not the plugin directory.

Use `notebooklm-research` for the requested source research or comparison. Query selected existing notebooks using full IDs. Create a notebook, import research results, generate a report, or download artifacts only when those steps are part of the accepted request. Attribute findings to notebook/source references, preserve contradictions, and report pending or failed work.
