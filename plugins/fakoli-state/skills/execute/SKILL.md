---
name: execute
description: "Execute a claimed Fakoli State work packet, verify its acceptance criteria and submit concrete evidence for review."
---

# Execute

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Confirm an active claim and its actor, worktree, scope and expiry. Generate `packet TASK_ID`, then read the returned file; regeneration overwrites the previous packet. `packet TASK_ID --format json` is available for structured consumers.
2. Implement the packet's acceptance criteria. Coordinate overlapping files, preserve other work, and renew the claim before expiry. Use only agent tools and specialist roles exposed in the current host.
3. Run the packet's verification commands and record their actual exits and useful output. Collect changed files from git and any available hook evidence. Hook coverage differs by host; never invent hook-recorded evidence.
4. Run `submit --help`, then submit TASK_ID with the supported evidence flags: `--commands`, `--files-changed`, `--output-file`, optional `--commit-sha`/`--pr-url`/`--screenshots`, and honest `--known-limitations`. Use the CLI's documented value formats. Submission releases the claim and enters review; it is not acceptance.
5. Read `show TASK_ID` to confirm recorded evidence and disposition. Continue to finish when review is in scope.

A passing test is evidence for what it exercised, not proof that an external deployment or API worked. Do not fabricate outputs, silently weaken acceptance criteria, or edit the database directly.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
