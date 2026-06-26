# TODO

Tracked work for systems-thinking-plugin. Items are roughly prioritized within each section.

## Utilities & Determinism

- [ ] **Data fetching utilities** — Build helper functions that fetch external data (vendor pricing pages, API docs, release notes) and normalize it into clean Markdown for agent consumption. Reduce variability in how raw sources get ingested.
- [ ] **Document parsing pipeline** — Structured parsers for common input formats (PDF → Markdown, HTML → Markdown, JSON/YAML config → annotated Markdown). Agents should receive consistent, pre-processed input regardless of source format.
- [ ] **Output normalization** — Post-processing functions that enforce output contract structure deterministically. Validate that agent outputs conform to the schema in `docs/output-contracts.md` before presenting to the user.
- [ ] **Caching layer** — Cache fetched and parsed documents locally so repeated analysis of the same source doesn't re-fetch or re-parse. Key by content hash + fetch date.
- [ ] **Diff-aware ingestion** — When a vendor doc is updated in `reference/vendor_docs/`, detect what changed since the last analysis and surface the delta rather than re-processing the full document.

## Memory & Context Persistence

- [ ] **Session memory** — Persist key findings, decisions, and risk assessments across sessions so follow-up analysis can build on prior work instead of starting from scratch.
- [ ] **Analysis history** — Track which documents have been analyzed, what was found, and when. Allow agents to reference prior analysis runs (e.g., "last time we reviewed this vendor doc, we found these caveats").
- [ ] **Cross-session risk registry** — Maintain a running registry of identified risks, their status (open/mitigated/accepted), and which analyses surfaced them. Enable trend tracking across projects.
- [ ] **Reference directory indexing** — Auto-index `reference/` contents so agents don't re-scan the directory structure every run. Update the index when files change.

## Agent & Skill Improvements

- [ ] **Orchestrator agent** — Lightweight orchestrator that can run multi-step workflows (e.g., full complexity-mapper pipeline) without manual agent chaining. Keep it simple — sequence, not autonomy.
- [ ] **Confidence scoring** — Standardize how agents express confidence in findings. Move from free-text ("high/medium/low") to a consistent scoring rubric agents share.
- [ ] **Agent output validation hooks** — Post-agent hooks that validate extraction agent outputs contain source anchors and synthesis agent outputs contain uncertainty markers. Catch contract violations before they propagate downstream.
- [ ] **Incremental analysis** — Allow skills to pick up where a previous run left off rather than re-running the full pipeline.

## Testing

- [ ] **Expand eval cases** — Add eval cases for pattern-remix, context-sharding, and architecture-risk-review workflows.
- [ ] **Regression fixtures** — Capture real analysis outputs as golden files for regression testing.
- [ ] **Grader for source anchor coverage** — Grade whether agent outputs actually include source references, not just mention the concept.
- [ ] **Load testing** — Test behavior with large reference directories (50+ files) to verify context window protection works.

## Packaging & Distribution

- [ ] **Cursor compatibility adapter** — Implement the adaptation notes in `COMPATIBILITY_NOTES.md`. Map agents → rules, skills → prompts, hooks → Cursor equivalent.
- [ ] **Plugin manifest** — Add `plugin.json` if/when distributing beyond local use.
- [ ] **Installation script** — One-command setup that creates the directory structure, installs test dependencies, and validates the plugin is functional.
