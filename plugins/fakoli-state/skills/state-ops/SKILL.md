---
name: state-ops
description: "Inspect the Fakoli State project summary, task details, ready queue, active claims and local reconciliation when orienting or diagnosing blocked work."
---

# State Ops

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Resolve the project directory and verify `.fakoli-state/state.db` exists. If absent, report an uninitialized project; run `init` only when project setup is part of the request.
2. Run `fakoli-state status`, then use `list --status ready`, `list --status in_progress`, `show TASK_ID`, or `next` to answer the actual question. Use `--cwd PROJECT` when the shell is elsewhere. `next` selects work without claiming it.
3. Inspect task dependencies and claim scope before recommending work. For local filesystem/git discrepancies, run bare `fakoli-state sync` and read its report. `sync --fix` changes state; provider sync may write remote issues. Execute those only within the requested remediation scope.
4. Report concrete task IDs, claim/blocker evidence and the next available action. For machine summaries, use `status --hook-format`; do not parse the decorative human output.

The current CLI has no `conflicts` or `decision` top-level command. Use the actual exposed MCP conflict tool if available, or inspect `show`/claim scope and local sync output. Some inspection commands initialize storage or reap expired leases: do not describe them as byte-preserving reads. Never repair canonical state by editing SQLite directly.

See [GitHub sync](../../docs/github-sync.md) before any provider operation. A local status request does not authorize a remote push or a recurring watcher.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
