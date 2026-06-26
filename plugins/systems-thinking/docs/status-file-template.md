# Status File Template

Systems-thinking agents write a status file when dispatched by fakoli-flow or
any compatible orchestrator. The status file is the inter-agent communication
channel — the wave engine reads it between waves to confirm completion, extract
decisions for the next wave's dispatch prompt, and detect blockers.

**File path convention:** `docs/plans/agent-<name>-status.md`

Use the agent's role name as `<name>`. When multiple agents of the same type
run in the same wave, append a scope suffix to disambiguate:
`agent-caveat-extractor-sla-status.md`.

---

## Template

```markdown
# Agent <Name> Status

**Status:** IN_PROGRESS | COMPLETE | NEEDS_REVIEW | BLOCKED
**Wave:** <number>
**Timestamp:** <YYYY-MM-DD HH:MM UTC>

## Files Modified

- `docs/plans/agent-<name>-status.md` — this status file

## Files Read (not modified)

- `path/to/source.md` — why it was read

<!-- NOTE: "Files Read" is informational for downstream agents only.
     The wave engine reads only "Files Modified" and "Decisions".
     List files here so downstream agents know what context this agent had. -->

## Decisions

Key findings and choices downstream agents need to know:
1. Finding or decision with brief rationale

## Notes for Specific Agents

- **<agent-name>:** specific instructions or context for that agent

## Blockers (if BLOCKED)

What is preventing progress and what is needed to unblock.
```

---

## Status Values

| Status | Meaning | Next action |
|---|---|---|
| `IN_PROGRESS` | Agent is actively working | Downstream agents wait |
| `COMPLETE` | All work finished, criteria met | Wave engine proceeds |
| `NEEDS_REVIEW` | Ambiguity requiring human judgment | Orchestrator halts wave |
| `BLOCKED` | Cannot proceed without external input | Orchestrator resolves |

**Writing discipline:**

1. Write `IN_PROGRESS` as the first thing you do, before reading any files.
   This signals to the orchestrator that you are active.
2. Set `COMPLETE` only when all extraction or synthesis work is done and
   output artifacts are written.
3. Set `BLOCKED` or `NEEDS_REVIEW` honestly. Do not attempt workarounds —
   surface the problem and stop.

---

## What to Write in "Decisions"

The "Decisions" section is copied verbatim into the next wave's dispatch
prompt. Write what downstream agents need to know — not a narrative of what
you did.

**Good decisions entries:**

- Factual, concrete, actionable
- Include counts, severities, and specific section references
- Flag any gaps or absent information the next agent should know about

**What not to write:**

- Summaries of your own process ("I read 5 files and found…")
- Redundant information the next agent will discover by reading your output
- Uncertainty disguised as a decision ("probably fine")

### Per-agent guidance

**web-researcher:**
```
- Found N sources; M are high-relevance official documentation
- Gap: [topic] — no official vendor docs found, only community posts
- Gap: [pricing page] — JavaScript-rendered, content not extractable
```

**extraction-planner:**
```
- Material volume: Medium (12 sections across 3 documents)
- Dispatching 4 extraction agents: 2 caveat-extractor, 1 cost-capacity-analyst,
  1 architecture-dependency-mapper
- Sections with highest caveat density: [section names]
```

**doc-indexer:**
```
- Mapped N documents, M total sections
- P1 sections: [names] — highest value for extraction agents
- Structural gap: [document] has no table of contents; structure is irregular
```

**doc-reader / caveat-extractor / cost-capacity-analyst / architecture-dependency-mapper:**
```
- N findings total: X critical, Y significant, Z informational
- Critical finding: [brief description] — source: [file:line]
- Critical finding: [brief description] — source: [file:line]
- Gap: [expected limit type] not documented — risk: [brief description]
```

**synthesis-brief-writer:**
```
- Produced: [Hidden Risk Summary / Complexity Heat Map / Decision Brief]
- Top finding: [brief description]
- Top finding: [brief description]
- Unresolved: [question] — requires human input before proceeding
```

---

## Example: caveat-extractor Status File

```markdown
# Agent caveat-extractor Status

**Status:** COMPLETE
**Wave:** 2
**Timestamp:** 2026-04-02 14:33 UTC

## Files Modified

- `docs/plans/agent-caveat-extractor-sla-status.md` — this status file

## Files Read (not modified)

- `reference/vendor_docs/managed-db-sla.md` — assigned section: SLA terms
- `reference/vendor_docs/managed-db-sla.md` — assigned section: exclusions appendix
- `reference/vendor_docs/managed-db-pricing.md` — cross-reference for cost caveats

## Decisions

- 17 caveats found: 4 critical, 9 significant, 4 informational
- Critical: 99.99% SLA excludes planned maintenance windows — source: sla.md:L38
- Critical: Failover SLA clock starts only after automated detection, not after
  actual failure — detection lag undocumented — source: sla.md:L112
- Critical: "Automatic backups" do not include transaction logs by default;
  point-in-time recovery requires separate configuration — source: sla.md:L201
- Gap: No documented limit on maximum database size — vendor confirmed
  "contact sales" for sizes above 64TB

## Notes for Specific Agents

- **synthesis-brief-writer:** The SLA exclusion for planned maintenance is the
  highest-impact finding. The vendor's uptime graph counts this as 100% but
  customers will experience it as downtime. Prioritize in the risk summary.
```

---

## Further Reading

- `docs/flow-protocol.md` — How the 3-tier pipeline maps to fakoli-flow waves
- `fakoli-flow/references/status-protocol.md` — Authoritative protocol
  definition (wave engine reading/writing rules)
