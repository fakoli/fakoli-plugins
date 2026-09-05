---
name: prd
description: "Author, parse and review a Fakoli State PRD when turning agreed requirements into project state."
---

# Prd

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Inspect existing `.fakoli-state/prd.md`, state and active claims. Use [the PRD template](../../docs/prd-template.md) for required structure. Preserve authored requirements; clarify only missing decisions that materially affect the task.
2. Edit the draft with concrete goals, non-goals, requirements, tasks, acceptance criteria, file scope and verification commands. Do not silently replace requirements under an active claim.
3. Parse with `prd parse` (or the supported `--file PATH`), inspect the resulting counts, and run `prd find-decisions`. Resolve meaningful open items through the resolve-decisions workflow.
4. Run `prd review`. Record approval with `prd review --approve --reviewer REVIEWER` only when the project's required reviewer has made that decision, including an explicit decision already in the conversation.
5. Verify status and continue into planning when in scope. The current CLI provides `prd parse`, `prd review`, and `prd find-decisions`; `start-prd` is a skill workflow, not a CLI subcommand.

Keep the event log authoritative; use supported CLI operations for mutations. A model-generated draft is still a draft until the review gate is satisfied.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
