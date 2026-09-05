---
name: claim
description: "Acquire, renew or release a Fakoli State task lease when beginning work or recovering an interrupted claim."
---

# Claim

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Inspect `status`, `next` and `show TASK_ID`. Check approved PRD status, ready task status, dependencies, acceptance criteria and overlapping file scope.
2. Run `claim TASK_ID --actor ACTOR` (add `--worktree` when isolated git work is appropriate). Read the returned claim ID, branch/worktree and lease expiry. Task IDs and claim IDs are different identifiers.
3. Work only within the claimed scope. Renew with `renew CLAIM_ID --actor ACTOR` before the reported lease expires; use the host's supported scheduling or execution loop rather than promising an unstarted background timer.
4. For completed work, use the execute skill to submit evidence. To relinquish unfinished work, run `release CLAIM_ID --actor ACTOR --reason REASON`.

Never steal another live claim with `--force` merely to unblock yourself. Coordinate shared files through the available agent mechanism; do not assume any named crew agent exists. Expired claims cannot be renewed retroactively: inspect current state and reacquire ownership before resuming.

CLI `--help` is authoritative for lease and actor flags. Hooks are supplementary: check their actual availability before relying on automatic file tracking.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
