---
name: finish
description: "Review a Fakoli State evidence bundle and record the authorized accept or reject decision for a submitted task."
---

# Finish

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Inspect `show TASK_ID` and the submitted evidence. Confirm the task is awaiting review, acceptance criteria are met, verification is relevant, and limitations are explicit.
2. Perform the required review using the current host's tools. Independent review can use an available agent; do not invoke a nonexistent named agent or require a Claude CLI probe under Codex.
3. Respect the project's human review policy. Use an explicit review decision already supplied in the conversation; do not manufacture a reviewer identity or treat technical completion alone as approval. If that decision is required and missing, leave the review pending with the exact evidence the reviewer needs.
4. Record the decision with `apply TASK_ID --approve --reviewer REVIEWER` or `apply TASK_ID --reject --reason REASON --reviewer REVIEWER`, then verify the resulting status with `show`.
5. Run merge, publication or provider-sync steps only when those actions are in the user's authorized scope. `apply` itself does not deploy or create a pull request.

Do not use `--force` or direct database edits to bypass the evidence/review gates. Distinguish rejected work from a blocked test environment in the report.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
