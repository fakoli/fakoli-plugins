---
name: Complexity Mapper
description: >
  Surface hidden complexity, risks, dependencies, and likely project blow-up points in a proposed
  design or architecture. Use this when you have architecture docs, design proposals, or technical
  specs and need to identify where operational, cost, networking, or implementation complexity is
  hiding before committing resources. Produces a Complexity Heat Map and Hidden Risk Summary with
  source-anchored evidence and severity ratings. Ask for a "complexity map", "hidden risk analysis",
  "blow-up point review", or "complexity audit" to trigger this workflow.
---

# Complexity Mapper

## When to Use

Use Complexity Mapper when:

- A proposed design or architecture has been drafted and needs a rigorous complexity audit before committing resources.
- Stakeholders are confident in a design but you suspect hidden operational, cost, networking, or implementation complexity.
- You need to identify the most likely blow-up points before they become expensive surprises during implementation.
- A project is entering a review gate and needs a structured risk surface analysis.

Do **not** use Complexity Mapper when:

- The design is still in early ideation with no concrete artifacts. Recommend solidifying the design first.
- You only need a focused risk review of a specific architectural component. Use `architecture-risk-review` instead.
- The source material is too large for a single analysis pass. Run `context-sharding` first, then feed sharded outputs into this workflow.

## Inputs Required

| Input               | Required | Description                                                                                                                                                                 |
| ------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Documentation       | Yes      | Architecture docs, design proposals, technical specs, API references, infrastructure diagrams, or any material describing the system under analysis.                        |
| Design assumptions  | Yes      | Stated or implied assumptions the design relies on — scaling expectations, cost models, SLA targets, team capacity.                                                         |
| Constraints         | Yes      | Hard limits: budget ceilings, latency requirements, compliance mandates, vendor lock-in boundaries.                                                                         |
| Operational context | No       | Current operational environment: existing infrastructure, team expertise, monitoring capabilities, incident history. Improves analysis quality significantly when provided. |

## Process Steps

### Step 1: Invoke doc-indexer on Provided Materials

Before starting extraction, check `plugins/systems-thinking/reference/vendor_docs/` for pre-loaded vendor documentation relevant to the analysis target (e.g., service limits, pricing pages, known issues). Include any relevant vendor docs alongside user-provided materials as additional input for the doc-indexer.

Run the `doc-indexer` agent on all provided documentation to produce a structural map of the material:

- Section inventory with topic classification.
- Cross-reference map showing which sections reference each other.
- Identification of gaps: topics mentioned but not documented, external dependencies referenced but not detailed.

The doc-indexer output serves as the routing table for Step 2. If the doc-indexer identifies significant gaps in the documentation, flag these immediately — they are themselves a complexity signal.

### Step 1.5: Conditionally Invoke web-researcher for External Sources

If the analysis requires external documentation (vendor docs, pricing pages, service quotas) that is not available locally, or if the doc-indexer identifies gaps that need external sources:

1. Invoke the `web-researcher` agent with the specific topics or documentation gaps to research.
2. The web-researcher produces a **Source Manifest** listing discovered URLs, document locations, and sections of interest.
3. Present the Source Manifest to the user for review before proceeding — the user may want to add, remove, or reprioritize sources.
4. Feed approved sources back into doc-indexer for structural mapping, or pass them directly to the extraction-planner in Step 2.

**Skip this step** if all necessary material is already available locally or has been provided by the user.

### Step 2: Invoke extraction-planner for Dispatch Planning

Run the `extraction-planner` agent with the doc-indexer output (and any web-researcher Source Manifest from Step 1.5). The extraction-planner:

1. Assesses the total volume and complexity of material (section count, page count, topic diversity).
2. Determines how many extraction agents to spawn and of which types.
3. Writes specific, scoped instructions for each extractor — what sections to read, what to focus on, what to skip.
4. Produces a **Dispatch Plan** specifying agent assignments.

This step prevents extractor overload. Instead of one massive extraction prompt, each agent receives bounded, focused instructions.

**Skip this step** if the doc-indexer identifies ≤5 total sections. In that case, proceed directly to Step 3 with a single extractor per type.

### Step 3: Launch Extraction Agents Per the Dispatch Plan

Following the Dispatch Plan from Step 2 (or using default single-extractor-per-type if Step 2 was skipped), launch the extraction agents in parallel:

**Agent A — caveat-extractor**

- Target: All sections containing limitations, quotas, rate limits, deprecation notices, known issues, edge cases, and traps.
- Instruction: Extract every caveat with its source location, severity assessment, and the conditions under which it would be triggered.
- Pay special attention to: soft limits that become hard limits at scale, features marked as "beta" or "preview," cross-service interaction caveats, and documentation that says "not recommended for production."

**Agent B — cost-capacity-analyst**

- Target: All sections related to pricing, resource allocation, scaling behavior, throughput limits, and capacity planning.
- Instruction: Extract cost models, identify non-linear cost curves (costs that explode at scale), find capacity cliffs (points where adding load requires architectural changes, not just more resources), and flag any pricing that depends on usage patterns the design assumes but hasn't validated.
- Pay special attention to: egress costs, per-request pricing at projected volumes, storage costs over time, and the gap between "free tier" assumptions and production reality.

**Agent C — architecture-dependency-mapper**

- Target: All sections describing system components, integrations, data flows, and external service dependencies.
- Instruction: Map every dependency with its ownership (internal team, external vendor, open source), SLA, failure mode, and blast radius. Identify single points of failure, circular dependencies, and components where the dependency chain is deeper than two levels.
- Pay special attention to: shared infrastructure that multiple components assume is always available, implicit ordering dependencies, and services owned by teams outside the project's control.

### Step 4: Collect Extraction Outputs

Gather outputs from all three extraction agents. For each output:

- Verify it contains source anchors (specific document sections, page numbers, or URLs).
- Check for contradictions between agents (e.g., cost-capacity-analyst assumes a scaling path that caveat-extractor has flagged as limited).
- Note any sections that no agent covered — these may indicate documentation gaps or areas that don't fit neatly into one extraction category.

### Step 5: Invoke synthesis-brief-writer

Pass all three extraction outputs plus the original design assumptions and constraints to the `synthesis-brief-writer` agent with instructions to produce:

**Complexity Heat Map**: A structured view of where complexity concentrates in the design, rated by:

- Likelihood of causing problems (High / Medium / Low)
- Impact if the complexity materializes (High / Medium / Low)
- Visibility — whether current monitoring/testing would catch it before production (Visible / Hidden / Unknown)

**Hidden Risk Summary**: A prioritized list of risks that are not obvious from a surface reading of the design, including:

- The risk and what triggers it.
- Evidence from the extraction outputs.
- Which design assumptions it threatens.
- Recommended investigation or mitigation.

### Step 6: Present Findings to User

After synthesis, compare the output format and depth against any examples in `plugins/systems-thinking/reference/examples/` to ensure consistency with established quality standards.

Deliver the Complexity Heat Map and Hidden Risk Summary with:

- A top-3 list of the most dangerous complexity concentrations — the places most likely to cause project delays, cost overruns, or production incidents.
- Explicit flags on any findings based on single-source evidence (lower confidence).
- Recommended next steps: what to investigate further, what to prototype, what to get vendor confirmation on.

## Output Format

The output consists of two artifacts conforming to their respective output contracts:

### Complexity Heat Map

```
## Complexity Heat Map

### Summary
[1-2 sentence overview of where complexity concentrates]

### Heat Map

| Area | Complexity Type | Likelihood | Impact | Visibility | Source |
|---|---|---|---|---|---|
| [Component/Integration] | [Operational/Cost/Dependency/Implementation] | [H/M/L] | [H/M/L] | [Visible/Hidden/Unknown] | [Doc section ref] |

### Top Concentrations
1. [Area]: [Why this is the highest-risk complexity concentration]
2. [Area]: [Why this ranks second]
3. [Area]: [Why this ranks third]
```

### Hidden Risk Summary

```
## Hidden Risk Summary

### Risks (Ordered by Severity)

#### Risk: [Name]
- **Trigger**: [What causes this risk to materialize]
- **Evidence**: [Specific findings from extraction, with source anchors]
- **Threatened Assumptions**: [Which design assumptions this undermines]
- **Severity**: [Critical / High / Medium / Low]
- **Confidence**: [High / Medium / Low — based on evidence quality]
- **Recommended Action**: [Investigate / Prototype / Get vendor confirmation / Redesign]

[Repeat for each risk]

### Evidence Gaps
- [Topic]: [What is missing and why it matters]

### Recommended Next Steps
1. [Action with rationale]
2. [Action with rationale]
```

## Failure Modes and Caution Points

| Failure Mode                    | Signal                                                                                                                          | Response                                                                                                                                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Insufficient documentation      | doc-indexer identifies major structural gaps; extraction agents return thin results                                             | Flag low confidence on the overall analysis. List specific documentation gaps as findings in their own right. Recommend the user provide additional material before treating the analysis as comprehensive. |
| Single-source analysis          | Most findings come from one document or one extraction agent                                                                    | Flag in the output that findings are single-source. Confidence ratings should be lowered accordingly. Recommend cross-referencing with additional sources.                                                  |
| Design too early-stage          | Provided materials are aspirational rather than concrete; extraction agents cannot identify specific components or dependencies | Stop or downgrade the analysis. Inform the user that complexity mapping requires concrete design artifacts. Recommend returning after the design has been elaborated.                                       |
| Extraction agent contradiction  | cost-capacity-analyst and caveat-extractor produce conflicting assessments of the same component                                | Surface the contradiction explicitly in the synthesis. Do not silently resolve it. Present both perspectives and recommend investigation.                                                                   |
| Scope too large for single pass | doc-indexer produces a structural map with more than 30 distinct sections or 5+ major subsystems                                | Recommend running `context-sharding` first to split the material, then running complexity-mapper on each shard, followed by a cross-shard synthesis pass.                                                   |
