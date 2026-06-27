---
name: Decision Brief
description: >
  Package extracted findings into a compact, decision-ready format for engineers, managers, or
  review bodies. Use this after running complexity-mapper, architecture-risk-review, or
  context-sharding to synthesize findings into a structured brief with options, evidence, risks,
  and recommended next steps. Produces a Decision Brief with evidence summary, top risks,
  unresolved questions, and actionable recommendations. Ask for a "decision brief",
  "decision package", or "summarize findings for a decision" to use this workflow.
---

# Decision Brief

## When to Use

Use Decision Brief when:

- Findings from extraction, analysis, or prior workflow runs need to be packaged for a specific decision audience — engineering leads, architecture review boards, management, or cross-functional stakeholders.
- A decision is pending and the decision-makers need a structured, evidence-based summary rather than raw analysis output.
- You need to translate technical findings into a format that supports clear reasoning about options, trade-offs, and next steps.
- Multiple prior workflows have produced outputs that need to be synthesized into a single coherent recommendation surface.

Do **not** use Decision Brief when:

- No extraction or analysis has been performed yet. Run `complexity-mapper`, `context-sharding`, or `architecture-risk-review` first to generate the raw findings.
- The decision is purely technical and the audience is the same person who did the analysis. In that case, the raw analysis output may be sufficient.
- The findings are too preliminary for a decision — flag this and recommend further analysis instead of producing a weak brief.

## Inputs Required

| Input              | Required | Description                                                                                                                                                                      |
| ------------------ | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Extracted findings | Yes      | Outputs from prior workflow runs: Context Packets, Complexity Heat Maps, Hidden Risk Summaries, or direct analysis results. The more structured the input, the better the brief. |
| Ranked risks       | Yes      | Prioritized list of risks with severity assessments. Typically produced by complexity-mapper or architecture-risk-review. If not available, the brief will flag this gap.        |
| Assumptions        | Yes      | Assumptions underlying the findings — both validated and unvalidated. These become critical context for decision-makers.                                                         |
| Decision audience  | No       | Who will read this brief and what decisions they are empowered to make. Shapes the level of technical detail and the framing of options. Defaults to technical leadership.       |
| Options considered | No       | If multiple design or implementation options were evaluated, provide them. If not provided, the brief will present findings as applying to the current proposed approach.        |

## Process Steps

### Step 1: Gather Extraction Outputs

Collect all available outputs from prior workflow runs or direct input:

- Context Packets from `context-sharding`
- Complexity Heat Maps and Hidden Risk Summaries from `complexity-mapper`
- Risk assessments from `architecture-risk-review`
- Pattern Remix Drafts from `pattern-remix`
- Source Manifests from `web-researcher` (if web research was performed upstream)
- Dispatch Plans from `extraction-planner` (for understanding how extraction was parallelized)
- Any direct analysis notes, findings, or data provided by the user

For each input, verify:

1. **Source anchors are present**: Every finding should trace back to specific evidence. Unanchored findings get flagged as inferred.
2. **Confidence ratings are present**: If the input doesn't include confidence, assign conservative ratings and note that they were not part of the original analysis.
3. **Recency**: Ensure the findings are current. Stale analysis based on outdated documentation should be flagged.

If the inputs are insufficient for a meaningful brief — fewer than three substantive findings, no risk assessment, or no concrete evidence — **stop and recommend** running `complexity-mapper` or another appropriate upstream workflow first. Do not produce a thin brief that creates false confidence.

### Step 2: Invoke synthesis-brief-writer with Decision Brief Contract

Before final synthesis, check `plugins/systems-thinking/reference/examples/` for sample Decision Brief outputs. Match the format and depth of any found examples to maintain consistency. Also check `plugins/systems-thinking/reference/prompts/` for decision-framing patterns the user has found effective — these can sharpen the brief's structure and language.

Pass all gathered inputs to the `synthesis-brief-writer` agent with the Decision Brief output contract and the following instructions:

**Structure the brief to answer these questions in order:**

1. **What is being decided?** Frame the decision clearly. If the user hasn't stated the decision explicitly, infer it from the findings and flag the inference.
2. **What options were considered?** List each option with a one-sentence description. If only one option was analyzed, state this and note that the brief reflects a single-option assessment.
3. **What does the evidence say?** Summarize findings organized by option. Separate evidence-backed findings from inferred concerns. Every finding must cite its source.
4. **What are the top risks?** Present the highest-severity risks with their triggers, impact, and likelihood. Include source anchors.
5. **What is unresolved?** List open questions that the decision-makers should be aware of — things the analysis could not answer, data that was missing, assumptions that remain unvalidated.
6. **What should happen next?** Recommend concrete next steps: validations to run, prototypes to build, vendor conversations to have, follow-up analyses to commission.

**Synthesis-brief-writer constraints:**

- Do not introduce new analysis. The brief synthesizes existing findings; it does not generate new ones.
- Mark every inferred concern with `[Inferred]` so decision-makers can distinguish evidence from interpretation.
- If findings from different sources contradict each other, present both perspectives. Do not silently resolve contradictions.
- Keep the brief under 2 pages of content (excluding tables). Decision-makers will not read longer documents; move supporting detail to appendices.

### Step 3: Verify Output Completeness

Before presenting, check the Decision Brief against these requirements:

- [ ] **Decision frame**: The decision being made is clearly stated.
- [ ] **Options considered**: At least one option is described. Single-option briefs are explicitly labeled as such.
- [ ] **Evidence summary**: Findings are organized, sourced, and confidence-rated.
- [ ] **Inferred concerns marked**: Every inference is labeled `[Inferred]`.
- [ ] **Top risks**: At least three risks are listed with severity, trigger, and source. If fewer than three risks were identified, flag this as unusual.
- [ ] **Unresolved questions**: At least one open question is listed. If none were found, flag this — it usually means the analysis wasn't deep enough.
- [ ] **Recommended next steps**: Concrete, actionable items with rationale.
- [ ] **Length check**: Core brief fits in 2 pages. Appendices are used for supporting detail.

If any check fails, return to the `synthesis-brief-writer` with specific feedback.

### Step 4: Present to User

Deliver the Decision Brief with:

- A one-line summary of the decision and the brief's top recommendation (or "no recommendation — insufficient evidence" if that is the case).
- The full brief.
- A note on what would strengthen the brief if the user wants higher confidence: additional data, further analysis, stakeholder input.

## Output Format

The output is a **Decision Brief** conforming to the output contract:

```
## Decision Brief

### Decision Frame
[What is being decided, who is deciding, and what authority level is required]

### Options Considered
| Option | Description | Analysis Depth |
|---|---|---|
| [Option A] | [One-sentence description] | [Full / Partial / Surface-level] |
| [Option B] | [One-sentence description] | [Full / Partial / Surface-level] |

### Evidence Summary

#### Option A
- [Finding]: [Source] — Confidence: [H/M/L]
- [Finding]: [Source] — Confidence: [H/M/L]
- [Inferred] [Concern]: [Reasoning] — Confidence: [L]

#### Option B
- [Finding]: [Source] — Confidence: [H/M/L]

### Top Risks
| Risk | Severity | Trigger | Evidence Source | Confidence |
|---|---|---|---|---|
| [Risk] | [Critical/High/Medium] | [What causes it] | [Source anchor] | [H/M/L] |

### Contradictions (if any)
- [Source A] says [X]; [Source B] says [Y]. Resolution requires: [action].

### Unresolved Questions
| Question | Why It Matters | Suggested Resolution |
|---|---|---|
| [Question] | [Impact on decision] | [How to answer it] |

### Recommended Next Steps
1. [Action]: [Rationale] — Owner: [Suggested]
2. [Action]: [Rationale] — Owner: [Suggested]

### Appendices (if needed)
- [Appendix A: Full risk inventory]
- [Appendix B: Detailed evidence tables]
```

## Failure Modes and Caution Points

| Failure Mode                        | Signal                                                                                                  | Response                                                                                                                                                                                         |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Insufficient extraction data        | Step 1 yields fewer than 3 substantive findings or no risk assessment                                   | Stop. Do not produce a thin brief. Recommend running `complexity-mapper` or `architecture-risk-review` first to generate adequate raw material.                                                  |
| Single-perspective input            | All findings come from one source, one extraction agent, or one analysis workflow                       | Flag in the brief that the evidence base is limited. Lower all confidence ratings by one level. Recommend additional analysis from a different angle.                                            |
| Missing cost or dependency analysis | No findings related to cost implications or system dependencies                                         | Flag the gap explicitly in the Unresolved Questions section. Recommend running the relevant extraction (cost-capacity-analyst or architecture-dependency-mapper) before finalizing the decision. |
| Stale findings                      | Input findings are based on documentation or analysis more than 30 days old                             | Flag recency concerns in the brief. Recommend re-running upstream analysis with current documentation before making the decision.                                                                |
| False precision                     | Brief presents low-confidence findings as high-confidence, or uses precise numbers from rough estimates | Review confidence ratings in Step 3. Ensure `[Inferred]` labels are applied. Remove false precision from quantitative claims.                                                                    |
| Scope creep in synthesis            | synthesis-brief-writer introduces new analysis not present in the inputs                                | Reject and re-invoke. The brief synthesizes; it does not analyze. New observations must be labeled `[Inferred]` at minimum, but the brief should not be the place for new investigation.         |
