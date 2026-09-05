---
description: Generate NotebookLM artifacts — podcasts, videos, slide decks, quizzes, reports, mind maps, flashcards, infographics, and data tables
allowed-tools: Bash
---

# Generate

Read `skills/notebooklm-core/SKILL.md` for workflow boundaries, authentication, and explicit notebook selection. Parse the user’s request from `$ARGUMENTS`.

Run the locked CLI through `bash "${CLAUDE_PLUGIN_ROOT}/scripts/notebooklm.sh" ...`; resolve inputs/outputs against the user’s workspace, not the plugin directory.

Resolve the requested notebook and artifact type. Inspect `generate TYPE --help`, select user-requested options and source IDs, and submit once with `--notebook` and JSON output. Track the returned artifact/task ID with bounded status checks (no more than 60 seconds per blocking wait). Download only when requested, using the exact completed artifact ID and explicit output path. Verify the file before linking it. An uncertain submission requires readback before retry, and unknown/failed status is not completion.
