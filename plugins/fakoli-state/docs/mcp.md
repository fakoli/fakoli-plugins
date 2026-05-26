# fakoli-state MCP server

## What it does

Agents need to read and write canonical project state without each one shelling out to the
CLI per operation and without fighting over the same SQLite rows. The MCP server exposes 13
tools over stdio so that any MCP-compatible runtime — Claude Code, Codex, Cursor, OpenHands,
Copilot, or a local script — can claim tasks, check conflicts, submit evidence, and inspect
the dependency graph as first-class tool calls. Read-only tools return structured Pydantic
objects; mutating tools run stale-claim reaping before writing, so the state the agent sees
is always fresh.

---

## Installation

The server is wired automatically once the plugin is installed. No manual configuration is
required. The plugin ships a `.mcp.json` at its root that Claude Code reads on session start:

```json
{
  "mcpServers": {
    "fakoli-state": {
      "type": "stdio",
      "command": "bash",
      "args": ["${CLAUDE_PLUGIN_ROOT}/bin/fakoli-state-mcp"]
    }
  }
}
```

`${CLAUDE_PLUGIN_ROOT}` is the absolute path to the installed plugin directory. The wrapper
`bin/fakoli-state-mcp` calls `uv sync` if `uv.lock` or `pyproject.toml` is newer than the
virtual environment (covering cold starts and `git pull` updates), then delegates to
`python -m fakoli_state.mcp_server`.

Each tool call opens a fresh `SqliteBackend` against `.fakoli-state/state.db` resolved from
the agent's current working directory at call time. Agents can invoke from any project
directory — the server re-resolves state on every call.

**Prerequisite**: `fakoli-state init` must have been run in the project root before any tool
call will succeed.

---

## Tool reference

Tools are grouped below by access pattern: read-only tools first, mutating tools second.

### Read-only tools

---

### `get_project_summary`

Returns a snapshot of overall project health: task counts by status, active claim count,
blocked task count, and ready task count. Stale-claim reaping runs before the read, so
counts reflect freshly expired leases.

**Inputs**

None.

**Output**

```json
{
  "project_id": "string",
  "project_name": "string",
  "project_description": "string",
  "prd_status": "string | null",
  "task_counts": {
    "proposed": 0,
    "drafted": 0,
    "reviewed": 0,
    "ready": 0,
    "claimed": 0,
    "in_progress": 0,
    "blocked": 0,
    "needs_review": 0,
    "accepted": 0,
    "done": 0,
    "rejected": 0
  },
  "active_claim_count": 0,
  "blocked_task_count": 0,
  "ready_task_count": 0
}
```

`prd_status` is `null` when no PRD has been parsed yet.

**Failure modes**

- `ToolError` — project not initialized (`.fakoli-state/` missing).
- `ToolError` — project row not found in state.db (run `fakoli-state init`).

**When to call**: at session start or before orchestrating a wave, to decide how many agents
to spawn and whether the queue is draining or stacking up.

---

### `list_tasks`

Returns tasks filtered by status, feature, or claiming actor. All three filters are optional
and combinable. `status` and `feature_id` are pushed to SQL; `claimed_by` is an in-memory
filter joined against active claims.

**Inputs**

| Parameter    | Type            | Required | Default |
|--------------|-----------------|----------|---------|
| `status`     | `string \| null` | no       | `null`  |
| `feature_id` | `string \| null` | no       | `null`  |
| `claimed_by` | `string \| null` | no       | `null`  |

Valid `status` values: `proposed`, `drafted`, `reviewed`, `ready`, `claimed`,
`in_progress`, `blocked`, `needs_review`, `accepted`, `done`, `rejected`.

**Output**

A JSON array of Task objects serialized from their Pydantic models. Each element includes
full task fields: `id`, `title`, `status`, `priority`, `feature_id`, `dependencies`,
`conflict_groups`, `expected_files`, `scores`, and all other Task model fields.

**Failure modes**

- `ToolError` — state directory not found.

**When to call**: when a coordinator agent needs to see all `ready` tasks before deciding
which ones to dispatch in a wave.

---

### `get_task`

Returns the full Task object for a single task ID.

**Inputs**

| Parameter | Type     | Required |
|-----------|----------|----------|
| `task_id` | `string` | yes      |

**Output**

A single Task object serialized to JSON (same shape as one element from `list_tasks`).

**Failure modes**

- `ToolError` — task not found: `"Task '{task_id}' not found."`.
- `ToolError` — state directory not found.

**When to call**: after `get_next_task` returns a candidate, to read the full acceptance
criteria and constraints before calling `claim_task`.

---

### `get_next_task`

Returns the single highest-priority `ready` task that has no active claim and no unsatisfied
dependencies. Sort key (from `ClaimManager.next_claimable()`): `priority desc` (`critical` >
`high` > `medium` > `low`), then `complexity asc` (lower score wins; unscored tasks rank
last), then `created_at asc` (oldest first for fairness). Returns `null` when no claimable
task is available.

Stale-claim reaping runs before the selection, so expired leases are cleared before the
candidate set is computed. Tasks in active conflict groups (where a conflicting task is
already claimed) are excluded.

**Inputs**

| Parameter | Type            | Required | Default |
|-----------|-----------------|----------|---------|
| `actor`   | `string \| null` | no       | `null`  |

`actor` is accepted but not used in the selection logic in the current implementation;
it is reserved for future suitability filtering.

**Output**

A Task object serialized to JSON, or `null`.

**Failure modes**

- `ToolError` — state directory not found.

**When to call**: the standard first step for any agent entering the work loop — call
`get_next_task`, then `claim_task` on the returned ID.

---

### `generate_work_packet`

Renders a work packet for a task in markdown or JSON format. The packet includes task intent,
acceptance criteria, constraints, non-goals, open dependencies, and the active claim if one
exists. Delegates to `fakoli_state.context.packets.render_packet`.

**Inputs**

| Parameter | Type                       | Required | Default      |
|-----------|----------------------------|----------|--------------|
| `task_id` | `string`                   | yes      |              |
| `format`  | `"markdown" \| "json"`     | no       | `"markdown"` |

**Output**

```json
{
  "format": "markdown",
  "content": "# T012 — Implement auth middleware\n..."
}
```

`content` is a `string` when `format` is `"markdown"` and a `dict` when `format` is
`"json"`.

**Failure modes**

- `ToolError` — task not found.
- `ToolError` — state directory not found.

**When to call**: immediately after `claim_task` succeeds, to get the structured prompt
the agent will work against.

---

### `check_conflicts`

Cross-references a list of proposed file paths against the `expected_files` of all currently
active claims, excluding the task's own claim. Returns one conflict entry per overlapping
file per claim.

**Inputs**

| Parameter        | Type           | Required |
|------------------|----------------|----------|
| `task_id`        | `string`       | yes      |
| `proposed_files` | `list[string]` | yes      |

**Output**

```json
{
  "conflicts": [
    {
      "file": "src/auth/middleware.py",
      "claim_id": "C001",
      "claimed_by": "agent-welder-1",
      "task_id": "T008"
    }
  ]
}
```

An empty `conflicts` list means no overlaps were detected.

**Failure modes**

- `ToolError` — state directory not found.

**When to call**: before declaring `expected_files` in a `claim_task` call, to surface
potential write conflicts before work begins rather than discovering them at merge time.

---

### `get_dependency_graph`

Returns nodes, directed edges, and the `ready_to_claim` set for a given scope. Edges run
from dependency to dependent (`from → to`). `ready_to_claim` lists task IDs that are in
`ready` status, have all dependencies in `done` status, and have no active claim.

**Inputs**

| Parameter   | Type                             | Required | Default  |
|-------------|----------------------------------|----------|----------|
| `scope`     | `"all" \| "feature" \| "task"`   | no       | `"all"`  |
| `target_id` | `string \| null`                 | no       | `null`   |

`target_id` is required when `scope` is `"feature"` or `"task"`. When `scope` is `"task"`,
the graph covers the target task and all its transitive dependencies.

**Output**

```json
{
  "nodes": [
    {
      "id": "T001",
      "title": "Scaffold auth module",
      "status": "done",
      "priority": "high",
      "feature_id": "F001"
    }
  ],
  "edges": [
    { "from": "T001", "to": "T002" }
  ],
  "ready_to_claim": ["T002", "T003"]
}
```

**Failure modes**

- `ToolError` — `target_id` is `null` when `scope` is `"feature"` or `"task"`.
- `ToolError` — state directory not found.

**When to call**: when a planner agent needs to decide which tasks are unblocked and safe
to dispatch in parallel this wave.

---

### Mutating tools

Every mutating tool runs `detect_and_release_stale` at the top of its call. This is
automatic — agents do not need to trigger reaping manually. See
[Stale-claim reaping](#stale-claim-reaping) for details.

---

### `claim_task`

Acquires an exclusive lease on a task for the given actor. Delegates to
`ClaimManager.claim`, which writes the `Claim` row in an atomic SQLite transaction.
Stale-claim reaping runs first.

**Gate**: the PRD must not be in `draft` status. If the PRD is `draft` or missing, the tool
raises a `ToolError` and no claim is created.

**Inputs**

| Parameter                | Type                    | Required | Default |
|--------------------------|-------------------------|----------|---------|
| `task_id`                | `string`                | yes      |         |
| `claimed_by`             | `string`                | yes      |         |
| `expected_files`         | `list[string] \| null`  | no       | `[]`    |
| `lease_duration_seconds` | `int`                   | no       | `900`   |

`lease_duration_seconds` is converted to minutes (floor, minimum 1) before being passed
to `ClaimManager`. The default 900 seconds gives a 15-minute MCP-side override — note that
the CLI's `ClaimManager` ships with a 60-minute default (see
[`bin/src/fakoli_state/claims/manager.py`](../bin/src/fakoli_state/claims/manager.py)
line 118), and the project-level override is read from `.fakoli-state/config.yaml`.

**Output**

```json
{
  "id": "C001",
  "task_id": "T012",
  "claimed_by": "agent-welder-1",
  "lease_expires_at": "2026-05-25T14:15:00+00:00",
  "branch": "agent/t012-implement-auth",
  "worktree_path": null,
  "expected_files": ["src/auth/middleware.py", "tests/test_auth.py"]
}
```

`branch` and `worktree_path` are `null` when git ops are not configured.

**Failure modes**

- `ToolError` — PRD is `draft` or missing.
- `ToolError` — `ClaimError` from `ClaimManager` (task already claimed, task not in claimable state, etc.).
- `ToolError` — state directory not found.

**When to call**: after `get_next_task` or `get_task` confirms the task is ready and
the agent has checked conflicts.

---

### `release_task`

Releases the active claim on a task held by `actor`. The claim is located by task ID; the
actor string does not need to match (the lookup finds the active claim regardless of who
holds it). Stale-claim reaping runs first.

**Inputs**

| Parameter | Type            | Required | Default |
|-----------|-----------------|----------|---------|
| `task_id` | `string`        | yes      |         |
| `actor`   | `string`        | yes      |         |
| `reason`  | `string \| null` | no      | `null`  |

**Output**

```json
{
  "released": true,
  "claim_id": "C001"
}
```

**Failure modes**

- `ToolError` — no active claim found for the task.
- `ToolError` — `ClaimError` from `ClaimManager`.
- `ToolError` — state directory not found.

**When to call**: when an agent determines it cannot complete a task and wants to return it
to the `ready` pool for another agent to pick up.

---

### `renew_claim`

Extends the lease on an active claim. Use this as a heartbeat during long-running work to
prevent the claim from going stale. Stale-claim reaping runs first, so the claim must still
be active at the point of the call.

**Inputs**

| Parameter        | Type     | Required | Default |
|------------------|----------|----------|---------|
| `task_id`        | `string` | yes      |         |
| `actor`          | `string` | yes      |         |
| `extend_seconds` | `int`    | no       | `900`   |

`extend_seconds` is converted to minutes (floor, minimum 1). The default extends by 15
minutes from the time of the call.

**Output**

```json
{
  "lease_expires_at": "2026-05-25T14:30:00+00:00"
}
```

**Failure modes**

- `ToolError` — no active claim found (claim may have already gone stale).
- `ToolError` — `ClaimError` from `ClaimManager`.
- `ToolError` — state directory not found.

**When to call**: every ~5 minutes while actively working on a claimed task (recommended
in the execute skill). Missing a renewal window causes the claim to go stale and the task
to re-enter the `ready` pool.

---

### `submit_progress`

Records an in-progress note for a task without changing its status. Writes a
`progress.noted` event to the JSONL audit log. Does not require an active claim.

**Inputs**

| Parameter | Type     | Required |
|-----------|----------|----------|
| `task_id` | `string` | yes      |
| `actor`   | `string` | yes      |
| `notes`   | `string` | yes      |

**Output**

```json
{
  "recorded": true
}
```

**Failure modes**

- `ToolError` — task not found.
- `ToolError` — state directory not found.

**When to call**: to emit a mid-task checkpoint visible in the event log — for example,
after completing one sub-step of a multi-step task, so the audit trail reflects partial
progress.

---

### `submit_completion_evidence`

Submits completion evidence for a task. Requires an active claim. Emits an
`evidence.submitted` event that auto-releases the claim and transitions the task to
`needs_review`. Mirrors `fakoli-state submit` from the CLI.

**Inputs**

| Parameter        | Type                    | Required | Default |
|------------------|-------------------------|----------|---------|
| `task_id`        | `string`                | yes      |         |
| `actor`          | `string`                | yes      |         |
| `commands_run`   | `list[string]`          | yes      |         |
| `files_changed`  | `list[string]`          | yes      |         |
| `output_excerpt` | `string \| null`        | no       | `null`  |
| `pr_url`         | `string \| null`        | no       | `null`  |
| `commit_sha`     | `string \| null`        | no       | `null`  |

**Output**

```json
{
  "evidence_id": "EV3A9F1C2D",
  "task_status": "needs_review"
}
```

`evidence_id` is an `"EV"` prefix followed by 8 uppercase hex characters, generated at
call time.

**Failure modes**

- `ToolError` — task not found.
- `ToolError` — no active claim found for the task (claim the task before submitting).
- `ToolError` — `TransactionAborted` from the backend.
- `ToolError` — state directory not found.

**When to call**: when the agent's work is complete and it is ready to hand off to review.
This is the last step in the execute loop before the agent exits.

---

### `update_task_status`

Transitions a task to a new status. Only the following transitions are permitted:

| From           | To allowed        |
|----------------|-------------------|
| `drafted`      | `ready`           |
| `ready`        | `drafted`         |
| `in_progress`  | `blocked`         |
| `claimed`      | `blocked`         |
| `blocked`      | `in_progress`     |

Any other transition raises a `ToolError` with the current status and the allowed targets.
Stale-claim reaping runs first.

**Inputs**

| Parameter   | Type                               | Required | Default |
|-------------|------------------------------------|----------|---------|
| `task_id`   | `string`                           | yes      |         |
| `to_status` | `"drafted" \| "ready" \| "blocked" \| "in_progress"` | yes      |         |
| `actor`     | `string`                           | yes      |         |
| `reason`    | `string \| null`                   | no       | `null`  |

**Output**

```json
{
  "from_status": "drafted",
  "to_status": "ready"
}
```

**Failure modes**

- `ToolError` — task not found.
- `ToolError` — transition not allowed (message includes current status and valid targets).
- `ToolError` — `TransactionAborted` from the backend.
- `ToolError` — state directory not found.

**When to call**: when a planner agent marks reviewed tasks as `ready` before a work wave,
or when a sentinel marks an `in_progress` task as `blocked` after discovering a dependency
that cannot be resolved yet.

---

## Error model

Every failure raises a FastMCP `ToolError`. The message is a human-readable string
describing what failed, what was expected, and what the agent should do next. There is no
outer envelope — `ToolError` is surfaced directly to the MCP client.

Example error message from `claim_task` when the PRD gate fires:

```
Cannot claim task 'T012': PRD is in 'draft' status. The PRD must be reviewed or approved
before tasks can be claimed.
```

Example error message from `update_task_status` when the transition is invalid:

```
Cannot transition task 'T012' from 'done' to 'ready'. Allowed targets from 'done': none.
This tool supports only: drafted↔ready and blocked toggle.
```

The spec describes a structured `{code, message, target_id, payload}` envelope for future
versions; the current implementation uses the `ToolError` string directly. Agents should
treat any `ToolError` as a terminal condition for the current operation and log the message
before deciding whether to retry, release, or escalate.

---

## Integration with fakoli-crew and fakoli-flow

**fakoli-crew agents** gain access to all 13 MCP tools when fakoli-state is installed
alongside fakoli-crew. The standard work loop for a crew agent (welder, smith, guido) is:

1. `get_next_task` — find the highest-priority claimable task.
2. `check_conflicts` — verify proposed files do not overlap active claims.
3. `claim_task` — acquire the lease.
4. `generate_work_packet` — render the structured prompt.
5. Do the work; call `renew_claim` every ~5 minutes.
6. `submit_progress` for mid-task checkpoints (optional).
7. `submit_completion_evidence` — release the claim and move the task to `needs_review`.

The sentinel agent uses `get_project_summary` and `list_tasks` (filtered by
`status="needs_review"`) to find tasks awaiting verification, then calls
`update_task_status` to set a task `blocked` if evidence is insufficient.

**fakoli-flow skills** use the MCP tools when fakoli-state is present:

- `flow:execute` reads `get_next_task` and calls `claim_task` before dispatching each
  wave, replacing the markdown-status-file convention.
- `flow:verify` filters on `needs_review` tasks via `list_tasks` before dispatching the
  sentinel.
- `flow:finish` uses `update_task_status` to drive accepted tasks toward `done` before
  the merge or PR decision.

When fakoli-state is absent, fakoli-flow and fakoli-crew continue to operate via their
existing markdown-status conventions. Integration is strictly opt-in.

See [`specs/2026-05-24-fakoli-state-v0.md`](specs/2026-05-24-fakoli-state-v0.md) for the
full integration contract.

---

## Stale-claim reaping

Every mutating tool (`claim_task`, `release_task`, `renew_claim`, `submit_progress`,
`submit_completion_evidence`, `update_task_status`) and `get_project_summary` call
`detect_and_release_stale` before performing their operation. This is automatic — agents do
not need to trigger reaping manually.

Reaping scans all active claims, identifies those whose `lease_expires_at` timestamp has
passed, marks them stale, and returns the associated tasks to the `ready` pool. If the
reaper itself throws an exception, the error is swallowed and the main operation proceeds
(best-effort, never blocking).

The practical consequence: an agent that calls `get_next_task` will never receive a task
whose claim expired seconds ago — the expired claim is cleared in the same call before the
candidate set is built.

---

## See also

- [`specs/2026-05-24-fakoli-state-v0.md`](specs/2026-05-24-fakoli-state-v0.md) — canonical
  design spec: data model, task lifecycle, phasing plan, integration contracts.
- `hooks.md` — claim discipline hooks: `check-claim.sh`, `record-file-change.sh`,
  `capture-evidence.sh`, `detect-state.sh`. (Landing in Phase 6 documentation pass.)
- `integration-flow-crew.md` — detailed integration contract between fakoli-state,
  fakoli-flow, and fakoli-crew. (Planned.)
