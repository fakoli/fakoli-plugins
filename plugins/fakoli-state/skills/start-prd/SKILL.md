---
name: start-prd
description: "Bootstrap a Fakoli State PRD from an idea, notes or an existing brief when the project lacks a usable draft."
---

# Start Prd

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Inspect the target project and any existing PRD before writing. Reuse requirements and decisions already supplied. When an existing draft is present, revise it rather than replacing it wholesale.
2. Establish the problem, intended users, outcomes, non-goals, constraints and how success will be checked. Ask only consequential unanswered questions when the user is available; for an authorized autonomous run, record reasonable assumptions and unresolved decisions without waiting on cosmetic preferences.
3. Use [the PRD template](../../docs/prd-template.md), writing a reviewable draft to `.fakoli-state/prd.md`. Preserve previous content through version control or an explicit backup when doing a rewrite.
4. Review the draft against the supplied brief, surface remaining decisions, and continue into parse/review via the prd skill when those steps are authorized. Do not require the user to type commands the host can execute.

This skill uses the current assistant and needs no separate API key. Optional external model inference belongs to the CLI's configured provider workflow. Invoke another brainstorming skill only if it is available and helpful; its mere installation does not make it mandatory.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
