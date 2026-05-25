---
name: prd
description: Author, parse, and review a project PRD in fakoli-state — capture the requirements that everything downstream (features, tasks, claims, evidence) gets generated from. Use this skill when starting a new project or revising requirements before any planning work happens.
---

# PRD — Author, Parse, and Review Requirements

Write the contract that everything downstream depends on. The PRD is the single source of truth for every `Requirement`, `Feature`, and `Task` row in `state.db`. Nothing can be claimed until this document exists, parses cleanly, and clears the review gate.

---

## When to Use

- Starting a new project — before any planning, scoring, or task assignment happens.
- Revising the PRD after stakeholder feedback changes the scope or acceptance criteria.
- Recovering after a scope change mid-project — re-anchor what the work is before resuming claims.
- Before any invocation of `/fakoli-state:plan` — planning reads from a parsed PRD; authoring must come first.
- When `fakoli-state status` reports `prd-status: draft` or `prd-status: none` and the project can't proceed.
- When a co-authored PRD is ready for a formal review and approval step.

**Do not use this skill to generate or score tasks.** Once the PRD is approved, proceed to `/fakoli-state:plan` for the task graph. This skill only authors, parses, and reviews requirements.

---

## Prerequisites

`.fakoli-state/` must exist. Confirm before proceeding:

```bash
ls .fakoli-state/state.db 2>/dev/null || echo "MISSING: run fakoli-state init first"
```

If `state.db` is absent, run:

```bash
fakoli-state init --name "<project-name>"
```

Phase 3 commands used in this skill:

| Command | Phase | Status |
|---|---|---|
| `fakoli-state prd parse` | Phase 3 | available |
| `fakoli-state prd review` | Phase 3 | available |
| `fakoli-state prd review --approve` | Phase 3 | available |

The structured template at `docs/prd-template.md` (relative to the plugin root) is the canonical contract. The parser enforces it — any deviation from the required sections produces a `ParseError`.

---

## Workflow

### Step 1 — Author or update `.fakoli-state/prd.md`

Open the PRD in an editor:

```bash
$EDITOR .fakoli-state/prd.md
```

The canonical structure is defined in `docs/prd-template.md`. Required sections — the parser fails without them:

- `# Project: <Name>` — H1 title, first line of the file
- `## Summary` — one prose paragraph
- `## Goals` — bulleted list, at least one item
- `## Requirements` — bulleted list of `R001: ...` items

Optional sections that should be present in any non-trivial PRD:

- `## Non-Goals` — even if the answer is "none stated", declare it
- `## Acceptance Criteria` — project-level verifiability, not per-task
- `## Features` — logical groupings of related tasks
- `## Tasks` — hand-authored tasks with `**Acceptance criteria:**` and `**Verification:**` fields
- `## Risks`, `## Open Questions` — informs the planner's scoring

#### Co-authoring with a human

When working interactively, resist the urge to dump the full template at once. Proceed one question at a time:

1. **What are the goals?** — the bulleted list under `## Goals`. Ask the human to state what success looks like.
2. **What are the requirements?** — each atomic "the system must" statement becomes an `R00N:` bullet.
3. **What are the features and tasks?** — group related requirements, then describe the units of work.

Separate each topic as its own exchange. Confirm the goals look right before moving to requirements.

---

### Step 2 — Parse the markdown into state

```bash
fakoli-state prd parse
```

This reads `.fakoli-state/prd.md`, validates structure, and writes `Requirement`, `Feature`, and `Task` entities to `state.db`. PRD status becomes `draft`.

**On parse error:** the parser surfaces each `ParseError` with the section name and, where possible, the line number. Existing `state.db` content is preserved — no silent rollback of previous good state. Fix each error in `prd.md`, then re-run `prd parse`.

Common parse errors:

- `missing required section: Summary` — the `## Summary` heading is absent or has no body
- `missing required section: Goals (must have at least one item)` — the list is empty
- `ParseError: duplicate ID R003` — the same requirement ID appears twice; renumber
- A task block has a `**Feature:** F002` reference but no `### F002:` heading exists in `## Features`

**On success:** the command prints a summary. Verify the counts match expectations:

```
parsed 6 requirements, 3 features, 8 tasks
```

If the counts are wrong, open `prd.md` and confirm all sections parsed without truncation. Re-run until the counts match intent.

---

### Step 3 — Review the PRD

```bash
fakoli-state prd review
```

This is a gate, not a rubber-stamp. Before invoking the command, check the PRD for completeness:

- Are goals concrete statements ("Users can export a CSV with one command") rather than aspirations ("good performance")?
- Is `## Non-Goals` declared — even as a single item? A missing non-goals section is a red flag in any non-trivial project.
- Are `## Acceptance Criteria` written as independently verifiable statements, not restatements of goals?
- Does every task have a non-empty `**Acceptance criteria:**` block and at least one `**Verification:**` command?
- Are open questions either resolved or explicitly parked as known unknowns?

When co-authoring with a human, surface gaps before running the review command:

> Before running `prd review`, I noticed the following might need attention:
> - T003 has no verification commands — add at least one `pytest` or shell command
> - "## Non-Goals" is absent — even "none declared for v1" is better than silence
> - R004 says "the system handles errors" — what kind, and how? Make this measurable

Only invoke `prd review` once these items are addressed or explicitly accepted as-is.

If the review gate passes, PRD status becomes `reviewed`.

---

### Step 4 — Approve when ready

```bash
fakoli-state prd review --approve
```

Approval transitions the PRD from `reviewed` to `approved`. This is the gate that `fakoli-state claim` enforces — no task can be claimed while the PRD is in `draft` or `reviewed` status.

**Keep approval a deliberate, separate step.** In a team context, the reviewer and approver should differ: the agent reviews for structural completeness; the human approves the scope. In a solo context, read through the full PRD one more time before approving.

After approval:

```bash
fakoli-state status
```

Confirm `prd-status: approved` in the output. The project is now ready for `/fakoli-state:plan`.

---

## Iterating

The PRD will change. Here is the safe sequence for updates:

1. Edit `.fakoli-state/prd.md` with the revised content.
2. Run `fakoli-state prd parse` again. Re-parse replaces all `Requirement`, `Feature`, and `Task` entities — it is not a merge.
3. Re-run `fakoli-state prd review` if the changes are material (added/removed requirements, changed acceptance criteria, altered feature scope).
4. Re-run `fakoli-state prd review --approve` for significant scope changes. Minor editorial corrections (typo fixes, clarified wording, unchanged structure) do not require re-approval.

**Coordinate before re-parsing a live project.** Re-parse replaces Task entities in all statuses — including `claimed` and `in_progress`. Before re-parsing while active claims exist:

1. Run `fakoli-state status` to confirm no active claims.
2. If claims exist, coordinate with the agents holding them. Release the claims first, or wait for them to complete.
3. Tasks whose IDs survive the re-parse (same `T00N` ID in the file) will have their claim and evidence history preserved via the event log. Tasks that are removed from `prd.md` will lose their state rows on re-parse.

Avoid editing a task's acceptance criteria or scope while that task is `claimed` or `in_progress`. The agent working the task has already been given a work packet derived from the old spec. Release the claim first, update the PRD, re-parse, then let the agent re-claim.

---

## Common Pitfalls

- **Parsing a thinking-out-loud draft.** `prd.md` is not a scratchpad. Parse only when the document is intended as a real spec. Parsing a half-formed draft seeds `state.db` with garbage requirements that downstream planning will dutifully score and promote.
- **Approving without re-reading.** Run `cat .fakoli-state/prd.md` before invoking `--approve`. An approval event is permanent in `events.jsonl`. It cannot be undone without replaying from a snapshot.
- **Skipping `## Non-Goals`.** The planner agent uses non-goals to bound task generation. Without them, tasks may sprawl into adjacent features. Even one item is better than none.
- **Tasks without verification commands.** The `review tasks` gate (in the plan skill) requires at least one item under `**Verification:**`. Add shell commands — `pytest tests/test_foo.py`, `python -m mymodule --help` — so the gate does not block the entire queue.
- **Re-parsing with active claims and no coordination.** This silently replaces task rows. Agents holding those tasks will find their task ID in an unexpected state on next heartbeat. Always check `fakoli-state status` before re-parsing.

---

## Composition with Other Skills

| Position | Skill |
|---|---|
| Before this skill | Usually none — prd is the entry point for new projects |
| After Step 2 (parse success) | `/fakoli-state:state-ops` to verify counts and structure |
| After Step 4 (approved) | `/fakoli-state:plan` to generate features, tasks, and scores |
| If `fakoli-state status` shows `prd-status: draft` | Return here to complete review and approval |

---

## Phase 3 Limitations

LLM-assisted PRD drafting (brainstorm-to-prd pipeline) is deferred to Phase 7. The `brainstorm` skill will bridge to `fakoli-flow:brainstorm` at that point, using an LLM to co-author from rough ideas.

Until Phase 7 ships, the agent co-authors with the user directly using the deterministic template. The one-question-at-a-time pattern described in Step 1 is the Phase 3 substitute for automated brainstorm assistance.

| Feature | Phase |
|---|---|
| `fakoli-state prd parse` | Phase 3 — available |
| `fakoli-state prd review` | Phase 3 — available |
| `fakoli-state prd review --approve` | Phase 3 — available |
| LLM-assisted drafting via `--use-llm` | Phase 7 — pending |
| `fakoli-state brainstorm` CLI command | Phase 7 — pending |
