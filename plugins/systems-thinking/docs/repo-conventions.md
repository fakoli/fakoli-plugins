# Repo Conventions

These are the active conventions for the systems-thinking-plugin repository. All contributions — human or agent-generated — should follow these standards.

---

## Naming conventions

- **All files:** kebab-case with `.md` extension for content files, `.json` for config. Examples: `doc-reader.md`, `output-contracts.md`, `settings.json`.
- **Spec/seed documents:** Numbered prefix for ordering. Examples: `00-project-brief.md`, `07-output-contracts.md`.
- **Agent files:** Named after the agent's role. One word for simple roles, hyphenated for compound roles. Examples: `doc-indexer.md`, `cost-capacity-analyst.md`.
- **Skill files:** Named after the workflow they implement. Examples: `pattern-remix.md`, `complexity-mapper.md`.
- **No spaces in filenames.** No camelCase, no PascalCase, no underscores.

---

## Folder structure

```
systems-thinking-plugin/
├── .claude/
│   ├── agents/          # Subagent definitions (one per file)
│   ├── skills/          # Skill playbooks (one per file)
│   └── settings.json    # Hooks and Claude Code configuration
├── specs/               # Design specifications (numbered files)
├── reference/           # Input material for context and grounding
│   ├── previous_designs/
│   ├── vendor_docs/
│   ├── prompts/
│   └── examples/
├── docs/                # Reference documentation
│   ├── output-contracts.md
│   ├── agent-design-principles.md
│   └── repo-conventions.md
├── examples/            # Usage scenarios and worked examples
├── CLAUDE.md            # Project instructions for Claude Code
├── COMPATIBILITY_NOTES.md
└── README.md
```

### Folder purposes

| Folder            | What goes here                                                                              | What does not go here                              |
| ----------------- | ------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `.claude/agents/` | One Markdown file per subagent, defining its role, inputs, outputs, and behavioral rules    | Multi-agent orchestration logic, skill definitions |
| `.claude/skills/` | One Markdown playbook per skill, defining when/inputs/process/output/failure-modes          | Agent definitions, raw documentation               |
| `specs/`          | Design specifications — numbered spec files defining the plugin's design and contracts      | Generated outputs, scratch files                   |
| `reference/`      | Source material that informs agent behavior — prior designs, vendor docs, prompts, examples | Generated outputs, scratch files                   |
| `docs/`           | Reference documentation about the plugin's design, contracts, and conventions               | Tutorials, marketing material, generated outputs   |
| `examples/`       | Usage scenarios showing how to invoke skills and what to expect                             | Agent or skill definitions                         |

---

## Agent conventions

Each agent file in `.claude/agents/` follows this structure:

1. **YAML frontmatter** containing:
   - `name`: Agent name matching the filename
   - `type`: Either `extraction` or `synthesis`
   - `description`: One-sentence summary of the agent's job

2. **Markdown body** containing:
   - Purpose (what the agent does)
   - Inputs (what it expects)
   - Outputs (what it produces, referencing the appropriate output contract)
   - Behavioral rules (specific to this agent)
   - Scope boundaries (what it should not do)

3. **One agent per file.** No multi-agent definitions.

4. **Extraction vs synthesis clearly labeled.** The `type` field in frontmatter is not optional. It determines which set of design principles apply (see `docs/agent-design-principles.md`).

---

## Skill conventions

Each skill file in `.claude/skills/` follows this structure:

1. **YAML frontmatter** containing:
   - `name`: Skill name matching the filename
   - `description`: One-sentence summary

2. **Markdown playbook body** containing all five required sections:
   - **When to use:** Conditions under which this skill is appropriate
   - **Inputs:** What the user or orchestrator must provide
   - **Process:** Step-by-step instructions for executing the skill, including which agents to invoke and in what order
   - **Output:** What the skill produces, referencing the appropriate output contract
   - **Failure modes:** What can go wrong and how to detect or mitigate it

3. **One skill per file.**

4. **Skills reference agents, not the other way around.** A skill orchestrates agents. An agent does not know which skill invoked it.

---

## Documentation conventions

- **Markdown only.** No other document formats in `docs/` or `examples/`.
- **One topic per file.** Do not combine unrelated topics into a single document.
- **Descriptive filenames.** The filename should tell you what the document covers without opening it.
- **No generated boilerplate.** Every document should contain substantive, useful content. If a section has nothing to say, omit it rather than writing "TBD" or "TODO."

---

## Output conventions

- All agent and skill outputs follow the contracts defined in `docs/output-contracts.md`.
- **Source anchors are mandatory.** Every finding must reference its source. If a finding cannot be anchored, it must be marked as "inferred" or "unanchored."
- **Confidence markers are expected.** Use high / medium / low when rating severity, likelihood, or certainty.
- **Assumptions must be explicit.** Every synthesis output includes an Assumptions section.
- **Unresolved questions must be surfaced.** Do not silently resolve gaps — carry them forward for the reader.
