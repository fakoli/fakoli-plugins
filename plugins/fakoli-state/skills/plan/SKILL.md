---
name: plan
description: Turn a reviewed PRD into a ready-to-execute task graph — generate features and tasks, score each on six dimensions, surface dependencies and conflict groups, promote drafted tasks to ready. Use this skill once the PRD is approved and before any agent claims work.
---

# Plan — PRD to Ready Task Graph

Convert an approved PRD into a queue of agent-ready tasks. This skill drives four sequential state transitions: PRD requirements → features and tasks → scored tasks → reviewed-and-ready tasks. Once the queue contains at least one `ready` task, agents can claim work.

---

## When to Use

- Immediately after `fakoli-state prd review --approve` — the PRD is approved and the task graph does not yet exist.
- After a significant PRD revision that adds new `## Features` or `## Tasks` sections — re-plan to generate the updated task graph.
- When `fakoli-state status` shows `prd-status: approved` but `ready-tasks: 0` and no tasks exist yet.
- When tasks exist but none have scores — scoring was skipped or the plan was never completed.

**Do not use this skill for re-scoring individual tasks, managing claims, or adjusting task status after work has started.** Once tasks are `ready`, proceed to `/fakoli-state:execute` (Phase 5). Use `/fakoli-state:state-ops` for inspection at any point.

---

## Prerequisites

The PRD must be parsed and in at least `reviewed` status. Confirm before proceeding:

```bash
fakoli-state status
```

Look for `prd-status: reviewed` or `prd-status: approved`. If `prd-status: draft` or `prd-status: none`, proceed to `/fakoli-state:prd` first.

Phase 3 commands used in this skill:

| Command | Phase | Status |
|---|---|---|
| `fakoli-state plan` | Phase 3 | available |
| `fakoli-state score [TASK_ID]` | Phase 3 | available |
| `fakoli-state expand TASK_ID` | Phase 7 (pending; scaffolded) | limited |
| `fakoli-state review tasks` | Phase 3 | available |
| `fakoli-state list [--status X]` | Phase 3 | available |
| `fakoli-state show TASK_ID` | Phase 3 | available |

---

## Workflow

### Step 1 — Generate features and tasks

```bash
fakoli-state plan
```

Reads the parsed PRD from `state.db` and emits `feature.created` and `task.created` events for each `Feature` and `Task` found. Dependency inference and conflict-group detection run automatically — tasks that share `likely_files` entries are grouped into the same conflict group.

The command prints the generated count. Verify it matches the PRD:

```
generated 3 features, 8 tasks
```

If the counts are wrong, check that the PRD was re-parsed after the last edit. A stale parse will produce a stale task graph. Run `fakoli-state prd parse` and then re-run `fakoli-state plan`.

**Pause here before continuing.** When running this skill with a human, present the task list:

```bash
fakoli-state list
```

Let the human review titles, features, and priorities before proceeding. Catching mis-scoped tasks now costs one loop; catching them after scoring or claiming costs three.

---

### Step 2 — Score every task

```bash
fakoli-state score
```

Populates all six dimensions on each `Task`. The scorer is rule-based — no LLM required. Dimensions:

| Dimension | Scale | What it measures |
|---|---|---|
| `complexity` | 1–5 | Estimated implementation effort |
| `parallelizability` | 1–5 | How independently this task can run from others |
| `context_load` | 1–5 | How much context an agent needs to hold while working |
| `blast_radius` | 1–5 | How much of the codebase a mistake here could damage |
| `review_risk` | 1–5 | How carefully a human reviewer needs to inspect the output |
| `agent_suitability` | 1–5 | How well-suited a typical frontier model is to this task |

After scoring, run:

```bash
fakoli-state list
```

The output includes `agent_suitability` for each task. Surface anything that needs attention before proceeding:

- **`complexity >= 4`**: flag for expand (Step 3). These tasks are too large for a single agent session.
- **`agent_suitability <= 2`**: flag for human attention. Low suitability means the task involves judgment calls, ambiguous requirements, or architecturally broad changes that a model is likely to get wrong.
- **`blast_radius >= 4`**: flag for careful claim ordering. High blast-radius tasks touch foundational code and should not run in parallel with other tasks that share files.

Present these findings to the human before moving to Step 3. Do not silently continue if multiple high-complexity tasks appear — this is the moment to decide whether to expand them.

---

### Step 3 — Expand oversized tasks

For each task with `complexity >= 4`, run:

```bash
fakoli-state expand TASK_ID
```

**Phase 7 limitation:** in Phase 3, `expand` scaffolds the subtask structure but refuses to auto-generate subtask content without `--use-llm`. Running `fakoli-state expand T001` will return an error similar to:

```
Error: LLM augmentation required for expand. Re-run with --use-llm once Phase 7 ships.
```

**Phase 3 workaround:** author the subtasks manually in `prd.md`. Add `### T001.1:` and `### T001.2:` blocks under `## Tasks` with their own `**Acceptance criteria:**` and `**Verification:**` fields. Re-parse, then re-plan:

```bash
# 1. Edit prd.md to add T001.1 and T001.2 subtask blocks
$EDITOR .fakoli-state/prd.md

# 2. Re-parse
fakoli-state prd parse

# 3. Re-run plan to generate the subtask entities
fakoli-state plan

# 4. Re-run score to populate dimensions on the new tasks
fakoli-state score
```

The parent task `T001` can be dropped from `prd.md` once its subtasks are defined — or left as a logical grouping if the parser supports it. Confirm with guido's parser behavior before removing parent task blocks.

---

### Step 4 — Review tasks to promote them

```bash
fakoli-state review tasks
```

Promotes tasks through `drafted → reviewed → ready`. The gate checks two conditions for each task:

1. `acceptance_criteria` is non-empty.
2. `verification.commands` is non-empty (at least one shell command).

Tasks that pass both conditions are promoted to `ready`. Tasks that fail the gate stay at `drafted` with a failure reason printed. For example:

```
T004: BLOCKED — verification.commands is empty
T005: PROMOTED to ready
T006: PROMOTED to ready
```

For each blocked task, return to `prd.md`, add the missing field, re-parse, and re-run `review tasks`. Do not retry without fixing the underlying gap — the gate will block on the same condition again.

---

### Step 5 — Verify the ready queue

```bash
fakoli-state list --status ready
```

This is the queue agents can now claim. If it is empty after Step 4 succeeded, something blocked the gate. Check what is stuck:

```bash
fakoli-state list --status drafted
```

Every task still in `drafted` missed the gate. Read the failure reason in the Step 4 output and fix each one.

If the `ready` list looks correct, the plan is complete. Proceed to `/fakoli-state:execute` (Phase 5).

---

### Step 6 — Drill into specific tasks

```bash
fakoli-state show TASK_ID
```

Example:

```bash
fakoli-state show T003
```

Returns the full task detail: title, description, acceptance criteria, verification commands, all six score dimensions, `expected_files`, and dependency chain.

Run `show` on any task that looks suspicious — a title that seems too broad, a `blast_radius` of 5 on something that should be isolated, or a dependency chain that creates a bottleneck. These are planning issues that are far cheaper to fix before claiming than after.

---

## Co-Authoring Guidance

When running this skill with a human, do not chain all steps in a single shot on the first run. Pause and present findings at each step:

**After Step 1 (`plan`):** Show the task list. Ask whether the titles and feature groupings match intent. A missing feature or a mis-titled task caught here avoids re-planning later.

**After Step 2 (`score`):** Surface every task where `agent_suitability <= 2` and every task where `complexity >= 4`. Present them explicitly:

> Three tasks have `complexity >= 4` and need to be split before they can be claimed:
> T001: Implement storage backend (complexity: 5)
> T003: Wire authentication middleware (complexity: 4)
> T007: Migrate existing data (complexity: 4)
>
> Two tasks have `agent_suitability = 2` and may benefit from human review before claiming:
> T002: Define API contract (low suitability — architectural judgment required)

**After Step 4 (`review tasks`):** If any tasks are blocked, surface the exact missing field — do not just report "blocked". The human needs to know what to add.

---

## Common Pitfalls

- **Planning against an unreviewed PRD.** The `claim_task` gate enforces `prd-status: approved` — but planning against a `draft` PRD produces a task graph that will be replaced on the next parse. Wait for approval before running `plan`.
- **Running `plan` twice without re-parsing.** A second `plan` invocation on unmodified state will either re-emit duplicate events or error with a conflict. If the PRD has changed, re-parse first. If nothing has changed, skip `plan`.
- **Treating scores as fixed truth.** The scoring engine uses rule-based heuristics against task fields. A task with a one-word description will score misleadingly. If a score seems wrong (e.g., `blast_radius: 1` on a task that clearly touches a shared schema file), adjust the `**Likely files:**` field in `prd.md`, re-parse, and re-score.
- **Manually editing `state.db`.** Do not use `sqlite3` directly. Every mutation must flow through the CLI so the change is recorded in `events.jsonl`. Manual edits produce state that cannot be replayed or audited.
- **Skipping the pause after `plan`.** Jumping straight to `score` and `review tasks` without reviewing the task list means catching structural problems only after the queue is ready. A task graph that doesn't reflect real work is worse than no task graph.

---

## Composition with Other Skills

| Position | Skill |
|---|---|
| Before this skill | `/fakoli-state:prd` — PRD must be at least `reviewed` |
| After Step 1 (plan) | `/fakoli-state:state-ops` — inspect the raw task graph before scoring |
| After Step 5 (ready queue confirmed) | `/fakoli-state:execute` (Phase 5) — agents can now claim and work tasks |
| If `show TASK_ID` reveals `complexity >= 4` | Expand in Step 3, then re-run `score` and `review tasks` |

---

## Phase 3 Limitations

| Feature | Phase | Status |
|---|---|---|
| `fakoli-state plan` | Phase 3 | available |
| `fakoli-state score` | Phase 3 | available |
| `fakoli-state review tasks` | Phase 3 | available |
| `fakoli-state list` | Phase 3 | available |
| `fakoli-state show TASK_ID` | Phase 3 | available |
| `fakoli-state expand TASK_ID` (auto-generate subtasks) | Phase 7 | pending — use manual prd.md workaround |
| `fakoli-state score --use-llm` (LLM-augmented scoring) | Phase 7 | pending — rule-based scoring is default |
| `fakoli-state next` (pick highest-priority claimable task) | Phase 4 | pending — use `list --status ready` instead |
| Planner agent (`agents/planner.md`) | Phase 3 | available — dispatched by plan when needed |
