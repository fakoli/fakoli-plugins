---
description: Browse and manage your NotebookLM library — list notebooks, sources, artifacts, and set active notebook
allowed-tools: Bash
---

# Library

Read `skills/notebooklm-core/SKILL.md` for workflow boundaries, authentication, and explicit notebook selection. Parse the user’s request from `$ARGUMENTS`.

Run the locked CLI through `bash "${CLAUDE_PLUGIN_ROOT}/scripts/notebooklm.sh" ...`; resolve inputs/outputs against the user’s workspace, not the plugin directory.

List notebooks with `list --json` and present the fields actually returned. To inspect a selected notebook, pass its full ID to source/artifact list operations. Do not switch the global current notebook unless the user explicitly asks to change that preference.
