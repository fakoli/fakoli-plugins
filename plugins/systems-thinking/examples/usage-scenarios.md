# Usage Scenarios

Five worked examples showing how to use the systems-thinking-plugin in practice. Each scenario describes the situation, which skill to invoke, what happens under the hood, and what outputs to expect.

---

## Scenario 1: Cloud connectivity option review

### Situation

A team is evaluating multiple connectivity approaches between cloud providers (e.g., dedicated interconnects, SD-WAN overlays, VPN tunnels). They need to understand networking tradeoffs, hidden costs, operational burden, and likely project risks before committing to an approach.

### Recommended skill

Start with **context-sharding** to break down the vendor documentation, then run **complexity-mapper** to surface hidden issues, then **decision-brief** to package findings.

### What happens under the hood

1. **context-sharding** invokes the **doc-indexer** agent, which scans all source documents (vendor PDFs, internal architecture notes, pricing sheets) and produces a document map identifying high-value sections and caveat-heavy areas.

2. **context-sharding** assigns scopes to extraction agents running in parallel:
   - **doc-reader** extracts technical claims, limits, and dependencies from each vendor's networking documentation.
   - **caveat-extractor** pulls out limitations, quotas, exclusions, and buried operational traps.
   - **cost-capacity-analyst** highlights pricing mechanics, throughput assumptions, scaling constraints, and support burden.
   - **architecture-dependency-mapper** maps control-plane, data-plane, routing, and ownership dependencies.

3. Each extraction agent produces a **Context Packet** with findings, caveats, confidence notes, and source anchors.

4. **complexity-mapper** consumes all Context Packets and produces a **Complexity Heat Map** and **Hidden Risk Summary**, identifying where implementation difficulty concentrates and what risks are non-obvious.

5. **decision-brief** takes the extracted evidence and complexity findings and produces a **Decision Brief** with options considered, evidence summary, inferred concerns, top risks, recommended next checks, and unresolved questions.

### Expected outputs

- **Context Packets** (one per extraction agent per source) — raw findings with source anchors
- **Complexity Heat Map** — ranked complexity areas with severity and confidence
- **Hidden Risk Summary** — non-obvious risks, impact areas, assumptions
- **Decision Brief** — stakeholder-ready summary of the connectivity decision

### How to invoke

```
/complexity-mapper

Evaluate the following cloud connectivity options for our multi-cloud environment.
Sources are in reference/vendor_docs/ and reference/previous_designs/.
Constraints: must support BGP, budget ceiling is $X/month, ops team is 2 people.
```

---

## Scenario 2: Vendor documentation risk scan

### Situation

A vendor's pitch deck and technical documentation look clean, but the team suspects there are buried caveats, quota limitations, region restrictions, operational constraints, and support burden that are not obvious from a surface reading.

### Recommended skill

**complexity-mapper** is the primary skill. If the documentation set is large, start with **context-sharding** first.

### What happens under the hood

1. If the documentation is large (50+ pages or multiple documents), **context-sharding** runs first: **doc-indexer** maps the structure, then **doc-reader** and **caveat-extractor** work assigned sections in parallel.

2. If the documentation is manageable (one document, under 50 pages), skip sharding and go directly to extraction: **doc-reader** and **caveat-extractor** process the full document.

3. **caveat-extractor** is the most important agent in this scenario. It specifically looks for:
   - Soft limits described as hard limits
   - Features described as "supported" that require manual configuration
   - Regional availability gaps
   - Support tier requirements for critical features
   - Pricing that changes at scale breakpoints

4. **cost-capacity-analyst** reviews pricing and scaling sections for hidden cost mechanics.

5. **synthesis-brief-writer** produces a **Hidden Risk Summary** combining all findings, with each risk anchored to the specific page or section where it was found.

### Expected outputs

- **Context Packets** — raw extractions with source anchors
- **Hidden Risk Summary** — buried risks, impact areas, assumptions about vendor claims
- A list of **questions to ask the vendor** — generated from gaps and ambiguities found during extraction

### How to invoke

```
/complexity-mapper

Scan the vendor documentation in reference/vendor_docs/vendor-x/ for hidden risks.
Focus on: quotas, regional limitations, support requirements, pricing at scale.
We are evaluating this vendor for production network connectivity.
```

---

## Scenario 3: Reusing prior patterns for a new design

### Situation

There is a known-good prior implementation (e.g., a hub-spoke network design, a Terraform module structure, a migration playbook) and a new target problem that is similar but not identical. The team wants a strong first draft that reuses what worked before while adapting to new constraints.

### Recommended skill

**pattern-remix** is the primary skill.

### What happens under the hood

1. **doc-reader** extracts the structure, decisions, constraints, and implementation details from the prior design artifacts in `reference/previous_designs/`.

2. **pattern-remix-planner** (a synthesis agent) receives:
   - The extraction results from the prior design
   - The user-provided target state and constraints
   - Any anti-patterns or things to avoid

3. **pattern-remix-planner** produces a **Pattern Remix Draft** that:
   - Identifies which elements from the prior work transfer directly
   - Identifies which elements need adaptation and why
   - Proposes a concrete approach for the new problem
   - Lists implementation steps in order
   - Flags risks introduced by the adaptation (things that worked in the prior context but might not work in the new one)

### Expected outputs

- **Context Packet** from prior design extraction — what was reusable and what was context-specific
- **Pattern Remix Draft** — the adapted design with implementation steps, constraints, and known risks

### How to invoke

```
/pattern-remix

Prior work: reference/previous_designs/hub-spoke-aws-gcp/
Target: Extend the hub-spoke model to include Azure with a shared transit layer.
Constraints: Azure does not support our current BGP community tagging scheme.
Avoid: Do not replicate the manual failover process from the original design.
```

---

## Scenario 4: Big repo orientation

### Situation

A repository is too large for one clean reasoning pass. The user (often new to the codebase or revisiting after time away) wants fast orientation: what is in the repo, where the important parts are, where complexity hides, and what to inspect next.

### Recommended skill

**context-sharding** is the primary skill, followed optionally by **complexity-mapper** for deeper analysis of flagged areas.

### What happens under the hood

1. **doc-indexer** scans the repository structure — directories, key files, README files, config files, module boundaries — and produces a document map.

2. **context-sharding** assigns sections of the repo to **doc-reader** agents working in parallel. Each reader covers a module or directory and produces a Context Packet summarizing:
   - What the module does
   - Key dependencies
   - Notable patterns or conventions
   - Likely complexity areas
   - Things that look unusual or inconsistent

3. **synthesis-brief-writer** merges all Context Packets into a **Decision Brief** structured as an orientation document:
   - Repo map (directory structure with annotations)
   - Key modules and their purposes
   - Identified complexity hot spots
   - Recommended inspection targets for deeper analysis

4. Optionally, the user can then run **complexity-mapper** on the flagged hot spots to get a full **Complexity Heat Map** and **Hidden Risk Summary** for specific areas.

### Expected outputs

- **Document map** — repo structure with annotations on what each area contains
- **Context Packets** — per-module findings from parallel extraction
- **Orientation Brief** (Decision Brief format) — key modules, complexity areas, recommended next inspection targets

### How to invoke

```
/context-sharding

Orient me to this repository. I need to understand:
- What the major modules do
- Where complexity is likely hiding
- What I should inspect first

Start with the top-level structure and go one level deep into each major directory.
```

---

## Scenario 5: Platform migration evaluation (full pipeline with web research)

### Situation

Your team is evaluating a migration from a self-managed service to a vendor's managed platform — could be a database, a message queue, a container orchestration platform, or any managed service. The vendor's pitch looks clean, the demo worked, and the pricing page makes sense. But you've been through enough of these to know: the real costs and constraints don't show up until you're committed. You want the full picture before signing anything.

The material doesn't all exist locally — you need the agents to research the vendor's documentation from the web alongside your internal architecture docs.

### Recommended skill

**complexity-mapper** with web research enabled. This exercises the full pipeline: `web-researcher` → `doc-indexer` → `extraction-planner` → parallel extractors → `synthesis-brief-writer`.

### What happens under the hood

1. **doc-indexer** maps any local materials you've provided (vendor proposals, internal architecture docs, migration plans).

2. **web-researcher** discovers external sources — the vendor's quota pages, pricing calculators, SLA documents, known issues pages, community forums with production war stories. Produces a **Source Manifest** listing every source found, with relevance ratings and gaps (e.g., "pricing calculator requires JavaScript — not fully extractable").

3. **extraction-planner** assesses the total volume — 20+ sections across vendor docs and internal materials — and produces a **Dispatch Plan**: "spawn 3 caveat-extractors (platform limits, operational constraints, migration risks), 1 cost-capacity-analyst, 1 architecture-dependency-mapper." Each agent gets scoped instructions specifying exactly which sections to read and what to focus on.

4. Extraction agents run in parallel (~60-90 seconds). Each produces findings with source anchors:
   - Caveat-extractors surface hard limits buried in quota tables, SLA exclusions that carve out the scenarios you care about most, behavioral differences between the managed version and what you're running today, and migration constraints the vendor's sales team didn't mention.
   - Cost-capacity-analyst confirms base pricing and flags hidden multipliers — the per-operation fees that compound at your scale, the data transfer costs between components, the premium tier you'll need for the features the demo showed.
   - Architecture-dependency-mapper identifies what breaks if the managed service goes down, what new dependencies you're inheriting, and where your rollback path has gaps.

5. **synthesis-brief-writer** combines all findings into a **Complexity Heat Map** and **Hidden Risk Summary**, cross-referencing across agents to surface compound risks — the places where two individually manageable constraints combine into a serious problem.

### Expected outputs

- **Source Manifest** — catalog of all web and local sources discovered
- **Dispatch Plan** — how extraction was parallelized and why
- **Context Packets** — raw findings per extraction agent with source anchors
- **Complexity Heat Map** — ranked complexity areas (quotas, cost traps, dependencies, scaling cliffs)
- **Hidden Risk Summary** — top risks with evidence, compound failure scenarios, unresolved questions
- Optionally, feed everything into **decision-brief** for a stakeholder-ready package

### How to invoke

```
/complexity-mapper

We're evaluating migrating from self-managed PostgreSQL to [Vendor]'s
managed database platform. Analyze their documentation for hidden risks.

Internal docs: reference/vendor_docs/vendor-proposal.md
Architecture: reference/previous_designs/current-db-architecture.md

Focus on: SLA exclusions, pricing at our scale (2TB, 50K IOPS),
failover behavior, backup/restore guarantees, and migration risks.
```

### What makes this scenario different

This is the full pipeline — web research, dispatch planning, parallel extraction, and synthesis all working together. The key insight is that the extraction-planner prevents the overload that would happen if a single caveat-extractor tried to process 20+ sections of vendor documentation at once. By scoping each agent to a specific topic area and bounded set of sections, the extraction stays fast and focused.

---

## General notes

- These scenarios can be combined. A vendor evaluation might start with context-sharding, move to complexity-mapper, and finish with decision-brief.
- The skills are designed to be invoked individually. You do not need to run the full chain every time.
- If the source material is small enough to fit in a single context window, you can skip context-sharding and go directly to the relevant analysis skill.
- Always populate `reference/` with your source material before invoking skills. The agents read from those directories.
