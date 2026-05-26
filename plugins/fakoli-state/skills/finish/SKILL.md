---
name: finish
description: Decide what to do with a fakoli-state task that has submitted evidence and is awaiting human review — accept and ship, reject and reopen, or hold for further investigation. Use this skill when one or more tasks are in needs_review and need a final disposition.
---

# Finish — Review Evidence and Ship

Drive the final leg of the task lifecycle: read the evidence, pick a disposition, call `apply`, and hand off to the project's git workflow for merging. Nothing moves from `needs_review` to `done` (or back to `drafted`) without going through here. This skill covers the solo and human-reviewer path; `fakoli-flow:finish` wraps it with wave-level batch apply and automated PR creation.

---

## When to Use

- Tasks appear in `fakoli-state list --status needs_review`.
- Before merging a PR that contains fakoli-state-tracked work — confirm the task has been applied first.
- At end-of-day or end-of-iteration when deciding what to ship versus what to reopen.

**Do not use this skill to execute work or submit evidence** — that is `/fakoli-state:execute`. Do not use it to inspect queue state without making a decision — use `/fakoli-state:state-ops` for read-only inspection.

---

## Prerequisites

One or more tasks in `needs_review`. Confirm before proceeding:

```bash
fakoli-state list --status needs_review
```

Each row shows `TaskID`, title, `claimed_by`, claim duration, and `files_changed` count. Phase 5 commands used in this skill:

| Command | Phase | Status |
|---|---|---|
| `fakoli-state list --status needs_review` | Phase 3 | available |
| `fakoli-state show TASK_ID` | Phase 3 | available |
| `fakoli-state apply TASK_ID --approve` | Phase 5 | available |
| `fakoli-state apply TASK_ID --reject --reason "..."` | Phase 5 | available |

---

## Workflow

### Step 1 — List what needs review

```bash
fakoli-state list --status needs_review
```

Read every row. Before proceeding to any individual task:

- Note tasks that have been in `needs_review` longer than expected — long dwell times may indicate evidence was submitted in a broken state or the reviewer window closed.
- Note whether multiple tasks in the list touch the same files — they may need to be applied in dependency order to avoid conflicts on merge.

When multiple tasks are ready, apply them in dependency order: tasks with no dependents first, then tasks whose dependencies are already `done`.

---

### Step 2 — Inspect each task's evidence

```bash
fakoli-state show TASK_ID
```

Example:

```bash
fakoli-state show T012
```

The output surfaces: `acceptance_criteria`, `evidence.commands_run` (with exit codes), `files_changed` (list), `output_excerpt` (first and last lines of captured output), and `pr_url` if one was linked at submit time.

Read all of it before invoking `apply`. The Review engine pre-checks `evidence_complete` against the task's `required_evidence` list; missing items are flagged in the `show` output:

```
Evidence status: INCOMPLETE
Missing:        pytest -x (no evidence captured)
```

An `INCOMPLETE` flag means the agent ran verification commands outside the hook window or the `capture-evidence.sh` hook did not fire. Do not apply an incomplete evidence row without understanding why — the gap may indicate the verification was never actually run.

For tasks where the evidence looks complete:

- Confirm every acceptance criterion has a corresponding command that exited 0.
- Confirm `files_changed` matches what the acceptance criteria required — a task that was supposed to modify `src/claims/manager.py` but shows only `tests/` in `files_changed` is suspicious.
- If a `pr_url` is linked, open the PR and scan the diff to spot anything the evidence summary missed.

---

### Step 3 — Pick a disposition

#### Accept and ship (the happy path)

All verification commands exited 0, evidence is complete, and the diff matches the acceptance criteria:

```bash
fakoli-state apply T012 --approve
```

This transitions the task `needs_review → accepted → done` and writes a `Review` row to `state.db` with the approver identity, timestamp, and disposition. A single `task.applied` event is appended to `events.jsonl` carrying the decision; the handler does the Review insertion and the status transition atomically in one transaction.

After `apply --approve`, merge the branch via the project's normal git workflow — fakoli-state does not auto-merge. See Step 4 for the ship sequence.

#### Reject and reopen

Evidence is incomplete, verification failed, or the implementation does not satisfy the acceptance criteria:

```bash
fakoli-state apply T012 --reject --reason "pytest -x reports 3 failures in test_retry.py"
```

`--reason` is required. The string is stored in the `Review` row and logged in `events.jsonl`. The task transitions `needs_review → rejected → drafted`.

From `drafted`, the task can be re-reviewed, re-scoped, and re-promoted via `fakoli-state review tasks`. The original branch and Evidence row are preserved in the audit log. After correcting the underlying issue (re-scoping the acceptance criteria, or letting the agent fix the failures), the task is re-claimable.

Do not reject without a concrete reason. "Not done" is not a reason. "pytest -x exits 1 — 3 failures in test_retry.py" is.

#### Hold for further investigation

Evidence is submitted but the reviewer needs more context before deciding:

- Do not invoke `apply` yet.
- Keep the task in `needs_review`.
- Capture the open questions in the task's `implementation_notes` field so the next reviewer has context. Until Phase 6 ships a `decision` CLI subcommand, add notes by re-editing the relevant section of `prd.md`, re-parsing, and coordinating with the next reviewer directly.

Loop back to Step 2 after gathering context.

#### Discard the work entirely

The task direction was wrong and the implementation should not be merged:

```bash
fakoli-state apply T012 --reject --reason "discarded — approach superseded by T015"
```

This transitions the task to `drafted`. Then delete the branch manually:

```bash
git branch -D agent/t012-add-retry-backoff
```

The audit log retains the `Evidence` row and rejection `Review` row for posterity. The task can be deprioritized, re-scoped, or removed from the PRD at the next planning cycle.

---

### Step 4 — Ship the merged work

For every task that received `--approve`:

1. Merge the `agent/<task>-<slug>` branch to the project's main branch:

```bash
git checkout main
git merge --no-ff agent/t012-add-retry-backoff -m "merge: T012 add-retry-backoff"
git push origin main
```

Or open a PR from the branch and merge via the project's PR workflow. Reference the fakoli-state task ID in the PR body for traceability:

```
Closes fakoli-state:T012 — add-retry-backoff
```

2. After merging, clean up the branch:

```bash
git branch -d agent/t012-add-retry-backoff
```

Branches accumulate. After a task is `done` and its branch is merged, delete it. `fakoli-state sync` (Phase 8) will flag undeleted agent branches as orphans.

fakoli-state does not auto-merge. The deliberate separation between `apply` (state transition) and `merge` (git operation) means the reviewer controls the merge strategy, PR template, and commit message — without the tool imposing a workflow.

---

### Step 5 — Sync to external tracker (optional)

Phase 8 ships bidirectional sync. If the project has a sync provider
configured (a `GITHUB_REPOSITORY` env var, a `gh auth` session, or any
contributor-registered provider in `PROVIDER_REGISTRY`) AND the task is
now at `status=done`, push the final state so the remote tracker
reflects the completion.

```bash
fakoli-state sync github --task T012
```

This runs a single-task push + pull pass through the GitHub Issues
provider. The closed-issue mapping (`done` → `status:done` label +
issue state `closed`) writes back to GitHub; any remote-side edits land
locally in the same pass. Failures (rate limit, deleted issue, auth
missing) surface on stderr and exit `1` without blocking the next task.

Run a health check first if this is the first sync of the session:

```bash
fakoli-state sync github --health
```

For other providers (Linear, Monday, Jira) use the generic form:

```bash
fakoli-state sync provider <provider_id> --task T012
```

See [`docs/github-sync.md`](../../docs/github-sync.md) for the full CLI
surface and conflict-resolution strategies.

**Otherwise** — no provider configured, no `GITHUB_REPOSITORY`, no `gh
auth` — skip this step. The local `state.db` + `events.jsonl` is the
canonical record; nothing else needs to happen. fakoli-state is fully
functional without any external sync.

---

## Co-authoring Guidance

When the human is the reviewer and an agent runs this skill:

- Surface the full evidence summary (Step 2 output) BEFORE invoking `apply`. Do not apply without explicit human confirmation.
- For the reject path, propose a concrete reason — surface the exact failure message from `evidence.commands_run`, not a vague "did not pass".
- For the hold path, write the open questions in plain language and confirm where they will be tracked before moving on.
- For the discard path, confirm with the human that the branch will be deleted. Deleting a branch is recoverable for a short window via `git reflog`; after the ref expires it is gone.

---

## Common Pitfalls

- **Applying without reading the evidence.** `evidence_complete` is a heuristic based on `required_evidence` fields — it checks presence, not correctness. The diff and the output excerpt are the ground truth. Read them.
- **Rejecting without a `--reason`.** The flag is required. A rejection without a reason leaves the next agent (or the next session of the same agent) without context for why the task failed review. Concrete reasons prevent duplicate mistakes.
- **Applying out of dependency order.** If T013 depends on T012, apply T012 first and merge it before applying T013. Applying in the wrong order creates a branch that cannot be cleanly merged until its dependency lands on main.
- **Forgetting to delete merged branches.** Agent branches accumulate. After merge, `git branch -d` the branch. Running `fakoli-state sync` (Phase 8) will report stale agent branches, but it is easier to clean up immediately.
- **Manually editing `state.db` to change a task status.** Use `fakoli-state apply` so the `Review` row and status transition are recorded in `events.jsonl`. Direct edits produce state that cannot be replayed or audited.

---

## Composition with Other Skills

| Position | Skill |
|---|---|
| Before this skill | `/fakoli-state:execute` — evidence must be submitted; task must be in `needs_review` |
| For read-only inspection before deciding | `/fakoli-state:state-ops` — inspect queue without making a disposition |
| After reject + redraft | `/fakoli-state:plan` — if the task needs re-scoping; `/fakoli-state:execute` — to re-claim and re-attempt |
| After accept + merge | The project's normal PR + deploy workflow; fakoli-state does not drive deployment |

**When `fakoli-flow:finish` is installed:** that skill wraps this one for wave-based batch completion. It drives `apply` for all completed tasks in a wave, then triggers automated PR creation via `gh pr create`. Solo and human-reviewer workflows use this skill directly. `fakoli-flow:finish` calls `fakoli-state apply` for each task the same way, but orchestrates the full wave before handing off to git.

**When `fakoli-crew` is installed:** the `sentinel` agent validates evidence before the reviewer reaches this skill. Detect availability explicitly rather than guessing:

```bash
claude plugin list 2>/dev/null | grep -q "fakoli-crew"
```

The grep pattern is intentionally unanchored. `claude plugin list` output renders each plugin row as `  ❯ fakoli-crew@fakoli-plugins` (indented marker, then `<plugin>@<source>` slug); a `^` anchor would never match. The unanchored substring is safe because `fakoli-crew` is a unique slug within the marketplace.

- **Exit code 0** (`fakoli-crew` present): dispatch the `fakoli-crew:sentinel` agent against the task's evidence bundle before invoking `fakoli-state apply`. `fakoli-flow:finish` does this dispatch automatically as part of its wave-completion flow; in solo mode, ask the parent Claude session to dispatch the agent and pass the task ID.
- **Non-zero exit** (`fakoli-crew` absent): fall through to the plugin-local `sentinel` agent if you are running under a Claude session that has access to it, otherwise rely on the reviewer's own reading of the evidence. Sentinel is an agent surface, not a skill — it must be dispatched via the agent mechanism, never via a slash command.

Sentinel produces a pass/fail recommendation that supplements (but does not replace) the reviewer's judgment. The `apply` call is always a human decision.

---

## Phase 5 Limitations

| Feature | Phase | Status |
|---|---|---|
| `fakoli-state apply TASK_ID --approve` | Phase 5 | available |
| `fakoli-state apply TASK_ID --reject --reason "..."` | Phase 5 | available |
| `fakoli-state list --status needs_review` | Phase 3 | available |
| `fakoli-state show TASK_ID` (with evidence) | Phase 5 | available |
| LLM-assisted disposition recommendation | Phase 7 | pending |
| GitHub Issues mirror (close issue when task done) | Phase 8 | pending |
| `fakoli-state decision` CLI subcommand | Phase 6 | pending |
| Automated PR creation on accept | Phase 8 | pending (use `gh pr create` manually) |
