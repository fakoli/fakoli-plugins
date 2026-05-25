---
name: claim
description: Acquire an exclusive lease on a fakoli-state task — pick from the ready queue, check for file conflicts, claim the task, and get a working git branch to commit into. Use this skill when ready to start work on an approved task.
---

# Claim — Acquire an Exclusive Lease

Turn a `ready` task into an active claim: a row in `state.db` with a 60-minute lease, a branch checked out, and hooks watching every file touch. This is the entry point to the agentic execution loop. Nothing moves to `claimed` without going through here.

---

## When to Use

- Starting work on a task after `/fakoli-state:plan` has produced a ready queue.
- When `fakoli-flow:execute` dispatches an agent against a fakoli-state task — the claim step happens inside that dispatch.
- When `fakoli-crew:welder` picks up integration work, or `fakoli-crew:scout` picks up a research task — both land here before touching files.
- When resuming after an interrupted session — check `fakoli-state status` first, then re-claim if the previous lease has expired and the task returned to `ready`.
- When coordinating parallel agents — each agent claims a separate task; `claim` enforces the conflict gate.

**Do not use this skill to inspect the queue without taking work** — use `/fakoli-state:state-ops` for that. Do not use this skill to submit completed work — that is the Phase 5 `finish` skill.

---

## Prerequisites

`.fakoli-state/state.db` must exist and the PRD must be in `reviewed` or `approved` status. Confirm before proceeding:

```bash
fakoli-state status
```

Look for `prd-status: approved`. The claim gate enforces this — `fakoli-state claim` raises `ClaimError` when `prd-status` is `draft` or `none`. If the PRD is not approved, proceed to `/fakoli-state:prd` first.

Phase 4 commands used in this skill:

| Command | Phase | Status |
|---|---|---|
| `fakoli-state next` | Phase 4 | available |
| `fakoli-state claim TASK_ID` | Phase 4 | available |
| `fakoli-state release CLAIM_ID` | Phase 4 | available |
| `fakoli-state renew CLAIM_ID` | Phase 4 | available |
| `fakoli-state show TASK_ID` | Phase 3 | available |
| `fakoli-state list --status ready` | Phase 3 | available |

Git is optional. When a git repo is present in the project root, `claim` automatically creates the branch `agent/<task_id_lower>-<slug>`. Without git, claim still succeeds — the record is written to `state.db` and the branch field is left `null`.

---

## Workflow

### Step 1 — See what is claimable

```bash
fakoli-state next
```

Returns the single highest-priority `ready` task with no unmet dependencies and no conflict-group overlap with currently active claims. Priority ordering: `critical` > `high` > `medium` > `low`; ties broken by complexity ascending (simpler first), then `created_at` ascending (oldest first).

To see the full ready queue instead of just the top pick:

```bash
fakoli-state list --status ready
```

If `next` returns nothing, the queue is empty, fully claimed, or PRD-gated. Run:

```bash
fakoli-state status
```

Read `prd-status`, `ready-tasks`, and `active-claims` to identify the blocker. A non-zero `ready-tasks` count alongside a non-`approved` `prd-status` means the PRD gate is blocking all claims — the ready count is accurate, but the gate is closed.

---

### Step 2 — Inspect the task before claiming

```bash
fakoli-state show TASK_ID
```

Example:

```bash
fakoli-state show T012
```

Returns: title, intent, acceptance criteria, verification commands, all six score dimensions (`complexity`, `parallelizability`, `context_load`, `blast_radius`, `review_risk`, `agent_suitability`), `expected_files`, dependency chain, and any active claim on this task.

Before claiming, confirm:

- The acceptance criteria are concrete and independently verifiable — not aspirational descriptions.
- `complexity` is 3 or under. A score of 4 or 5 means the task should have been expanded via `fakoli-state expand` during planning. Claiming an oversized task and then abandoning it mid-way wastes the lease window.
- `agent_suitability` matches the current executor. A score of 1 or 2 signals that the task requires architectural judgment, significant human context, or decisions that a model is likely to get wrong. Defer those tasks.
- `expected_files` does not include files that look like they belong to a different subsystem — a sign the task scope drifted during authoring.

This step costs nothing and prevents the most common source of wasted claims.

---

### Step 3 — Check for conflicts

The `claim` command performs a conflict check before writing anything. Run claim with the task ID to trigger that check:

```bash
fakoli-state claim T012
```

The manager checks two conflict conditions before issuing the lease:

1. **File overlap** — another active claim by a different actor has at least one file in common with `expected_files` of T012.
2. **Conflict group** — T012 belongs to a `conflict_group` that already has an active claim on a sibling task.

If either condition is true and `--force` is not passed, `claim` raises `ClaimError` and prints the overlapping claim ID, the other actor's identity, and the overlapping files. Example:

```
ClaimError: Task 'T012' conflicts with active claims: claim C003 by agent-scout
(files: ['src/fakoli_state/state/backend.py']). Use --force to override.
```

If the conflict is acceptable — for example, the other actor owns C003 on a read-only research task and T012 writes to a different function in the same file — re-run with `--force`:

```bash
fakoli-state claim T012 --force
```

The override is logged as a warning in `events.jsonl` with the actor identity, the claim being forced, and the overlapping files. Every forced claim is auditable.

---

### Step 4 — Acquire the lease

A clean claim (no conflicts, or `--force` accepted) prints the claim result:

```
Claimed T012: add-retry-backoff
Claim ID:     C004
Branch:       agent/t012-add-retry-backoff
Lease:        60 min (expires 2026-05-24T19:00:00Z)
```

The task transitions from `ready` to `claimed` in `state.db`. Two events are appended to `events.jsonl`: `claim.created` and `task.status_changed`.

To also create a git worktree checked out to the branch (useful when running two agents in parallel from the same repo without checkout conflicts):

```bash
fakoli-state claim T012 --worktree
```

This creates `../wt-t012/` with the branch already checked out. Each worktree is fully independent — no stashing required when switching between tasks.

Without a git repo present, `claim` still succeeds and prints:

```
Warning: not a git repository — no branch created (record-only mode).
```

The claim is valid. Work proceeds in the repo root. The branch field on the Claim row is left `null`.

---

### Step 5 — Work on the branch

Actual code changes happen here, outside the skill. Commit incrementally to `agent/t012-add-retry-backoff` (or to the worktree branch). Incremental commits make the eventual PR reviewable and give a recovery point if the agent is interrupted.

Two hooks are active during this phase:

**`check-claim.sh`** (PreToolUse on Edit, Write, NotebookEdit) — warns when the file being modified is not in `expected_files` for any active claim. Non-blocking: the edit proceeds regardless.

**`record-file-change.sh`** (PostToolUse on Edit, Write, NotebookEdit) — appends a `file_changed` event to `events.jsonl` for every file touched. This populates the audit trail that Phase 5's `submit` command reads.

Both hooks run automatically. No manual action required.

---

### Step 6 — Heartbeat the lease

The default lease is 60 minutes. For sessions longer than 55 minutes, renew before the lease expires:

```bash
fakoli-state renew C004
```

Renewing extends `lease_expires_at` by another 60 minutes from now and updates `last_heartbeat_at`. The command errors if the lease is already expired — re-claiming is the only option at that point.

```
Renewed C004: lease extended to 2026-05-24T20:05:00Z
```

Automated agents should renew every 5 minutes. A missed heartbeat does not immediately lose the claim — the lease detector runs on the next CLI or MCP operation. Once the lease expires, the task returns to `ready` and any agent can claim it.

Only the owning actor can renew a claim. To release another actor's stale claim, use `release --force`.

---

### Step 7 — Submit when complete (Phase 5)

Phase 5 introduces `fakoli-state submit TASK_ID`, which auto-releases the claim and transitions the task to `needs_review`. Until Phase 5 lands, the workflow ends at "claimed + branch ready":

1. Complete the work on the branch.
2. Merge or open a PR manually.
3. Release the claim explicitly:

```bash
fakoli-state release C004
```

Release emits `claim.released` and transitions the task from `claimed` back to `ready` (pending a status change to `done` which Phase 5 will handle).

---

### Step 8 — Release explicitly when abandoning

When work must stop before completion — blocked on an upstream issue, deprioritized, or handed off — release the claim so the task returns to the pool:

```bash
fakoli-state release C004 --reason "blocked: upstream T009 not merged"
```

The `--reason` string is stored in `release_reason` on the Claim row and logged in `events.jsonl`. Another agent can then pick up the task via `fakoli-state next`.

To release a claim held by a different actor (use sparingly — logged in audit trail):

```bash
fakoli-state release C004 --force
```

`--force` bypasses the actor-ownership check and also allows releasing claims in non-`active` states (e.g., `stale`). Every forced release is recorded with the releasing actor's identity.

---

## Common Pitfalls

- **Claiming while PRD is still `draft`.** The claim gate checks `prd-status` and raises `ClaimError` before touching anything else. Run `fakoli-state prd review --approve` first.
- **Ignoring the `agent_suitability` score.** Claiming a task scored `1` or `2` with a small or local model burns 60 minutes and produces output that needs complete rework. Check `fakoli-state show TASK_ID` before committing.
- **Skipping the heartbeat on long sessions.** Leases expire silently. The task returns to `ready` and another agent can claim it while work is still in progress. Set a timer and run `fakoli-state renew CLAIM_ID` every 5 minutes.
- **Editing `state.db` directly with sqlite3 to fix a stuck claim.** Use `fakoli-state release --force` instead. Direct edits bypass `events.jsonl` and produce state that cannot be replayed or audited.
- **Calling `renew` after the lease has already expired.** `renew` raises `ClaimError` on an expired lease — the lease cannot be extended retroactively. Re-claim the task after it returns to `ready`.

---

## Composition with Other Skills

| Position | Skill |
|---|---|
| Before this skill | `/fakoli-state:plan` must have produced `ready` tasks; optionally `/fakoli-state:state-ops` to read the queue first |
| After claiming | Work the branch, heartbeat, complete; then Phase 5 `finish` for submit + ship |
| If `show TASK_ID` reveals `complexity >= 4` | Return to `/fakoli-state:plan` and expand the task before claiming |
| If `next` returns nothing | `/fakoli-state:state-ops` to diagnose — check `status`, `list --status drafted`, trace blockers |

**When `fakoli-flow` is installed:** `flow:execute` detects fakoli-state and wraps this skill. It reads `fakoli-state next`, calls `fakoli-state claim`, and dispatches the agent against the claimed task. The claim still appears in `state.db` — it is the same primitive, called from inside the flow.

**When `fakoli-crew` is installed:** `welder` is the standard claim consumer for integration work. `scout` claims research tasks. Pass `--actor` to tag the claim with the crew role for traceability:

```bash
fakoli-state claim T012 --actor fakoli-crew:welder
```

The `claimed_by` field on the Claim row records the actor string. The audit trail links every file change to the role that made it.

---

## Phase 4 Limitations

`submit` and `apply` ship in Phase 5. Until then, the claim lifecycle ends at `release` — no automated transition to `done`.

| Feature | Phase | Status |
|---|---|---|
| `fakoli-state next` | Phase 4 | available |
| `fakoli-state claim TASK_ID` | Phase 4 | available |
| `fakoli-state claim TASK_ID --worktree` | Phase 4 | available |
| `fakoli-state release CLAIM_ID` | Phase 4 | available |
| `fakoli-state renew CLAIM_ID` | Phase 4 | available |
| `check-claim.sh` hook (PreToolUse) | Phase 4 | available |
| `record-file-change.sh` hook (PostToolUse) | Phase 4 | available |
| `fakoli-state submit TASK_ID` (auto-release + needs_review) | Phase 5 | pending |
| `fakoli-state apply TASK_ID` (evidence review + done) | Phase 5 | pending |
| `fakoli-state conflicts` (full conflict map across all active claims) | Phase 5 | pending |
| Per-file scope check refinement in `check-claim.sh` | Phase 5 | pending — current hook warns on any active claim, not per-claim file scope |
| PR creation / commit assistance | Out of scope | fakoli-state coordinates work; it does not write code |
