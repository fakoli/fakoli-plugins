# systems-thinking

<p align="center">
  <img src="iceberg-banner.png" alt="Systems Thinking Plugin — the iceberg of hidden complexity" width="800">
</p>

A Claude Code plugin that applies systems thinking to infrastructure and architecture decisions — surfacing what vendors don't show you, what consultants gloss over, and what only becomes visible when you're in production with no exit.

This marketplace copy lives at `plugins/systems-thinking` in
`fakoli/fakoli-plugins`. It preserves the upstream repository documentation
while adapting install and path references for the marketplace layout.

## Provenance

The original standalone source repository is
`https://github.com/fakoli/systems-thinking-plugin`. This marketplace package
preserves that upstream history and attribution while publishing the installable
plugin identity as `systems-thinking`.

Migration note: this marketplace copy preserves the upstream documentation,
agent, skill, hook, and test surfaces while adapting paths and plugin identity
for `plugins/systems-thinking`.

## Why this exists

Systems engineers think differently. Whether the problem is a network design, a cloud migration, a storage architecture, or a vendor evaluation — the discipline is the same: understand what a system does well, understand what it *doesn't* do well, and build pathways to close the gap before you're in production wondering why nobody told you.

The pattern repeats across every technology and every era. First you get the rosy part, because that's what sells it. The vendor demo works. The POC looks clean. The pricing page makes sense. Then you commit, and you discover what was below the waterline the whole time — the quotas that bite at scale, the cost mechanics that compound non-linearly, the dependencies between services that nobody mapped, the caveats buried in page 47 of the docs.

This is the iceberg problem. The visible tip is what gets sold. The massive hidden mass below is what you actually have to operate. A systems engineer's job has always been to look below that waterline — to ask the questions that the sales pitch doesn't invite, to read the docs that the POC doesn't exercise, to map the dependencies that only matter when something fails. Whether you're evaluating a new cloud service, planning a multi-region architecture, designing a storage tier, or provisioning an OS at scale — the methodology is the same.

This plugin encodes that methodology into reusable workflows:

- **Extract before you synthesize.** Separate the work of gathering what a source *actually says* from the work of interpreting it. Extraction agents pull out every technical claim, limitation, cost mechanic, and dependency — faithfully, with source anchors. It's the difference between "what the vendor's doc claims" and "what you'll actually pay for." Synthesis agents connect those findings into decisions only after extraction is complete.
- **Preserve what you find.** Every finding traces back to a specific file, section, or page. Not "broadly available" when it says "us-east-1 only." Not "supports X" when the doc says "supports X when Y is also true." No collapsed nuance. The caveats are where the real decisions live.
- **Reuse what worked.** Prior designs, architecture decisions, and proven patterns are first-class inputs. The plugin adapts them to new constraints rather than starting from scratch, while flagging where the old context no longer applies. Lessons that got lost in the last vendor's sales pitch get carried forward.
- **Produce artifacts that travel.** Outputs follow structured contracts (Decision Briefs, Risk Summaries, Complexity Heat Maps) designed for design reviews, stakeholder conversations, and handoffs — not confident guesses dressed up as analysis.

Understanding what systems *don't* do well is as important as understanding what they do well. This plugin builds the discipline of looking below the waterline into reusable workflows — so the gaps surface before you've committed, not after. See `docs/systems-thinking-foundations.md` for the full conceptual mapping.

## Install

```text
/plugin marketplace add fakoli/fakoli-plugins
/plugin install systems-thinking
```

For local marketplace development, work from the repository root and use
`plugins/systems-thinking` as the plugin path.

## Workflows

Five workflows, each modeling a different phase of how a systems engineer navigates a problem:

### `/complexity-mapper`

The full below-the-waterline scan. When you have a design, a vendor proposal, or an architecture doc and you need to know where complexity is hiding — cost traps, scaling cliffs, dependency chains, operational burden that isn't in the pitch deck. Runs extraction agents in parallel, then synthesizes findings into a **Complexity Heat Map** and **Hidden Risk Summary**.

### `/context-sharding`

When the material is too large for a single pass — vendor doc packages, sprawling repos, multi-service specs. A systems engineer doesn't read 200 pages linearly and hope to catch everything. This workflow breaks material into focused chunks, extracts independently from each, and catches what a single-pass read would miss. Produces **Context Packets** with findings, caveats, and source anchors.

### `/pattern-remix`

Systems engineers don't start from scratch when a proven pattern exists. This workflow takes a known-good design and adapts it to new constraints — mapping what transfers, what needs to change, and what assumptions from the old context no longer hold. Produces a **Pattern Remix Draft** with source tracing and divergence risks.

### `/decision-brief`

Package extracted findings into a stakeholder-ready **Decision Brief** with evidence, options, risks, and next steps. The artifact that travels from the engineer's analysis to the review board's decision.

### `/architecture-risk-review`

Focused risk assessment of a specific architecture — failure modes, hidden dependencies, single points of failure, blast radius, operational survivability. The questions a systems engineer asks before signing off on a design. Produces a **Hidden Risk Summary** with architectural focus.

## How it works

Here's what a typical `/complexity-mapper` session looks like in Claude Code. The same pipeline pattern applies to all workflows — the agents and outputs change, but the rhythm is the same.

### 1. Invoke the skill

```
You: /complexity-mapper

     We're evaluating a migration from self-managed PostgreSQL to a
     managed database service. The vendor says it handles replication,
     failover, and backups automatically. I want to know what they're
     not telling us before we commit.
```

You describe what you're evaluating and what concerns you. The skill takes it from there.

### 2. Document indexing (~10 seconds)

Claude invokes the `doc-indexer` agent, which scans your provided materials and maps the structure — headings, sections, high-value areas, caveat-rich zones:

```
  doc-indexer scanning 4 documents...

  Document: vendor-proposal.md
    9 sections mapped, 3 flagged as high-value
    Caveat-rich areas: SLA exclusions (L38), Storage pricing tiers (L97)

  Document: migration-runbook.md
    6 sections mapped, 2 flagged
    Gap identified: no rollback procedure documented

  Prioritized Reading List:
  | Priority | Section                | Recommended Agent              |
  |----------|------------------------|---------------------------------|
  | P1       | SLA terms & exclusions | caveat-extractor                |
  | P1       | Storage & IOPS pricing | cost-capacity-analyst           |
  | P1       | Failover architecture  | architecture-dependency-mapper  |
  | P2       | Backup retention       | doc-reader                      |
```

### 3. Source discovery (when external docs are needed)

If the doc-indexer identifies gaps — vendor quotas not in your files, pricing pages you don't have locally — Claude invokes the `web-researcher` to find them:

```
  web-researcher discovering sources for 3 topics...

  Source Manifest:
  | # | Title                    | URL                           | Relevance |
  |---|--------------------------|-------------------------------|-----------|
  | 1 | Service Quotas & Limits  | docs.vendor.com/limits/...    | High      |
  | 2 | IOPS Pricing Calculator  | vendor.com/pricing/...        | High      |
  | 3 | Known Issues - Failover  | docs.vendor.com/known/...     | High      |

  Gaps: Pricing calculator requires JavaScript (not fully extractable)
```

Claude presents the Source Manifest for your review before proceeding. You can add or remove sources.

### 4. Dispatch planning (~10 seconds)

The `extraction-planner` looks at the total volume of material and decides how to parallelize the work — how many extraction agents to spawn and what scoped instructions each gets:

```
  extraction-planner assessing material volume...

  Dispatch Plan:
  - Total sections: 18
  - Material volume: Medium
  - Recommended: 4 extraction agents

  | Agent # | Type                          | Focus Scope                       |
  |---------|-------------------------------|-----------------------------------|
  | 1       | caveat-extractor              | SLA exclusions, known limitations |
  | 2       | caveat-extractor              | Operational constraints, quotas   |
  | 3       | cost-capacity-analyst         | Storage, IOPS, data transfer      |
  | 4       | architecture-dependency-mapper | Failover, replication, backups    |
```

This step prevents the overload that happens when a single agent tries to process too much material at once. Each agent gets bounded, focused instructions.

### 5. Parallel extraction (~30-90 seconds)

Claude launches the extraction agents in parallel. Each one works on its assigned sections and produces findings with source anchors:

```
  Launching 4 extraction agents in parallel...

  ✓ caveat-extractor (SLA): 14 caveats found (4 critical)
  ✓ caveat-extractor (ops): 11 caveats found (3 critical)
  ✓ cost-capacity-analyst: 9 pricing items confirmed, 3 unknown
  ✓ architecture-dependency-mapper: 8 dependencies, 2 SPOFs identified
```

### 6. Synthesis (~30-60 seconds)

The `synthesis-brief-writer` combines all extraction outputs into structured artifacts:

```
Complexity Heat Map

| Area                      | Type       | Likelihood | Impact | Visibility |
|---------------------------|------------|------------|--------|------------|
| IOPS throttling at tier boundary | Scaling | High  | High   | Hidden     |
| Failover window not in SLA      | Quota   | Medium | High   | Hidden     |
| Cross-region replication lag     | Dependency | High | Medium | Hidden   |
| Backup restore time undocumented | Operational | High | High | Hidden   |

Top 3 Risks:
1. SLA excludes maintenance windows — 99.99% uptime doesn't count planned downtime
2. IOPS pricing jumps 4x at the threshold their sizing tool recommends
3. "Automatic failover" requires manual DNS update in multi-region configurations
```

The full output includes source anchors for every finding, severity ratings, unresolved questions, and recommended next steps — ready for a design review or stakeholder conversation.

### What to expect

- **Total time:** 2-5 minutes for a typical analysis, depending on material volume and whether web research is needed
- **Token usage:** Varies with material size. Small analyses (≤5 sections) use minimal tokens. Larger research across multiple vendors or services will use more.
- **User interaction:** The skill runs mostly autonomously. You'll be asked to review the Source Manifest (if web research fires) and may be asked clarifying questions if the material is ambiguous.
- **Output location:** Results are delivered inline in the conversation. Use `/decision-brief` afterward to package findings for stakeholders.

For more worked examples, see `examples/usage-scenarios.md`.

## Agents

The visible tip of the iceberg is what the vendor shows you. Everything below the waterline is what these agents find.

Nine subagents with narrow, auditable roles organized into three tiers — discovery agents cast the net, extraction agents pull out what matters, and synthesis agents connect it into decisions:

### Orchestration Agents (Discovery + Planning)

| Agent | Role | Model |
|-------|------|-------|
| `web-researcher` | Discover source material from web and local files | Sonnet |
| `extraction-planner` | Assess material volume, produce Dispatch Plans | Haiku |

### Extraction Agents (Fast + Parallel)

| Agent | Role | Model |
|-------|------|-------|
| `doc-indexer` | Map document structure, flag high-value sections | Haiku |
| `doc-reader` | Extract technical claims, limits, dependencies | Haiku |
| `caveat-extractor` | Find buried limitations, quotas, traps | Sonnet |
| `cost-capacity-analyst` | Surface cost mechanics, scaling constraints | Sonnet |
| `architecture-dependency-mapper` | Map control/data-plane dependencies | Sonnet |

### Synthesis Agents (High-Quality Output)

| Agent | Role | Model |
|-------|------|-------|
| `pattern-remix-planner` | Adapt prior work to new problems | Opus |
| `synthesis-brief-writer` | Turn extracted evidence into decision briefs | Opus |

**Pipeline flow for research-heavy workflows:**

```
web-researcher → doc-indexer → extraction-planner → [parallel extractors] → synthesis-brief-writer
   (discover)    (map structure)  (plan dispatch)    (scoped extraction)       (synthesize)
```

Only `web-researcher` has web access (WebSearch + WebFetch). All other agents work on pre-discovered material via Read, Grep, and Glob. The `extraction-planner` prevents extractor overload by right-sizing parallelization before agents are spawned.

## Reference material

Drop source documents into `reference/` subdirectories to give the agents real material to work with:

| Directory | Contents |
|-----------|----------|
| `previous_designs/` | Prior design docs, ADRs, architecture notes |
| `vendor_docs/` | Vendor documentation, pricing, quotas, SLAs |
| `prompts/` | Prompts and patterns that have worked before |
| `examples/` | Example outputs showing the quality bar you want |

Even one vendor doc or one prior design is enough to start.

## Output contracts

All outputs follow structured formats defined in `docs/output-contracts.md`:

- **Hidden Risk Summary** — scope, top risks, impact areas, assumptions, unresolved questions
- **Complexity Heat Map** — complexity areas ranked by severity and confidence
- **Decision Brief** — decision frame, options, evidence, risks, next steps
- **Pattern Remix Draft** — reusable patterns, adaptations, constraints, known risks
- **Context Packet** — extracted findings with caveats and source anchors

Every finding includes source anchors so you can verify claims against the original material.

## Testing

**Local deterministic checks:** Unit and contract tests can run from the
marketplace checkout after changing into the plugin directory.

```bash
cd plugins/systems-thinking
uv run pytest tests/unit tests/contracts -v
```

The upstream test guide, Python test files, eval YAML cases, graders, and
fixtures are preserved under `plugins/systems-thinking/tests/`.

Utility/helper scripts for indexing, sharding, prompt assembly, orchestration,
aggregation, and output validation are preserved under `plugins/systems-thinking/utils/`.

Static assets are preserved in the same relative locations used by upstream:
the README banner at `iceberg-banner.png` and orchestration diagrams under
`docs/images/`.

**Evals (manual, local only):** Eval tests invoke the Claude CLI and require it
on your PATH. These are not run by the marketplace validation workflow — run
them locally when validating agent behavior.

```bash
# Run all evals
uv run pytest tests/evals -v -m eval --timeout=300

# Run a single eval
uv run pytest tests/evals -v -k complexity_mapper

# Dry-run (validate case files without executing)
python tests/evals/harness.py --dry-run
```

## Works with fakoli-flow

This plugin is compatible with the **fakoli-flow** orchestration plugin. When
both are installed, fakoli-flow can dispatch systems-thinking agents in waves —
running discovery agents, then parallel extraction agents, then synthesis —
with the wave engine managing sequencing, status tracking, and critic gates.

### Wave mapping

| Wave | Agents | Purpose |
|---|---|---|
| Wave 1 | `web-researcher`, `extraction-planner` | Discover source material, produce Dispatch Plan |
| Wave 2 | `doc-indexer`, `doc-reader`, `caveat-extractor`, `cost-capacity-analyst`, `architecture-dependency-mapper` | Parallel extraction — each agent works on its assigned scope |
| Wave 3 | `synthesis-brief-writer` | Turn Wave 2 evidence into decision artifacts |

Agents communicate between waves by writing status files to
`docs/plans/agent-<name>-status.md`. The wave engine reads these after each
wave to confirm completion and pass key decisions to the next wave's dispatch
prompt.

See `docs/flow-protocol.md` for the full wave mapping and status file format,
and `docs/status-file-template.md` for the template agents use.

## Further reading

- `docs/systems-thinking-foundations.md` — Conceptual foundations and concept-to-capability mapping
- `docs/output-contracts.md` — Output format definitions
- `docs/agent-design-principles.md` — Agent design rationale
- `docs/repo-conventions.md` — Naming and structure conventions
- `docs/flow-protocol.md` — fakoli-flow wave mapping and status file protocol
- `docs/status-file-template.md` — Status file template for wave-based execution
- `docs/images/` — Static orchestration diagrams referenced by design docs
- `examples/usage-scenarios.md` — Worked examples with agent flows
- `iceberg-banner.png` — README banner image
- `MIGRATION.md` — Upstream-to-marketplace path and runtime-assumption adaptations
- `utils/` — Deterministic helper scripts for indexing, sharding, prompt building, orchestration, aggregation, and validation
- `COMPATIBILITY_NOTES.md` — Cursor compatibility notes
