---
name: notebooklm-core
description: Operate Google NotebookLM notebooks, sources, grounded queries, and generated artifacts through the bundled notebooklm-py CLI when the user chooses NotebookLM.
---

# NotebookLM operations

This plugin uses the **unofficial** `notebooklm-py` CLI and Google's undocumented RPCs. Resolve `PLUGIN_ROOT` from this installed skill (`../..`), then use `bash "$PLUGIN_ROOT/scripts/notebooklm.sh" ...`. The wrapper selects the bundled lockfile; it does not change the user's project directory or notebook context. See [README](../../README.md) for prerequisites and authentication.

Check `--version` and the relevant command's `--help` before an unfamiliar operation. For account readiness use `auth check --json`, then a needed read such as `list --json`. `status` reports local context and is not an authentication test. A sign-in is interactive; the user completes it. Never print cookie storage or `NOTEBOOKLM_AUTH_JSON`.

List notebooks and select a full returned ID. Pass `--notebook "$NOTEBOOK_ID"` on notebook-scoped operations; confirm flag placement with subcommand help. Do not use the shared `notebooklm use` context in automated or parallel workflows. When continuing a query, pass the returned conversation ID explicitly. In the locked CLI, `ask --new` deletes the notebook's server-side conversation; `--json` also bypasses its confirmation. Do not use `--new` merely to obtain an independent answer—use it only when that history deletion is explicitly requested.

Run only operations implied or explicitly authorized by the user's request. A query/synthesis does not imply creating notebooks, adding/uploading sources, changing global language, generating paid/quota-consuming artifacts, sharing, or deleting data. Existing authorization remains valid; do not ask again for ordinary steps within it. Use generation-specific `--language` instead of altering global preferences.

Creation/submission is not completion. Parse returned notebook/source/task/artifact IDs from actual JSON. Poll the specific ID with bounded status/wait calls (at most 60 seconds per blocking call; `artifact wait ID --timeout 60 --interval 5 --notebook ID`, or research status with `--run-id`; research wait with `--import-all` can consume two timeout budgets), preserve progress, and report failed/unknown/incomplete states accurately. After an uncertain submission, inspect existing source/artifact state before resubmitting. Rate limits, authentication failures, and RPC protocol changes require different remedies; do not classify every RPC error as rate limiting.

Download the requested artifact ID to an explicit output path only when it reports ready, verify the resulting file, and return a usable link. Do not overwrite an unrelated output or download an arbitrary latest artifact. Google-side operations can fail or change; no operation is guaranteed to always work.

Use [notebooklm-research](../notebooklm-research/SKILL.md) for cross-notebook comparisons. The CLI reference and maintained upstream limitations are linked in the README; avoid maintaining a copied matrix of changing options here.
