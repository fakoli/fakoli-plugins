# Agent Roster

Canonical reference for all 8 fakoli-crew agents. Other files in this plugin link here rather than repeating this table.

## Agents

| Agent | Color | Role | Best For | File |
|-------|-------|------|----------|------|
| guido | blue | TypeScript architect | Interface design, type system patterns, new modules, type-safe refactors | `agents/guido.md` |
| critic | red | Code reviewer | Quality audits, bug detection, import analysis, severity ratings | `agents/critic.md` |
| scout | cyan | Researcher | API docs, codebase exploration, dependency investigation, technical references | `agents/scout.md` |
| smith | green | Plugin engineer | plugin.json manifests, hooks, commands, plugin structure | `agents/smith.md` |
| welder | yellow | Integration engineer | Wiring new code into existing systems, backward-compatible refactors | `agents/welder.md` |
| herald | pink | Documentation writer | READMEs, marketplace descriptions, branding, user-facing copy | `agents/herald.md` |
| keeper | purple | Infrastructure engineer | CI/CD workflows, CLAUDE.md, contributor docs, registry sync | `agents/keeper.md` |
| sentinel | orange | QA engineer | Test runs, validation scorecards, pre-release checks, verification | `agents/sentinel.md` |

## Notes

**Colors** map to the `color` field in each agent's frontmatter. They appear in the Claude Code UI to distinguish agent output during multi-agent runs.

**File paths** are relative to the plugin root (`plugins/fakoli-crew/`). Each file contains the agent's full system prompt, tool allowlist, and triggering conditions.

**critic** operates as a standing gate between waves rather than a build-phase agent. It fires after every wave that produces or modifies code — it does not own a dedicated build slot.

**sentinel** produces evidence-based scorecards. It verifies claims against observable outputs (test results, file counts, link resolution) rather than accepting assertions.

For orchestration context — wave sequencing, file ownership, and status-file protocol — see `skills/crew-ops/SKILL.md`. For pre-built crew compositions, see `commands/crew.md`.
