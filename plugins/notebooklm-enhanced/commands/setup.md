---
description: Authenticate and verify NotebookLM CLI setup — run login, check status, and list notebooks
allowed-tools: Bash
---

# NotebookLM Setup

Authenticate with Google and verify the NotebookLM CLI is ready.

## Arguments

Parse from: `$ARGUMENTS`

Options:
- `--reauth`: Force re-authentication even if already logged in
- `--check`: Only check current status without logging in

## Workflow

1. **Check CLI availability**: Verify `notebooklm` is accessible via uv:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm --help
   ```
   If this fails, tell the user to install `notebooklm-py` (e.g., `uv pip install notebooklm-py`).

2. **Check current status** (skip login if already authenticated and no `--reauth`):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm status
   ```
   If output shows "Authenticated as: ...", the user is already logged in. Proceed to step 4 unless `--reauth` was specified.

3. **Authenticate** (first-time or re-auth):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm login
   ```
   This opens a browser for Google OAuth. Wait for the user to complete sign-in.

4. **Verify authentication**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm status
   ```
   Confirm the output shows a valid authenticated session.

5. **List notebooks** to confirm full access:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm list
   ```

6. **Report**: Tell the user their authentication status, email, and how many notebooks they have.

## Example Usage

```
/notebooklm-enhanced:setup
/notebooklm-enhanced:setup --reauth
/notebooklm-enhanced:setup --check
```

## Troubleshooting

- If `notebooklm login` hangs, ensure a browser is available. In headless environments, set `NOTEBOOKLM_AUTH_JSON` instead.
- If authentication succeeds but `notebooklm list` fails, run `uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm auth check --test` for diagnostics.
- For re-authentication: `uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm login` (overwrites existing session).
