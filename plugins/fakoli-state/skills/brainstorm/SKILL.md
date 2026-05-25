---
name: brainstorm
description: Turn a rough idea into a structured PRD draft through question-by-question dialogue, then write the result to `.fakoli-state/prd.md` so `fakoli-state prd parse` can consume it. Use this skill when the user has a project intent but does not yet have a PRD — it bridges to `/fakoli-flow:brainstorm` when `claude plugin list` reports the `fakoli-flow` plugin installed, and falls back to a self-contained interview loop otherwise.
---

# Brainstorm — Rough Idea to PRD Draft

Produce a parseable PRD from an unstructured prompt by interviewing the user one question at a time. This skill writes `.fakoli-state/prd.md` — it does not parse, review, or approve. Those steps belong to the `prd` skill.

---

## When to Use

- The user has an idea ("I want to build a CLI that converts CSV to Parquet") but no PRD yet.
- `fakoli-state status` reports `prd-status: none` and the user is not ready to write the template by hand.
- A rough scope was discussed in chat and now needs to be captured as a structured document.
- The user explicitly asks to "brainstorm" or "spec out" a project before planning.

**Do not use this skill** to parse, review, or approve a PRD that already exists — use the `prd` skill. **Do not use this skill** to score, plan, or expand tasks — use the `plan` skill. **Do not use this skill** when the user already has a complete `prd.md` in hand and just wants it loaded into state.

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

This skill writes a file; it does not require any `fakoli-state` CLI subcommand to be available beyond `init`.

---

## Workflow

### Step 1 — Detect whether `fakoli-flow:brainstorm` is available

Before running the self-contained interview, run the explicit plugin check so the decision is deterministic and reproducible across sessions — no introspection of in-memory command lists, no fuzzy "if it seems available" prose:

```bash
claude plugin list 2>/dev/null | grep -q "^fakoli-flow"
```

- **Exit code 0** (`fakoli-flow` plugin present): bridge by invoking `/fakoli-flow:brainstorm` as a sub-skill — proceed with the bridge block below.
- **Non-zero exit** (plugin absent, or `claude` CLI itself not on `PATH`): fall through to Step 2 (self-contained interview). The fall-through is intentional graceful degradation: missing tooling never blocks the brainstorm flow.

When `fakoli-flow` is installed, prefer it. It runs a more thorough design dialogue (scope check, section-by-section presentation, optional visual companion) and produces a spec document. Hand off the user's rough idea and announce the bridge explicitly:

> The `fakoli-flow` plugin is installed, so I'll use its richer brainstorm flow to design this. When the spec is finished, I'll convert the result into a `prd.md` draft for `fakoli-state`.

Invoke `/fakoli-flow:brainstorm` with the user's idea as the seed. Let it run its full course — scope assessment, clarifying questions, design sections, user approval gate.

When `/fakoli-flow:brainstorm` completes and the user has approved the resulting spec file, convert the spec into the PRD template format and write it to `.fakoli-state/prd.md` (see Step 3 for the file structure and write rules). The spec produced by `fakoli-flow` will not match the `fakoli-state` PRD template verbatim — translate its sections:

- Spec goal / context → `## Summary` and `## Goals`
- Spec architectural decisions → context that feeds `## Requirements`
- Spec acceptance criteria → `## Acceptance Criteria`
- Spec out-of-scope items → `## Non-Goals`
- Spec data model / behaviors → `## Features` and `## Tasks` blocks

Show the translated `prd.md` to the user for a final glance before writing. Then proceed to Step 4.

### Step 2 — Self-contained interview (fallback)

When `fakoli-flow:brainstorm` is not available, run the interview directly. Ask one question per message. Wait for the answer before asking the next.

**Question 1 — The rough idea.** Open with:

> What are you building? A one or two sentence pitch is enough — we will refine from there.

Capture the user's answer verbatim. This becomes the seed for `## Summary`.

**Question 2 — Target users.** Ask:

> Who is this for? Internal team, external developers, end users, yourself?

The answer feeds the `## Summary` paragraph and may shape `## Non-Goals` (if the answer narrows the audience).

**Question 3 — Primary success criterion.** Ask:

> If only one thing has to be true for this project to be considered a success, what is it?

This becomes the lead bullet in `## Goals` and often the lead bullet in `## Acceptance Criteria`.

**Question 4 — Key non-goals.** Ask:

> What is explicitly out of scope for this version? Even "none declared" is a valid answer — but stating non-goals up front prevents the planner from sprawling.

This populates `## Non-Goals`. Push back gently if the user says "nothing" — most non-trivial projects have at least one obvious exclusion (e.g., "no auth in v1", "single-user only").

**Question 5 — Must-have features.** Ask:

> What are the two or three things this absolutely must do? Bullet form is fine.

Each item becomes a candidate `## Features` entry (or a `## Requirements` bullet if it is small enough to express as a single requirement).

**Question 6 — Risks and unknowns.** Ask:

> Are there any known risks, unknowns, or decisions you have not made yet?

The answer populates `## Risks` and `## Open Questions`. If the user says "none", record an empty section rather than skipping it — the visibility of "no risks identified" is itself useful information.

**Stop at six questions unless something material remains unclear.** Asking more questions than necessary fatigues the user and rarely improves the draft. If the answers are sparse, ask a single follow-up before moving to Step 3 — do not chain three more questions to "fix" thin input.

### Step 3 — Generate the PRD draft and show it to the user

Compose a draft that matches the structure in `docs/prd-template.md` (relative to the plugin root). The minimum draft uses the four required sections plus `## Non-Goals` and `## Acceptance Criteria`:

```markdown
# Project: <Name extracted from Question 1>

## Summary

<One paragraph synthesized from Questions 1 and 2.>

## Goals

- <Primary success criterion from Question 3.>
- <Each must-have feature framed as a goal statement.>

## Non-Goals

- <Each non-goal from Question 4, one per bullet.>

## Requirements

- R001: <First atomic "the system must..." statement, derived from must-have features.>
- R002: <Second atomic requirement.>
- R003: <...>

## Acceptance Criteria

- <Verifiable statement matching the primary success criterion.>
- <Additional verifiable statements covering each must-have feature.>

## Risks

- <From Question 6, or "none identified" as a single bullet.>

## Open Questions

- <From Question 6, or "none identified" as a single bullet.>
```

Add a `## Features` section only when the user named distinct groupings. Add a `## Tasks` section only when the user asked for hand-authored tasks; otherwise let `fakoli-state plan` generate them later.

**Show the draft to the user before writing.** Present the full proposed `prd.md` content inline (or as a fenced markdown block) and ask:

> Here is the PRD draft I assembled from your answers. Does this look right? Reply with edits or "looks good" to write it to `.fakoli-state/prd.md`.

Wait for explicit approval. Apply any requested edits in-place and re-present until the user accepts.

### Step 4 — Write `.fakoli-state/prd.md`

Once the user has approved the draft, check whether `.fakoli-state/prd.md` already exists:

```bash
ls .fakoli-state/prd.md 2>/dev/null
```

**If the file exists**, do not overwrite without confirmation. Show the user a one-line summary of the existing file (first heading, line count) and ask:

> `.fakoli-state/prd.md` already exists. Overwrite it with the new draft? (yes / no / save-as-backup)

- On `yes` — write the new draft to `.fakoli-state/prd.md`.
- On `no` — stop. Tell the user the draft was not written; offer to save it to a sibling path (e.g., `.fakoli-state/prd.draft.md`).
- On `save-as-backup` — copy the existing file to `.fakoli-state/prd.md.bak` first, then write the new draft to `.fakoli-state/prd.md`.

**If the file does not exist**, write the draft directly to `.fakoli-state/prd.md`.

### Step 5 — Hand off to the `prd` skill

After the file is written, tell the user the next two commands:

> Draft written to `.fakoli-state/prd.md`. Next steps:
>
> 1. Run `fakoli-state prd parse` to load the draft into `state.db`.
> 2. Open `.fakoli-state/prd.md` in an editor to refine requirements, then run `fakoli-state prd review` and `fakoli-state prd review --approve` once it is ready.
>
> See the `prd` skill for the full review and approval workflow.

Do not invoke `fakoli-state prd parse` automatically. The user should read the draft one more time on disk before parsing — that is the natural moment to catch translation errors from interview answers to PRD bullets.

---

## LLM Augmentation (Optional)

The brainstorm skill can use an LLM to generate richer follow-up questions when `ANTHROPIC_API_KEY` is set — for example, suggesting domain-specific follow-ups after Question 5 ("you mentioned a payments feature; should we capture PCI compliance as a non-goal or a requirement?"). This augmentation is optional. The skill is fully usable without an LLM and without any API key: Claude (the Code agent running this skill) drives the interview directly using the question template above.

If you want to use LLM augmentation explicitly, the user can set `ANTHROPIC_API_KEY` in their environment and the skill will surface follow-up suggestions inline. Without the key, the skill stays in the deterministic six-question loop.

---

## Anti-Patterns

- **Asking 20 questions at once.** A wall of questions produces a wall of one-word answers. Stay strictly at one question per message — even if it feels slow.
- **Writing the PRD without showing the user a draft for review.** The interview answers are raw input; the translation into PRD bullets is interpretive. Always show the draft and wait for explicit approval before writing the file.
- **Overwriting an existing `.fakoli-state/prd.md` without confirmation.** A silent overwrite can destroy a hand-authored PRD that took hours to craft. Always check for an existing file and prompt before clobbering.
- **Auto-running `fakoli-state prd parse` after writing.** The user should read the draft on disk before parsing. Hand off the next-step command; do not invoke it.
- **Skipping `## Non-Goals` because the user said "none".** Record "none identified" as an explicit bullet instead of omitting the section. Visibility matters for the planner and for reviewers.
- **Treating the bridge to `/fakoli-flow:brainstorm` as optional polish.** When the `claude plugin list` check reports `fakoli-flow` installed, its brainstorm flow produces a substantially better spec than the six-question interview. Prefer it unless the user explicitly opts for the lightweight path.

---

## Composition with Other Skills

| Position | Skill |
|---|---|
| Before this skill | Usually none — brainstorm is the entry point when no PRD exists |
| After Step 4 (file written) | `prd` — parse, review, and approve the draft |
| After `prd review --approve` | `plan` — generate features, tasks, and scores |
| If `fakoli-flow` is installed | `/fakoli-flow:brainstorm` runs first (Step 1 bridges to it) |

---

## Phase 7 Notes

| Feature | Phase | Status |
|---|---|---|
| Self-contained six-question interview | Phase 7 | available — pure markdown choreography |
| Bridge to `/fakoli-flow:brainstorm` when `fakoli-flow` is installed | Phase 7 | available — detect via `claude plugin list \| grep fakoli-flow` (explicit shell check, Phase 9 C3) |
| LLM-augmented follow-up question generation | Phase 7 | optional — requires `ANTHROPIC_API_KEY`; skill is fully usable without it |
| `fakoli-state brainstorm` CLI command | Phase 7+ | pending — for now, run this skill via `/fakoli-state:brainstorm` |
