# Agent Design Principles

## Core principles

### 1. Separate extraction from synthesis

Extraction agents gather facts, caveats, structure, limits, and references.
Synthesis agents connect those findings into a decision-ready artifact.

### 2. Keep roles narrow

Each subagent should have one primary job and clear boundaries.

### 3. Preserve source anchors

Whenever possible, outputs should reference the file, section, or source location that produced the finding.

### 4. Prefer structured outputs

Use predictable headings or simple schemas so downstream agents can consume results cleanly.

### 5. Avoid hallucinated certainty

Agents should call out ambiguity, missing data, and low-confidence inferences.

### 6. Optimize for senior engineering judgment

Outputs should help evaluate implementation burden, hidden risk, and decision quality.

## Extraction agent rules

- extract, do not over-interpret
- preserve nuance where possible
- return caveats and counterexamples
- include unknowns
- avoid making final recommendations unless explicitly asked

## Synthesis agent rules

- distinguish evidence from inference
- call out assumptions explicitly
- include unresolved questions
- avoid overselling certainty
- produce outputs that are useful in design reviews and stakeholder conversations
