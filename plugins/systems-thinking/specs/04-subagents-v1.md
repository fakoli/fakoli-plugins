# V1 Subagents

## 1. pattern-remix-planner

### Purpose

Convert prior examples, target state, and constraints into a high-quality draft plan.

### Inputs

- prior examples
- target state
- constraints
- anti-patterns

### Outputs

- proposed structure
- draft execution plan
- risks and unknowns

## 2. doc-indexer

### Purpose

Scan document structure quickly and map headings, sections, appendices, and likely caveat-heavy areas.

### Inputs

- one or more documents

### Outputs

- document map
- likely high-value sections
- caveat-rich areas to inspect

## 3. doc-reader

### Purpose

Read assigned sections and extract key technical claims, limits, dependencies, and implementation details.

### Inputs

- assigned files or sections

### Outputs

- extracted claims
- constraints
- implementation notes
- source anchors

## 4. caveat-extractor

### Purpose

Find limitations, quotas, exclusions, side effects, warning notes, and buried implementation traps.

### Inputs

- docs or extracted notes

### Outputs

- caveat list
- likely impact areas
- source anchors

## 5. cost-capacity-analyst

### Purpose

Highlight cost mechanics, throughput assumptions, scaling constraints, support burden, and capacity implications.

### Inputs

- docs, pricing notes, design assumptions

### Outputs

- cost and capacity findings
- hidden burden summary
- open questions

## 6. architecture-dependency-mapper

### Purpose

Map control-plane, data-plane, routing, ownership, and operational dependencies that affect delivery risk.

### Inputs

- design notes
- architecture docs
- extracted findings

### Outputs

- dependency map
- ownership concerns
- architectural choke points

## 7. synthesis-brief-writer

### Purpose

Turn extracted evidence into a clear decision-ready brief.

### Inputs

- outputs from extraction agents

### Outputs

- decision brief
- top risks
- unresolved questions
- recommended next checks

## Design note

In v1, these agents should be written so they can be composed manually or by a lightweight orchestrator rather than requiring a full autonomous control plane.
