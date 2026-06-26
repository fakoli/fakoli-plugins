# Compatibility Notes

## Primary target: Claude Code

This package is built for **Claude Code local project usage**. All agents, skills, hooks, and conventions are designed around Claude Code's file-based architecture:

- Agents are Markdown files in `.claude/agents/`
- Skills are Markdown playbooks in `.claude/skills/`
- Hooks are configured in `.claude/settings.json`
- Context comes from local files in `reference/`

This is the supported and tested workflow. Get this working well before considering other platforms.

## Secondary target: Cursor

Cursor compatibility is a future goal, not a current priority. The core ideas (extraction/synthesis separation, structured outputs, source anchors) transfer to any LLM-powered editor, but the packaging would need to change.

### What would need to change for Cursor

| Claude Code concept                            | Cursor equivalent                         | Migration effort                                                                                                            |
| ---------------------------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `.claude/agents/` (Markdown agent definitions) | `.cursorrules` or custom rules files      | Moderate — rewrite as rule directives rather than agent personas                                                            |
| `.claude/skills/` (Markdown playbooks)         | Prompt templates or composer instructions | Moderate — restructure as step-by-step prompts without agent delegation                                                     |
| `.claude/settings.json` hooks                  | No direct equivalent                      | High — Cursor does not have a hook system; would need to embed reminders in rules or rely on user discipline                |
| `reference/` directory for source material     | Same approach (local files)               | Low — file-based context works similarly                                                                                    |
| Output contracts                               | Same approach (prompt instructions)       | Low — include contract definitions in rules or prompt templates                                                             |
| Subagent delegation (parallel extraction)      | Not natively supported                    | High — Cursor does not have a subagent model; would need to simulate with sequential prompts or accept single-pass analysis |

### Key differences that affect design

1. **No subagent model.** Cursor operates as a single agent. The extraction/synthesis separation would need to be enforced through prompt structure (e.g., "First, extract all findings. Then, in a separate section, synthesize.") rather than through separate agent invocations.

2. **No hooks.** The pre-flight reminder and completion quality check would need to be baked into the rules file or included as part of every prompt template.

3. **No skill orchestration.** Skills in Claude Code can reference and invoke agents. In Cursor, the equivalent would be a detailed prompt that includes the full workflow inline.

4. **Rules file vs. agent files.** Cursor uses `.cursorrules` (a single file or a small set) rather than per-agent Markdown files. The content would need to be consolidated.

### Known unknowns

- Whether Cursor's rules system supports the level of structured output formatting these contracts require.
- How Cursor handles large context from `reference/` directories — whether it has similar file-reading capabilities or requires explicit file references.
- Whether Cursor's composer mode can approximate the multi-step workflows that skills define.
- How Cursor versioning and sharing works for rule sets (relevant for team adoption).

## Recommendation

Get the Claude Code workflow solid first. Validate that the agents produce useful outputs, the skills orchestrate correctly, and the output contracts are practical. Once the workflow is proven, adapt for Cursor as a separate packaging effort rather than trying to maintain dual compatibility from the start.

The core intellectual work — the design principles, output contracts, and extraction/synthesis separation — transfers regardless of platform. The packaging is what changes.
