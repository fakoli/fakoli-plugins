---
name: notebooklm-research
description: Compare and synthesize grounded answers across explicitly selected NotebookLM notebooks, or conduct requested NotebookLM source research with attributable results.
---

# NotebookLM research

Read [core operation rules](../notebooklm-core/SKILL.md) for installed paths, account readiness, explicit notebook IDs, completion checks, and authorization. Use the lock-backed wrapper, not a global executable from an unrelated environment.

For existing-notebook synthesis:

1. List notebooks as JSON and choose the notebooks relevant to the requested topic.
2. Query each full notebook ID explicitly, for example `bash "$PLUGIN_ROOT/scripts/notebooklm.sh" ask "QUESTION" --notebook "$NOTEBOOK_ID" --json`. Do not use `ask --new` for routine comparison: the locked CLI deletes existing server-side conversation history with this flag. Note prior conversation context as a limitation, or continue the specifically requested conversation. Never switch global context with `use`.
3. Retain each answer's notebook ID, conversation ID, source references, and cited passages. Distinguish source-supported conclusions from the model's synthesis; source-grounded answers can still be incomplete or wrong.
4. Compare agreements, contradictions, and gaps. Attribute findings to the relevant notebook/source. Do not imply that an empty or failed response means a source contains no evidence.

For requested new source research, create/select the intended notebook, submit research to that explicit notebook, track the returned research ID, and import only the requested results after completion. Check `source add-research --help` and `research --help` for the locked CLI's exact flags. Wait/poll in bounded intervals without resubmitting the same operation. Uploading local files, generating artifacts, and creating reports are separate steps only when requested or needed by the accepted outcome.

Delegate independent notebook queries only when delegation is available and authorized. Each worker uses explicit IDs and must return citations and failures. A generic research request does not authorize an unattended create/source/generate/download pipeline.
