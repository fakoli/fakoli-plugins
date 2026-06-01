# Herald Agent Status

**Status:** Complete

## Files Modified

- `plugins/fakoli-style/skills/style-ops/SKILL.md` — created; valid frontmatter, four verbs, lifecycle rule, links to README
- `plugins/fakoli-style/README.md` — created; authoritative reference with canonical-data model, status table, quick start, verbs table, links to generated doc
- `plugins/fakoli-style/CHANGELOG.md` — created; 1.0.0 initial release entry

## Decisions

- SKILL.md kept minimal per repo doc-hygiene rule: frontmatter + quick reference + links to README. Full prose lives in README.
- README links to `docs/fakoli-style.md` rather than duplicating ledger content, consistent with the canonical-data model.
- CHANGELOG uses ISO date 2026-05-31 (today) for the 1.0.0 entry.
- No em dashes used anywhere; repo voice rule followed throughout.
- Invocations document running from `plugins/fakoli-style/` as instructed, while noting the scripts are CWD-independent.

## Notes for Specific Agents

**keeper (next wave — repo README "Available Plugins" table and marketplace entry):**

One-line description to use, consistent with `plugin.json`:

> Governed ledger of the Fakoli operating-model principles — tracks proven, asserted, and aspirational rules, validates lifecycle evidence, and generates a formatted report from a single canonical JSON source.

Short form for table cells (matches plugin.json `description` field):

> Style operations and output formatting tools for Claude Code — apply, audit, and enforce code and prose style conventions.

Note: the plugin.json description is oriented toward style/formatting conventions broadly; the README and ledger content are specifically about the operating-model principles ledger. Keeper should decide which framing matches how the plugin is presented in the marketplace and keep all three sync sources (README table, registry/index.json, marketplace.json) consistent with whichever is chosen.

## Blockers

None.
