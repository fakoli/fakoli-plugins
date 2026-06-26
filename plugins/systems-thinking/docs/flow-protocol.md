# Fakoli-Flow Compatibility

This document explains how systems-thinking agents integrate with the
**fakoli-flow** orchestration plugin. It maps the 3-tier pipeline (Discovery,
Extraction, Synthesis) to fakoli-flow's wave model and describes the status
file format agents write between waves.

## The Wave Model

fakoli-flow dispatches agents in waves. Agents in the same wave run in
parallel. Agents in different waves run sequentially, with the orchestrator
reading status files between waves to confirm completion and pass decisions
forward.

The systems-thinking pipeline maps cleanly to three waves:

### Wave 1 — Discovery (research)

| Agent | Role |
|---|---|
| `web-researcher` | Find and catalog source material from the web and local files |
| `extraction-planner` | Assess material volume, produce Dispatch Plan for Wave 2 |

`web-researcher` runs first to build the Source Manifest. `extraction-planner`
then reads the Source Manifest (and doc-indexer output, if available) and
produces the Dispatch Plan. Because `extraction-planner` depends on
`web-researcher` output, they run sequentially within Wave 1 in practice —
the orchestrator may dispatch them as two sub-waves or as a single sequential
wave depending on whether local documents are pre-loaded.

Wave 1 produces no extracted findings. It produces discovery artifacts only
(Source Manifest, Dispatch Plan) that Wave 2 agents consume.

### Wave 2 — Extraction (parallel)

| Agent | Role |
|---|---|
| `doc-indexer` | Map document structure, flag high-value sections |
| `doc-reader` | Extract technical claims, limits, implementation details |
| `caveat-extractor` | Find buried limitations, quotas, exclusions, traps |
| `cost-capacity-analyst` | Surface cost mechanics and scaling constraints |
| `architecture-dependency-mapper` | Map control/data-plane dependencies, identify SPOFs |

All Wave 2 agents run in parallel on their assigned sections from the Dispatch
Plan. No Wave 2 agent sees another's output during extraction — they work
independently to prevent cross-contamination of interpretation.

Each Wave 2 agent writes a status file when complete. The orchestrator reads
all status files before proceeding to Wave 3.

### Wave 3 — Synthesis

| Agent | Role |
|---|---|
| `synthesis-brief-writer` | Turn Wave 2 evidence into decision-ready artifacts |

`synthesis-brief-writer` receives the Decisions sections from all Wave 2
status files as upstream context. It produces the final artifact: Hidden Risk
Summary, Complexity Heat Map, or Decision Brief.

## Full Pipeline Diagram

```
Wave 1a:  web-researcher
            ↓ Source Manifest
Wave 1b:  extraction-planner
            ↓ Dispatch Plan
            ↓
Wave 2:   doc-indexer  doc-reader  caveat-extractor  cost-capacity-analyst  architecture-dependency-mapper
          (parallel — each works on its assigned sections from the Dispatch Plan)
            ↓ Context Packets (all Wave 2 status files)
            ↓
Wave 3:   synthesis-brief-writer
            ↓ Hidden Risk Summary / Complexity Heat Map / Decision Brief
```

## Status File Protocol

Every systems-thinking agent writes a status file after completing its wave
task. This is the inter-agent communication channel that fakoli-flow reads
between waves.

### File Location

```
docs/plans/agent-<name>-status.md
```

Use the agent's role name as `<name>` (e.g., `agent-web-researcher-status.md`,
`agent-caveat-extractor-status.md`). When multiple agents of the same type run
in one wave (e.g., two `caveat-extractor` instances), disambiguate with a
scope suffix: `agent-caveat-extractor-sla-status.md`.

### Format

See `docs/status-file-template.md` for the full template.

### Status Values

| Status | Meaning | Orchestrator action |
|---|---|---|
| `IN_PROGRESS` | Agent is working | Wait — do not dispatch next wave |
| `COMPLETE` | Task finished, all criteria met | Read decisions, proceed |
| `NEEDS_REVIEW` | Agent hit an ambiguity requiring human judgment | Surface to user — halt wave |
| `BLOCKED` | Agent cannot proceed without external input | Surface to user — halt wave |

**Writing rule:** Write `IN_PROGRESS` immediately when the task begins. Set
`COMPLETE` only when all extraction or synthesis work is finished.

### What the Orchestrator Reads

Between waves, fakoli-flow reads the status files of all just-completed agents
and:

1. Confirms every agent reached `COMPLETE` (halts if any is `BLOCKED` or
   `NEEDS_REVIEW`).
2. Extracts the "Files Modified" list for the critic gate (not applicable to
   systems-thinking agents since they do not modify project code).
3. Copies the "Decisions" section from each status file into the next wave's
   dispatch prompt as upstream context.

For systems-thinking agents, "Decisions" carries the key extraction findings —
section counts, critical caveats found, dispatch plan choices — so that
Wave 3's `synthesis-brief-writer` can prioritize without re-reading all
extraction outputs from scratch.

## What Each Agent Writes in "Decisions"

### web-researcher

- Number of sources found and how many are high-relevance
- Which topics have gaps (no official documentation found)
- Whether any sources require JavaScript rendering or authentication

### extraction-planner

- Material volume assessment (Small / Medium / Large / Very Large)
- Total extraction agents recommended and rationale
- Which agent types were assigned to which topic areas

### doc-indexer

- Number of documents mapped and total sections identified
- Which sections were flagged P1 (highest priority)
- Any structurally unusual documents that warrant extra attention

### doc-reader / caveat-extractor / cost-capacity-analyst / architecture-dependency-mapper

- Total findings count and how many are critical severity
- The 2-3 most important individual findings (for Wave 3 prioritization)
- Any topics where expected information was absent (gaps)

### synthesis-brief-writer

- Output artifact type produced (Hidden Risk Summary / Heat Map / Decision Brief)
- Top 3 risks or findings in the artifact
- Any unresolved questions that require human follow-up

## Compatibility Notes

- Systems-thinking agents do not modify project source code. The "Files
  Modified" section in their status files will typically list only their own
  status file and any output artifacts written to `docs/plans/`.
- The critic gate that fakoli-flow runs after code-writing waves does not apply
  to systems-thinking analysis workflows.
- Pattern remix workflows (`/pattern-remix`) involve a `pattern-remix-planner`
  agent that runs in place of Wave 2 extraction agents. It reads prior designs
  and produces a Pattern Remix Draft. `synthesis-brief-writer` still runs in
  Wave 3.
- `doc-indexer` can run as a Wave 1c step (after `extraction-planner`) when
  documents are pre-loaded locally — there is no strict requirement that it run
  in Wave 2.

## Further Reading

- `docs/agent-design-principles.md` — Why extraction and synthesis are
  separated; rules each agent type follows
- `docs/status-file-template.md` — Status file template for copy-paste
- `docs/output-contracts.md` — Structured output formats all agents produce
- `fakoli-flow/references/status-protocol.md` — Authoritative status file
  protocol (wave engine reading/writing rules, full examples)
- `fakoli-crew/docs/flow-protocol.md` — How fakoli-crew agents integrate with
  the same wave model
