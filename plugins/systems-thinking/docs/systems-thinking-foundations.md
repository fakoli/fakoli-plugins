# Systems Thinking Foundations

## What systems thinking is

Systems thinking is the discipline of understanding behavior that emerges from interactions between parts — the stuff that kills you in production that wasn't obvious in the design doc. A load balancer works correctly on its own. An autoscaler works correctly on its own. Put them together without understanding their feedback loop and you get oscillation — the autoscaler adds capacity, the load balancer distributes traffic, latency drops, the autoscaler removes capacity, latency spikes, the autoscaler adds capacity again. The failure wasn't in either component. It was in the interaction. If you've operated infrastructure long enough, you've watched this exact scenario play out — and it's invisible until it's not.

Infrastructure and architecture decisions fail this way consistently. Not because technologies are misunderstood, but because the interactions between them — cost mechanics that compound at scale, dependency chains nobody mapped, vendor assumptions that don't match your operational reality, failure propagation paths that weren't in the sales pitch — are invisible until you've already committed months and budget. First you get the rosy part, because that's what sells it. Then you discover everything below the waterline. This plugin makes those interactions visible before they become incidents — or invoices.

## Core concepts that drive this plugin

### Feedback loops and causal dependencies

Components influence each other in cycles, not lines. A routing policy change affects traffic distribution, which affects capacity utilization, which affects cost, which triggers a policy review. Understanding these loops — which are reinforcing (amplifying change) and which are balancing (resisting change) — determines whether an intervention stabilizes or destabilizes the system.

### Leverage points

Not all interventions are equal. Donella Meadows identified that changing system parameters (quotas, thresholds) has far less impact than changing information flows, feedback loop structures, or the goals the system optimizes for. The plugin's complexity mapping identifies where risk and complexity concentrate — the places where intervention matters most.

### Iceberg model

Surface events — an outage, a cost spike, a failed migration — are the visible tip. They're also what vendors show you: the clean demo, the competitive pricing, the success stories. Below the waterline sit the patterns (the recurring failures nobody warned you about), the structures (feedback loops, incentive misalignment, where the vendor's architecture couples to yours), and the mental models (the assumptions your team carries about how the system works — assumptions that may have come straight from the vendor's pitch deck, not from production experience). Extraction agents dig below the surface of documentation to find the structures and assumptions that actually drive what happens when you operate the thing at scale.

### Emergent properties

Some behaviors exist only in the interaction between components, not in any single component's specification. A vendor's API performs well in the demo but introduces a serialization bottleneck when composed with your event pipeline. A pricing model looks linear on the pricing page but compounds non-linearly at the scale breakpoints nobody told you about. A networking service works perfectly in a single region but creates asymmetric routing when you add the second region the vendor said was "supported." These properties cannot be found by reading one document — they emerge from cross-referencing multiple sources against operational context. This is the systems engineer's core skill: seeing the behavior that arises from composition, not from components in isolation.

### Stock and flow

Costs accumulate. Capacity depletes. Quotas fill. Understanding a system requires tracking both the current state (stock) and the rate of change (flow). A database that handles today's load may not handle next quarter's if ingestion rate outpaces index maintenance. The cost-capacity analyst surfaces these dynamics — not just what things cost now, but how costs behave as scale changes.

### Mental models and bounded rationality

Every prior design encodes decisions made under specific constraints — budget, timeline, team size, technology landscape. Those constraints may no longer hold. Pattern remix works because prior designs contain proven structural decisions worth reusing, but only after explicitly checking which assumptions still apply and which have expired.

### System boundaries

Every analysis must declare what is in scope and what is not. Without explicit boundaries, scope drifts silently, dependencies at the boundary get missed, and findings become unfalsifiable. Every output contract in this plugin includes a "scope reviewed" section for this reason.

## Concept-to-capability mapping

| Concept | In Practice | Plugin Capability | Agent / Skill |
| --- | --- | --- | --- |
| Reductionist analysis + holistic synthesis | Separate fact-gathering from conclusion-drawing to prevent premature simplification | Extraction/synthesis separation | All extraction agents (Phase 2) then synthesis agents (Phase 3) |
| Feedback loops and causal dependencies | Map how components influence each other — control planes, data planes, failure propagation | Dependency mapping | `architecture-dependency-mapper`, `/complexity-mapper` |
| Leverage points | Identify where small changes produce disproportionate effects and where complexity concentrates | Complexity heat mapping | `/complexity-mapper`, Complexity Heat Map output |
| Iceberg model | Surface what is below the visible layer: buried caveats, implicit assumptions, undocumented constraints | Deep extraction from source material | `caveat-extractor`, `doc-reader`, `/context-sharding` |
| Emergent properties | Find behaviors that exist only in the interaction between components | Interaction-risk extraction | `caveat-extractor`, Hidden Risk Summary output |
| Stock and flow | Track cost that compounds at scale, capacity that depletes under load, quotas that fill silently | Cost and capacity analysis | `cost-capacity-analyst`, `/complexity-mapper` |
| Mental models and bounded rationality | Prior designs encode constraints that may no longer hold — check before reusing | Pattern reuse with constraint checking | `pattern-remix-planner`, `/pattern-remix` |
| System boundaries | Explicit scope prevents drift and catches missed dependencies at edges | Scope declarations in every output | All output contracts (Scope Reviewed section) |

## Extensibility

Systems thinking includes concepts the plugin does not yet cover: systems archetypes (detecting "fixes that fail" or "shifting the burden" patterns in architectures), causal loop diagrams (visualizing dependency chains as feedback structures), resilience vs. efficiency tradeoffs (how optimization for one degrades the other), and delays as a source of oscillation (why systems overshoot and overcorrect).

These map to future capabilities: incident analysis (causal loops and archetype detection), capacity planning (stock/flow dynamics with delay modeling), and operational readiness assessment (resilience scoring). The architecture — narrow agents, structured output contracts, strict separation of extraction and synthesis — was designed to absorb these extensions without restructuring.

## Key references

The concepts in this document draw primarily from Donella Meadows (*Thinking in Systems: A Primer*), Peter Senge (*The Fifth Discipline*), and Jay Forrester's system dynamics work at MIT. For leverage points specifically, see Meadows' paper *Leverage Points: Places to Intervene in a System* (1999).
