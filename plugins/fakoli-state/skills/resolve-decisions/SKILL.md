---
name: resolve-decisions
description: "Find and resolve meaningful open decisions in a Fakoli State PRD before they change planning or implementation."
---

# Resolve Decisions

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Read the current PRD and run `prd find-decisions` with its supported file/project arguments. Inspect each reported marker in context; do not treat every missing field as requiring a user question.
2. Apply answers already present in the brief, repository, or conversation. For a consequential unknown, present a concise decision with tradeoffs when the user is available. During an authorized autonomous run, use a justified assumption for reversible choices and record the rationale.
3. Update the relevant requirement/task and a Decisions section. Preserve unresolved markers for choices that cannot responsibly be inferred; do not label assumptions as user approvals.
4. Re-run decision detection, parse changed requirements when safe for current claims, and inspect the resulting state. Continue to planning when in scope, or report the exact unresolved decision that prevents it.

Use the host's available question and file tools. Do not assume `AskUserQuestion` exists, force a fixed options menu, or repeatedly ask whether to continue already-authorized work.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
