# Named Workflows

## 1. Pattern Remix

### Definition

Use prior proven work, target-state goals, and explicit constraints to generate high-quality first drafts and execution plans for new but related problems.

### Best use cases

- design doc drafting
- implementation plan drafting
- adapting prior Terraform or module patterns
- converting prior architecture patterns into new proposals

### Typical inputs

- previous design docs
- prior implementation examples
- desired target state
- constraints
- anti-patterns or things to avoid

### Typical outputs

- first draft proposal
- implementation plan
- rollout checklist
- known risk section

## 2. Complexity Mapper

### Definition

Gather documentation, architecture assumptions, cost and capacity constraints, operational considerations, and implementation caveats to surface hidden complexity, side effects, risks, dependencies, and likely project blow-up points.

### Best use cases

- vendor evaluation
- cloud and network connectivity design
- architecture reviews
- migration planning
- buried caveat and quota discovery

### Typical inputs

- vendor docs
- internal architecture docs
- cost notes
- capacity assumptions
- operational ownership boundaries
- constraints and non-goals

### Typical outputs

- hidden risk summary
- complexity heat map
- missing questions list
- decision brief
- implementation burden summary

## 3. Context Sharding

### Definition

Split large bodies of input across smaller parallel subagents so narrower agents can extract structure, summaries, caveats, constraints, and signals before a primary reasoning agent synthesizes them.

### Best use cases

- large documentation sets
- large codebases
- vendor documentation review
- cross-source comparison
- quota, limitation, and caveat extraction

### Typical inputs

- many docs
- large repos
- architecture notes
- reference prompts
- implementation examples

### Typical outputs

- doc maps
- index summaries
- extracted caveats
- distilled source packets
- synthesis-ready findings

## Relationship between workflows

- Context Sharding reduces large inputs into focused packets.
- Complexity Mapper uses those packets to surface hidden complexity.
- Pattern Remix uses prior patterns and constraints to produce first drafts.
