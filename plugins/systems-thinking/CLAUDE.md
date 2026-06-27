# Systems Thinking Plugin

A Claude Code plugin that encodes a systems engineer's methodology for evaluating infrastructure, architecture, and vendor proposals. It surfaces what's below the waterline — the hidden costs, buried caveats, scaling cliffs, and dependency traps that don't show up in the sales pitch or the POC.

Marketplace migration note: this file is preserved from the upstream repository
and adapted for its new location under `plugins/systems-thinking`, including the
marketplace plugin identity, paths, and validation commands.

## Key Commands

```bash
# Run tests (fast — skips evals by default)
cd plugins/systems-thinking
uv run pytest tests/ -v

# Run evals (slow — invokes Claude CLI, shows cost/token tracking)
uv run pytest tests/ -m slow -s

# Validate plugin structure
python3 -m json.tool .claude-plugin/plugin.json > /dev/null
```

## Architecture

### Pipeline Flow

```
web-researcher → doc-indexer → extraction-planner → [parallel extractors] → synthesis-brief-writer
   (discover)    (map structure)  (plan dispatch)    (scoped extraction)       (synthesize)
```

Only `web-researcher` has web access (WebSearch + WebFetch). All other agents work on pre-discovered material. The `extraction-planner` prevents extractor overload by right-sizing parallelization before agents are spawned.

### Agents (`agents/`)

Nine subagents organized into three tiers:

| Agent | Role | Model | Tier |
|-------|------|-------|------|
| `web-researcher` | Discover source material from web and local files | Sonnet | Orchestration |
| `extraction-planner` | Assess material volume, produce Dispatch Plans | Haiku | Orchestration |
| `doc-indexer` | Map document structure, flag high-value sections | Haiku | Extraction |
| `doc-reader` | Extract technical claims, limits, dependencies | Haiku | Extraction |
| `caveat-extractor` | Find buried limitations, quotas, traps | Sonnet | Extraction |
| `cost-capacity-analyst` | Surface cost mechanics, scaling constraints | Sonnet | Extraction |
| `architecture-dependency-mapper` | Map control/data-plane dependencies | Sonnet | Extraction |
| `pattern-remix-planner` | Adapt prior work to new problems | Opus | Synthesis |
| `synthesis-brief-writer` | Turn extracted evidence into decision briefs | Opus | Synthesis |

### Skills (`skills/`)

Five slash-command skills, each orchestrating agents through the pipeline:

| Skill | Purpose | Key Agents |
|-------|---------|------------|
| `/complexity-mapper` | Full below-the-waterline scan for hidden complexity | web-researcher → extraction-planner → all extractors → synthesis |
| `/context-sharding` | Break large material into parallel extraction chunks | doc-indexer → extraction-planner → parallel doc-readers |
| `/architecture-risk-review` | Targeted failure mode and dependency analysis | caveat-extractor + architecture-dependency-mapper → synthesis |
| `/decision-brief` | Package findings into stakeholder-ready format | synthesis-brief-writer (consumes upstream outputs) |
| `/pattern-remix` | Adapt prior proven work to new constraints | pattern-remix-planner |

### Hooks (`hooks/`)

Three event hooks, all command-type (not prompt-type):

| Event | Script | Purpose |
|-------|--------|---------|
| `SessionStart` | Inline command | Check for `uv` and `jq` availability |
| `UserPromptSubmit` | `user-prompt-gate.sh` | Inject extraction/synthesis reminder only when a systems-thinking skill is actively invoked |
| `Stop` | `stop-quality-gate.sh` | Verify outputs include assumptions, risks, unresolved questions, next steps |

**Hook safety rules:**
- All hooks use `hooks` array wrapper (required by Claude Code)
- No `set -e` in scripts (breaks `|| fallback` patterns)
- No `cat | grep` (ARG_MAX failures on large transcripts)
- Scripts grep transcript files directly
- `discover-components.sh` auto-discovers skills/agents from directory structure (no hardcoded lists)
- All command hooks have timeouts set

## Agent Design Principles

1. **Separate extraction from synthesis.** Extraction agents gather facts. Synthesis agents draw conclusions. Never both in one agent.
2. **Keep roles narrow.** One primary job per agent. The extraction-planner plans but doesn't extract. The web-researcher discovers but doesn't analyze.
3. **Preserve source anchors.** Every finding references file, section, line number, or URL.
4. **Right-size parallelization.** The extraction-planner assesses material volume before spawning extractors. Sizing heuristics: ≤5 sections → single extractor per type; 6-15 → 2 per type; 16-30 → 3-4 per type; 30+ → context-shard first.
5. **Avoid hallucinated certainty.** Call out ambiguity, missing data, low-confidence inferences. Label `[from source]` vs `[inferred]`.
6. **Optimize for senior engineering judgment.** Surface non-obvious findings. Skip introductory context. Present tradeoffs, not just recommendations.

## Output Contracts

All deliverables follow structured formats defined in `docs/output-contracts.md`:

| Contract | Key Sections |
|----------|-------------|
| Hidden Risk Summary | scope reviewed, top risks, impact areas, assumptions, unresolved questions |
| Complexity Heat Map | complexity areas ranked by severity, confidence, visibility |
| Decision Brief | decision frame, options, evidence, inferred concerns, top risks, next steps |
| Pattern Remix Draft | target outcome, reusable patterns, constraints, approach, risks |
| Context Packet | source, scope, extracted findings, caveats, confidence notes |
| Source Manifest | discovered URLs/paths, relevance, sections of interest, gaps |
| Dispatch Plan | material summary, agent assignments, scoped instructions per agent |

## Validation

The marketplace repository runs shared plugin validation on pull requests,
including manifest validation, path checks, changelog drift checks, and registry
drift checks. The systems-thinking unit and contract tests are imported for
local verification and targeted migration checks:

```bash
cd plugins/systems-thinking
uv run pytest tests/unit tests/contracts -q
```

**To prepare a marketplace release:** bump versioned plugin metadata, update
`CHANGELOG.md`, run `./scripts/generate-index.sh` from the marketplace root,
and include the generated registry updates in the PR.

### Evals (`tests/evals/`)

Not in marketplace CI — run locally when validating agent behavior. Each eval invokes the Claude CLI with a prompt and grades the output:
- Results saved to `plugins/systems-thinking/tests/evals/results/<case>/` for inspection
- Token usage and cost estimates printed per eval
- Slow tests excluded by default (`pyproject.toml` sets `-m 'not slow'`)

```bash
cd plugins/systems-thinking
uv run pytest tests/ -m slow -s             # run all evals with output
uv run pytest tests/ -m slow -k complexity  # run specific eval
```

## Versioning

The upstream repository kept three files in sync:
- `.claude-plugin/plugin.json` — canonical source (Claude Code reads this)
- `pyproject.toml` — Python package metadata
- `VERSION` — plain text version file

In the marketplace layout, `plugins/systems-thinking/.claude-plugin/plugin.json`
is the plugin manifest and `plugins/systems-thinking/VERSION` preserves the
upstream version marker. Python package metadata is imported with the executable
test and utility surface.

## Reference Directory (`reference/`)

User-curated materials that agents check during analysis:

| Directory | Contents | Used By |
|-----------|----------|---------|
| `previous_designs/` | Prior design docs, ADRs, architecture notes | pattern-remix-planner, doc-indexer |
| `vendor_docs/` | Vendor documentation, pricing, quotas, SLAs | all extraction agents, web-researcher |
| `prompts/` | Effective prompts and analysis patterns | synthesis-brief-writer |
| `examples/` | Example outputs showing the quality bar | synthesis-brief-writer, pattern-remix-planner |

## Conventions

- Markdown-based definitions for agents and skills
- `kebab-case` for all file and directory names
- Agent frontmatter: `name`, `model`, `color`, `description`, `allowed-tools`
- Skill frontmatter: `name`, `description` (≥250 chars with trigger phrases, no `trigger` field)
- Prefer many small composable files over one giant file
- Scope tools deliberately — only `web-researcher` gets WebSearch/WebFetch
- Tests skip evals by default (`-m 'not slow'` in pyproject.toml)

## Documentation

| File | Contents |
|------|----------|
| `README.md` | Why this exists, how it works walkthrough, workflows, agents |
| `docs/systems-thinking-foundations.md` | Conceptual foundations, iceberg model, concept-to-capability mapping |
| `docs/output-contracts.md` | Output format definitions |
| `docs/agent-design-principles.md` | Agent design rationale |
| `docs/repo-conventions.md` | Naming and structure conventions |
| `docs/images/` | Static orchestration diagrams referenced by design docs |
| `examples/usage-scenarios.md` | 5 worked examples with agent flows |
| `iceberg-banner.png` | README banner image |
| `utils/` | Deterministic helper scripts for indexing, sharding, prompt building, orchestration, aggregation, and validation |
| `CHANGELOG.md` | Version history (Keep a Changelog format) |
| `COMPATIBILITY_NOTES.md` | Cursor compatibility notes |
