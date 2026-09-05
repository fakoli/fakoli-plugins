---
description: Create a new NotebookLM notebook and optionally add initial sources
allowed-tools: Bash
---

# Create Notebook

Read `skills/notebooklm-core/SKILL.md` for workflow boundaries, authentication, and explicit notebook selection. Parse the user’s request from `$ARGUMENTS`.

Run the locked CLI through `bash "${CLAUDE_PLUGIN_ROOT}/scripts/notebooklm.sh" ...`; resolve inputs/outputs against the user’s workspace, not the plugin directory.

Create the requested notebook using `create "TITLE" --json`. Parse its full ID and return it. Add sources only if requested, targeting the returned ID explicitly. Creating a notebook does not require changing shared current-notebook context.
