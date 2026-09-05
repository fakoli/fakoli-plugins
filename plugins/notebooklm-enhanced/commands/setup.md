---
description: Authenticate and verify NotebookLM CLI setup — run login, check status, and list notebooks
allowed-tools: Bash
---

# Setup

Read `skills/notebooklm-core/SKILL.md` for workflow boundaries, authentication, and explicit notebook selection. Parse the user’s request from `$ARGUMENTS`.

Run the locked CLI through `bash "${CLAUDE_PLUGIN_ROOT}/scripts/notebooklm.sh" ...`; resolve inputs/outputs against the user’s workspace, not the plugin directory.

Use `--version` and `auth check --json` to inspect readiness. For `--check`, report the result and exit before login or other mutation. For requested initial setup or `--reauth`, run `login` and let the user complete browser sign-in; inspect `login --help` for browser requirements. Verify with auth check and a minimal notebook list. `status` only reports local context, not authentication. Never expose authentication cookies or inline auth JSON.
