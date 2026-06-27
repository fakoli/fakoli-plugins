---
name: Pattern Remix
description: >
  Generate high-quality first drafts by adapting prior proven work to new problems. Use this when
  you have successful prior designs, implementations, or architectural patterns and need a strong
  starting point for a new but related problem. Produces a Pattern Remix Draft that maps reused
  elements to their sources, flags carried assumptions, identifies divergence risks, and provides
  implementation steps. Ask to "remix a prior design", "adapt existing work", or "create a first
  draft from prior patterns" to use this workflow.
---

# Pattern Remix

## When to Use

Use Pattern Remix when:

- You have one or more prior successful designs, implementations, or architectural patterns and need to produce a strong first draft for a new but related problem.
- The new problem shares structural similarity with prior work but differs in domain, scale, constraints, or target audience.
- You want to accelerate the design phase by leveraging proven decisions rather than starting from scratch.

Do **not** use Pattern Remix when:

- No relevant prior work exists. In that case, start with a clean design process.
- The new problem is fundamentally different from all available prior work. Forcing a remix will import inappropriate assumptions.
- The prior work is known to have unresolved flaws that would propagate into the new draft.

## Inputs Required

| Input           | Required | Description                                                                                                                                                        |
| --------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Prior artifacts | Yes      | Designs, implementations, architecture docs, or decision records from previous successful work. Source from `plugins/systems-thinking/reference/previous_designs/` or user-specified locations. |
| Target state    | Yes      | Clear description of what the new design must achieve — goals, success criteria, user/system requirements.                                                         |
| Constraints     | Yes      | Hard boundaries: budget, timeline, technology mandates, compliance requirements, team capabilities.                                                                |
| Anti-patterns   | No       | Known failure modes, rejected approaches, or patterns explicitly ruled out for the new context.                                                                    |

## Process Steps

### Step 1: Gather Prior Artifacts

Collect all prior artifacts that may be structurally relevant to the new problem. Check the following sources in order:

1. `plugins/systems-thinking/reference/previous_designs/` directory for indexed prior work, proposals, and architecture notes.
2. User-specified file paths or repositories.
3. Context Packets from prior workflow runs that contain relevant design extractions.

When scanning `plugins/systems-thinking/reference/previous_designs/`, present any found materials to the user for selection before proceeding — not all prior work will be relevant to the current remix.

For each artifact, note:

- What problem it solved.
- What constraints it operated under.
- What trade-offs it made and why.
- What worked well and what was fragile.

If no relevant prior artifacts can be found, **stop here** and inform the user. Recommend starting with a clean design process or running `context-sharding` on broader source material to surface potential reference points.

### Step 2: Clarify Target State and Constraints

Before remixing, establish alignment with the user on:

- **Target state**: What does success look like? What are the measurable outcomes?
- **Constraints**: What is non-negotiable? Technology, cost, timeline, compliance, team skill boundaries.
- **Delta from prior work**: What is explicitly different this time? New scale requirements, different users, changed technology landscape, different risk tolerance.
- **Anti-patterns**: What has been tried and failed, or what approaches are explicitly off the table?

Document these as structured inputs. Do not proceed with ambiguity on target state or hard constraints.

### Step 3: Invoke pattern-remix-planner Agent

Before invoking, check `plugins/systems-thinking/reference/prompts/` for analysis prompts relevant to the problem domain. If found, use them to guide the remix approach and framing. Also check `plugins/systems-thinking/reference/examples/` for sample Pattern Remix Draft outputs to calibrate quality and depth expectations for the output.

Pass the following context to the `pattern-remix-planner` agent:

- All gathered prior artifacts with annotations from Step 1.
- Target state and constraints from Step 2.
- Anti-patterns (if provided).
- Explicit instruction to produce a Pattern Remix Draft that:
  - Maps each reused element to its source in the prior work.
  - Flags every assumption carried forward from prior work.
  - Identifies where the new context diverges and what adaptation was applied.
  - Lists open questions that require user input before the draft is finalized.
  - Calls out risks introduced by the remix (pattern mismatch, scale mismatch, context drift).

### Step 4: Review Output for Completeness

Before presenting to the user, verify the Pattern Remix Draft contains all required sections:

- [ ] **Reused elements**: Each element traced to its source artifact.
- [ ] **Adapted elements**: Each adaptation justified by a stated constraint or target-state difference.
- [ ] **Carried assumptions**: Every assumption from prior work explicitly listed, with a note on whether it still holds.
- [ ] **Risks**: At least one risk per major reused element. If none are identified, flag this as suspicious and re-examine.
- [ ] **Open questions**: Unresolved decisions that require user input, domain expertise, or further investigation.
- [ ] **Anti-pattern compliance**: Confirm no anti-patterns were inadvertently reintroduced.

If any section is missing or thin, loop back to the `pattern-remix-planner` agent with specific feedback before presenting.

### Step 5: Present Pattern Remix Draft to User

Deliver the completed draft with:

- A summary of what was reused, what was adapted, and what is new.
- A confidence assessment: how closely does the prior work map to the new problem?
- Explicit next steps: what decisions must the user make, what needs validation, what should be stress-tested.

## Output Format

The output is a **Pattern Remix Draft** conforming to the output contract:

```
## Pattern Remix Draft

### Source Mapping
| New Element | Source Artifact | Adaptation Applied | Assumption Carried |
|---|---|---|---|

### Carried Assumptions
- [Assumption]: [Still valid? / Needs validation / Likely invalid]

### Adaptations Applied
- [Element]: [What changed and why]

### Risks
- [Risk]: [Severity] — [Mitigation or open question]

### Open Questions
- [Question]: [Why it matters] — [Suggested next step]

### Anti-Pattern Check
- [Anti-pattern]: [Status: Avoided / Risk of reintroduction]

### Confidence Assessment
[High / Medium / Low] — [Rationale]

### Recommended Next Steps
1. [Action]
2. [Action]
```

## Failure Modes and Caution Points

| Failure Mode                               | Signal                                                                                     | Response                                                                                                           |
| ------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| No relevant prior work available           | Step 1 yields no artifacts with structural similarity                                      | Stop. Inform user. Recommend clean design or broader source gathering via `context-sharding`.                      |
| Prior work is from a very different domain | Artifact annotations show fundamentally different problem structure, users, or constraints | Proceed with caution. Flag low confidence in the remix. Recommend treating the output as inspiration, not a draft. |
| Constraints contradict prior patterns      | Step 2 reveals hard constraints that invalidate core decisions in the prior work           | Identify which elements cannot be reused. If the majority are invalidated, recommend clean design instead.         |
| Over-fitting to prior work                 | Draft reuses elements without meaningful adaptation                                        | Review Step 4 checklist. Ensure every reused element has an explicit justification for why it still applies.       |
| Assumption drift                           | Assumptions from prior work are carried forward without examination                        | Enforce the Carried Assumptions section. Every assumption must have a validity assessment.                         |
| Anti-pattern reintroduction                | Draft includes patterns the user explicitly ruled out                                      | Check Step 4 anti-pattern compliance. Reject and re-invoke if violations are found.                                |
