# Previous Designs

Prior design docs, proposals, architecture notes, ADRs, and implementation plans.

## What goes here

- Past network or infrastructure designs
- Connectivity and migration proposals
- Architecture decision records (ADRs)
- Implementation plans and outlines
- Architecture reviews and RFCs

## How agents and skills use this folder

- **`pattern-remix-planner`** reads these files to identify reusable patterns and adapt prior approaches to new problems.
- **`pattern-remix`** skill gathers inputs from this folder as source material for generating first drafts.

When you run a Pattern Remix workflow, the planner scans these docs for structural patterns, constraints that were solved before, and implementation sequences worth reusing.

## File guidelines

- Markdown preferred.
- One design per file.
- Use descriptive filenames with dates.
- Include enough context that an agent can understand the problem being solved, not just the solution.

## Example filenames

- `2025-03-transit-gateway-hub-spoke.md`
- `2024-11-multi-region-dns-design.md`
- `2025-01-vpn-failover-adr.md`
