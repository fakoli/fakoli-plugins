---
name: Context Sharding
description: >
  Split large or varied source material across parallel subagents for extraction before synthesis.
  Use this when documentation exceeds what can be processed in a single pass — typically more than
  5 dense documents or 50+ pages — or when material spans multiple distinct domains. Produces
  structured Context Packets that can feed into complexity-mapper, decision-brief, or
  architecture-risk-review. Ask to "shard documents", "split for parallel extraction", or
  "break this into digestible chunks" to use this workflow.
---

# Context Sharding

## When to Use

Use Context Sharding when:

- Source material exceeds what can be effectively processed in a single reasoning pass — typically more than 5 dense documents or 50+ pages of technical content.
- Source material spans multiple distinct domains, technologies, or concerns that benefit from specialized extraction.
- You need to feed extracted content into a downstream workflow (complexity-mapper, decision-brief, architecture-risk-review) and the raw material is too large to pass directly.
- A codebase audit requires reading multiple modules, services, or configuration files that are loosely coupled.

Do **not** use Context Sharding when:

- The material is small enough to process in one pass. Sharding adds overhead; use it only when the material genuinely exceeds single-pass capacity.
- The material is a single tightly integrated document where splitting would destroy critical context. In this case, summarize rather than shard.
- You need real-time interactive exploration. Sharding is a batch workflow.

## Inputs Required

| Input               | Required | Description                                                                                                                                                        |
| ------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Source material     | Yes      | Large document sets, multiple documents, big codebases, or any collection of material that needs extraction. Provide file paths, URLs, or inline content.          |
| Extraction goal     | Yes      | What information needs to be extracted. This drives the sharding strategy and the instructions given to each doc-reader instance.                                  |
| Downstream workflow | No       | If the sharded output will feed into another skill (complexity-mapper, decision-brief, etc.), specify it so the extraction can be shaped to match expected inputs. |

## Process Steps

### Step 0.5: Conditionally Invoke web-researcher for External Sources

If the extraction goal involves topics that require web research (e.g., vendor documentation, pricing, service limits not available locally):

1. Invoke the `web-researcher` agent to discover and collect relevant source material.
2. Present the Source Manifest to the user for review.
3. Include approved web sources alongside local materials as input for doc-indexer in Step 1.

Web-sourced material should be treated as separate shard candidates from local material to maintain source clarity.

**Skip this step** if all material is already available locally.

### Step 1: Invoke doc-indexer to Map All Provided Materials

When inventorying materials to shard, also check `plugins/systems-thinking/reference/vendor_docs/` and `plugins/systems-thinking/reference/previous_designs/` for files relevant to the extraction goal. Include relevant reference materials as additional input sources.

Run the `doc-indexer` agent on the full set of provided materials (including any web-sourced material from Step 0.5). The doc-indexer produces:

- A complete inventory of all documents/files with size, type, and topic classification.
- A structural map showing how documents relate to each other (cross-references, shared topics, dependency chains).
- An identification of natural boundary lines — where the material can be split with minimal information loss.

This output is the foundation for the sharding plan. Do not skip this step and shard based on file names or guesses.

### Step 2: Design the Sharding Plan

Using the doc-indexer output, design a sharding plan that optimizes for:

**Source separation**: Keep reference materials (from `plugins/systems-thinking/reference/`) in separate shards from user-provided materials to maintain source clarity. This makes it easy to distinguish findings derived from reference context vs. primary inputs.

**Shard independence**: Each shard should be processable without requiring context from other shards. The less cross-shard dependency, the higher the quality of parallel extraction.

**Shard coherence**: Each shard should cover a logically complete unit — a service, a subsystem, a concern area, a document group. Avoid splitting a single tightly coupled section across shards.

**Shard size balance**: Shards should be roughly equal in processing effort. One massive shard and four tiny ones defeat the purpose of parallelization.

The sharding plan should specify:

```
| Shard ID | Contents | Rationale | Cross-references to other shards | Extraction focus |
|---|---|---|---|---|
| shard-1 | [Files/sections] | [Why these belong together] | [References to shard-2, shard-3, etc.] | [What to extract from this shard] |
```

**Sharding strategies** (choose based on material structure):

- **By document**: When documents are self-contained and cover distinct topics.
- **By subsystem/service**: When material describes a multi-component system.
- **By concern**: When multiple documents cover the same system but from different angles (cost, security, operations, implementation).
- **By layer**: When material spans infrastructure, platform, application, and user-facing concerns.

If the material is too interrelated to shard cleanly, flag this and adjust: either use larger shards with more overlap, or add a mandatory cross-reference pass in Step 5.

### Step 3: Execute Parallel doc-reader Extractions

Launch one `doc-reader` instance per shard with:

- The specific files/sections assigned to that shard.
- The extraction goal tailored to the shard's focus area.
- Instructions to produce a Context Packet as output.
- A reminder to flag any references to material outside the shard (these become cross-reference signals).

All doc-reader instances run in parallel. Each produces a Context Packet containing:

- Extracted facts, decisions, constraints, and open questions.
- Source anchors for every extracted item.
- Flags for out-of-shard references that may need cross-referencing.
- Confidence ratings on extracted items.

### Step 3.5: Optionally Invoke extraction-planner for Caveat Extraction

If the extraction goal includes risk identification, limitation discovery, or the downstream workflow is complexity-mapper or architecture-risk-review, and the per-shard material volume is large (>5 sections per shard):

1. Run the `extraction-planner` on each shard to determine how many caveat-extractors to spawn per shard and what scoped instructions each receives.
2. Use the Dispatch Plan to launch targeted caveat-extractors.

**Skip this step** if per-shard material is small (≤5 sections) — use a single caveat-extractor per shard.

### Step 4: Optionally Run caveat-extractor on Each Shard

If the extraction goal includes risk identification, limitation discovery, or the downstream workflow is complexity-mapper or architecture-risk-review:

- Following the Dispatch Plan from Step 3.5 (or one caveat-extractor per shard if Step 3.5 was skipped), run `caveat-extractor` on each shard's raw material (not on the Context Packet — on the original source).
- Append caveat extraction results to the corresponding Context Packet.

This step adds depth but also adds processing time. Skip it if the extraction goal is purely informational (e.g., summarization, inventory).

### Step 5: Collect All Context Packets

Gather Context Packets from all shards. Post-collection quality checks:

1. **Completeness**: Every shard produced output. If any shard failed, investigate and re-run before proceeding.
2. **Cross-reference resolution**: Review out-of-shard reference flags from Step 3. For each:
   - If the referenced material exists in another shard's Context Packet, link them.
   - If the reference points to material not covered by any shard, flag it as a gap.
3. **Contradiction detection**: Scan across Context Packets for conflicting facts or assessments. Surface contradictions explicitly rather than silently picking one.
4. **Coverage verification**: Compare the doc-indexer structural map from Step 1 against the collected Context Packets. Ensure no section of the original material was dropped.

If critical cross-references were lost in sharding, run a targeted cross-reference pass: a single agent that reads the relevant sections from multiple shards and produces a Cross-Reference Addendum appended to the affected Context Packets.

### Step 6: Present or Forward Sharded Extractions

Depending on the workflow:

**If presenting directly to the user**: Deliver all Context Packets with a summary that includes:

- How the material was sharded and why.
- Key findings per shard.
- Cross-shard themes or contradictions.
- Gaps identified.

**If feeding into a downstream workflow**: Package the Context Packets in the format expected by the target skill:

- `complexity-mapper`: Pass as documentation input along with design assumptions.
- `decision-brief`: Pass as extracted findings input.
- `architecture-risk-review`: Pass as architecture docs input.

## Output Format

The output is a set of **Context Packets**, one per shard, conforming to the output contract:

```
## Context Packet — [Shard ID]: [Shard Label]

### Shard Scope
- **Contents**: [Files/sections in this shard]
- **Extraction Focus**: [What was extracted and why]

### Extracted Items

#### [Category: Facts / Decisions / Constraints / Open Questions]
| Item | Source | Confidence | Cross-Shard Reference |
|---|---|---|---|
| [Extracted item] | [Document, section, line] | [High/Medium/Low] | [Shard ID if referencing another shard, or "None"] |

### Caveats (if caveat-extractor was run)
| Caveat | Severity | Trigger Condition | Source |
|---|---|---|---|
| [Caveat] | [Critical/High/Medium/Low] | [When this becomes a problem] | [Source anchor] |

### Out-of-Shard References
- [Reference]: [What shard or external source it points to] — [Resolved / Unresolved]

### Shard Summary
[2-3 sentence summary of the most important findings in this shard]
```

### Sharding Summary (delivered with the full set of Context Packets)

```
## Sharding Summary

### Sharding Strategy
[Strategy used and rationale]

### Shard Overview
| Shard ID | Label | Items Extracted | Caveats Found | Cross-References | Confidence |
|---|---|---|---|---|---|
| shard-1 | [Label] | [Count] | [Count] | [Count resolved / unresolved] | [H/M/L] |

### Cross-Shard Themes
- [Theme]: [Which shards contribute to this theme]

### Contradictions
- [Contradiction]: [Shard X says A, Shard Y says B] — [Recommended resolution]

### Gaps
- [Gap]: [What is missing and which shard boundary caused it]
```

## Failure Modes and Caution Points

| Failure Mode                                | Signal                                                                                                   | Response                                                                                                                                                             |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Documents too interrelated to shard cleanly | doc-indexer shows dense cross-reference graph; most documents reference most other documents             | Use larger shards with intentional overlap at boundaries. Add a mandatory cross-reference pass after extraction. Accept higher processing cost for better coherence. |
| Individual shards still too large           | A single shard exceeds single-pass processing capacity                                                   | Re-shard: split the oversized shard into sub-shards. Apply the same sharding strategy recursively. Update the sharding plan.                                         |
| Critical cross-references lost in sharding  | Step 5 reveals important links between shards that neither shard's Context Packet captured               | Run a targeted cross-reference pass. A single agent reads the boundary material from both shards and produces a Cross-Reference Addendum.                            |
| Shard failure                               | One or more doc-reader instances fail to produce output                                                  | Do not proceed with incomplete data. Investigate the failure (material too dense, format issues, access problems), fix, and re-run the failed shard.                 |
| Unbalanced shards                           | One shard produces vastly more extracted items than others                                               | Review the sharding plan. The large shard may need splitting, or the small shards may be too granular and should be merged. Rebalance for the next run.              |
| Over-sharding                               | Material is split into so many shards that the synthesis step cannot hold all Context Packets in context | Reduce shard count. Merge related shards. As a rule of thumb, keep shard count under 8 for a single synthesis pass.                                                  |
