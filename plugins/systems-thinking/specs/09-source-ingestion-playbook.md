# Source Ingestion Playbook

## Goal

Give Claude Code enough real material to infer a better package structure before it starts scaffolding.

## Good things to add to the seed folders

### `seed/previous_designs/`

Add:

- prior design docs
- old proposals
- implementation plans
- architecture notes
- decision records

### `seed/vendor_docs/`

Add:

- exported docs
- copied markdown notes from vendor pages
- pricing notes
- limitation summaries
- quota references

### `seed/reference_prompts/`

Add:

- prompts that worked well before
- examples of how you frame constraints
- examples of how you frame anti-patterns
- notes on how you ask for plans before execution

### `seed/examples/`

Add:

- sample output you liked
- examples of good decision briefs
- examples of risk summaries
- examples of diagrams or scorecards you want the package to support

## Suggested file hygiene

- prefer Markdown over PDFs when possible
- keep filenames descriptive
- include dates if helpful
- use one topic per file when possible
- add a short note at the top explaining why the file matters
