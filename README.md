<p align="center">
  <img src="assets/fakoli-banner.png" alt="Fakoli Plugins Marketplace" width="100%">
</p>

<p align="center">
  <a href=".github/workflows/validate.yml"><img src="https://github.com/fakoli/fakoli-plugins/actions/workflows/validate.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/github/stars/fakoli/fakoli-plugins?style=social" alt="GitHub Stars">
</p>

<h1 align="center">Fakoli Plugins Marketplace</h1>

<p align="center"><strong>Extend Claude Code with production-grade plugins.</strong></p>

<p align="center">
  A curated collection of battle-tested Claude Code plugins — covering Google Workspace automation,
  AI image generation, text-to-speech, diagram authoring, secure web fetching, and marketplace
  self-management. The active catalog combines end-user tools, development workflows,
  durable project state, and CI-validated marketplace practices.
</p>

---

## Quick Start

Add this marketplace to Claude Code with one command:

```
/plugin marketplace add fakoli/fakoli-plugins
```

Then install any plugin:

```
/plugin install gws
/plugin install safe-fetch
/plugin install nano-banana-pro
```

---

## What are Claude Code Plugins?

Claude Code plugins extend the assistant with domain-specific capabilities. A plugin can bundle:

- **Skills** — Reusable context files that teach Claude how to use a tool or follow a workflow
- **Commands** — Slash commands (e.g. `/send-email`, `/speak`, `/fetch`) that invoke specific behaviors
- **Agents** — Isolated sub-agents for complex, multi-step operations
- **Hooks** — PreToolUse / PostToolUse interceptors that modify or guard Claude's actions

Plugins live in directories with a `.claude-plugin/plugin.json` manifest. The marketplace validates every plugin against a JSON Schema on every push and pull request.

---

## The Fakoli Ecosystem

Fakoli is a coherent plugin marketplace rather than a loose grab bag. It has
four layers:

- **Work orchestration** — `fakoli-flow`, `fakoli-crew`, and `fakoli-state`
  define how work is planned, staffed, claimed, verified, and recorded.
- **Infrastructure judgment** — `systems-thinking` helps teams examine hidden
  costs, dependencies, caveats, and risks before committing to large changes.
- **Plugin production practices** — `marketplace-manager`, `cli-to-plugin`,
  and `fakoli-plugin-critic` help create, validate, review, and maintain
  Claude Code plugins with repeatable standards.
- **Daily operator tools** — plugins such as `gws`, `safe-fetch`,
  `nano-banana-pro`, `handoff`, `quick-notes`, and `session-retro` cover
  common productivity, media, safety, continuity, and reflection workflows.

At the center is the fakoli trinity — three plugins designed to compose, each
useful standalone:

| Plugin | Role | What It Does |
|--------|------|--------------|
| [**fakoli-flow**](plugins/fakoli-flow) | Workflow orchestration | Intent-driven pipeline: brainstorm → plan → execute → verify → finish. Wave-based dispatch with mandatory critic gates between every code-writing phase |
| [**fakoli-crew**](plugins/fakoli-crew) | Specialist agents | 9 polyglot agents (TypeScript / Python / Rust) — architect, reviewer, security auditor, researcher, plugin engineer, integration specialist, documenter, infrastructure engineer, QA |
| [**fakoli-state**](plugins/fakoli-state) | Canonical project state | Local-first SQLite state engine for humans and AI coding agents. Lockable, evidence-backed work packets; event-sourced log with rebuildable SQLite projection; CLI + MCP surfaces, bidirectional GitHub Issues sync |

**fakoli-flow** defines how work moves. **fakoli-crew** defines who does the work. **fakoli-state** defines what is true. Together they form the canonical fakoli stack: orchestration + specialists + durable state.

A separate companion plugin, [**systems-thinking**](plugins/systems-thinking), runs multi-agent infrastructure analysis (discovery → extraction → synthesis) for decisions that affect the whole system — useful before the trinity starts work, but not part of the core stack.

Install any combination — each works standalone. The full marketplace gives you
a path from idea to execution: evaluate the system context, plan work, assign it
to specialists, capture durable handoffs, run safe tool-enabled workflows, and
verify plugin changes through a shared repository health gate.

For prior-art context — what fakoli invented, what it reinvented, and where
the moat is — see [docs/POSITIONING.md](docs/POSITIONING.md).

---

## Available Plugins

### Google Workspace & Productivity

| Plugin | Description |
|--------|-------------|
| [**gws**](plugins/gws) | Full Google Workspace via the `gws` CLI — 100 skills, 15 commands, 11 role-based agents, and 44 recipes spanning Gmail, Calendar, Drive, Docs, Sheets, Slides, Chat, and more. The most comprehensive Workspace plugin available for any AI assistant. |
| [**notebooklm-enhanced**](plugins/notebooklm-enhanced) | Programmatic control of Google NotebookLM — create notebooks, ingest PDFs and YouTube videos, generate podcasts and slide decks, and run end-to-end research workflows with a single command. |

### AI & Media Generation

| Plugin | Description |
|--------|-------------|
| [**nano-banana-pro**](plugins/nano-banana-pro) | Generate, edit, and remix production-ready images with Google Gemini 3 Pro. Includes a 5-agent PaperBanana pipeline (Retriever → Planner → Stylist → Visualizer → Critic) that iteratively refines images until they pass a quality threshold. |
| [**fakoli-speak**](plugins/fakoli-speak) | Multi-provider TTS for Claude Code — stream any response as speech via `/speak` using OpenAI ($0.015/1K), Deepgram, ElevenLabs, Google Gemini (free), or macOS Say (free). Switch with `/provider`, track spending with `/cost`, toggle auto-narration with `/autospeak`. |
| [**excalidraw-diagram**](plugins/excalidraw-diagram) | Generate `.excalidraw` files from natural language or by analyzing your codebase. Supports flowcharts, architecture diagrams, ER diagrams, and dependency graphs across four color themes — zero dependencies beyond Node.js 18. |

### Security & Web

| Plugin | Description |
|--------|-------------|
| [**safe-fetch**](plugins/safe-fetch) | Drop-in replacement for Claude's built-in `WebFetch` and `WebSearch` that runs content through a 6-layer sanitization pipeline before it touches the LLM. Neutralizes CSS-hidden text, zero-width Unicode, fake LLM delimiters, base64 payloads, and markdown exfiltration vectors. Security-team approvable. |

### Development & Workflow

| Plugin | Description |
|--------|-------------|
| [**anvil-pulse**](plugins/anvil-pulse) | Live operator dashboard for long autonomous [anvil](https://github.com/fakoli/anvil) runs — a dependency-free local web page showing active claims (actor, phase, elapsed, live lease countdown), the event feed, and per-claim stuck-state detection (healthy / quiet / possibly-wedged / lease-expired), plus an optional Claude Code statusline segment. Answers "is this still going, or is it wedged?" on any harness. |
| [**cli-to-plugin**](plugins/cli-to-plugin) | Convert any CLI with `--help` support into a Claude Code plugin: one skill per command group plus optional LLM-proposed workflow meta-skills. |
| [**gate-router**](plugins/gate-router) | Deterministic changed-path gate routing — map the files you changed to the verify commands this repo requires before shipping (docs -> strict build, shell -> bash -n, src -> suite), from a per-project rules file (`.claude/gate-router.local.md`) instead of session memory. |
| [**recall-mode-verifier**](plugins/recall-mode-verifier) | Spec-independent breakage-probe skill — attack a change along fail-closed, malformed-input, resource-exhaustion, and state-drift axes (not its own tests). Verify-left pass for anvil execute and pre-PR review; reports, doesn't fix. |
| [**windows-cli-hygiene**](plugins/windows-cli-hygiene) | Advisory scanner for Windows/cross-platform CLI hazards — non-ASCII in printed strings (cp1252 crashes), hardcoded python3, heredoc backslash mangling, Node .cmd/.bat spawns, set -e in hooks. The scanner form of ship-loop's Windows discipline; wire it as a gate-router gate. |
| [**fakoli-crew**](plugins/fakoli-crew) | Summon nine expert agent archetypes — polyglot architect, Staff-Engineer code reviewer, security auditor, API researcher, plugin engineer, integration specialist, documentation writer, infrastructure keeper, and QA validator — that work independently or as coordinated crews using wave-based orchestration with hook-enforced review gates. |
| [**fakoli-flow**](plugins/fakoli-flow) | Intent-driven workflow orchestration — brainstorm, plan, and execute complex projects through coordinated specialist agents with a five-stage pipeline (brainstorm → plan → execute → verify → finish), critic gates, and evidence-based verification. Works best alongside fakoli-crew. |
| [**fakoli-state**](plugins/fakoli-state) | Local-first, runtime-neutral project state engine for humans and AI coding agents. Turn PRDs into lockable, evidence-backed work packets; coordinate multiple agents without conflicts. Event-sourced JSONL source of truth with a rebuildable SQLite projection, lease-based claims, evidence-gated completion, score-driven task expansion, and bidirectional GitHub Issues sync. |
| [**systems-thinking**](plugins/systems-thinking) | Analyze infrastructure decisions through discovery, extraction, and synthesis so hidden costs, dependencies, caveats, and risks are visible before implementation. |
| [**marketplace-manager**](plugins/marketplace-manager) | Create and manage plugins without leaving Claude Code — scaffold new plugins from template with `/add-plugin`, validate manifests, regenerate registry indices, and install GitHub Actions workflows. The tool that maintains this marketplace. |
| [**fakoli-style**](plugins/fakoli-style) | Governed ledger of the Fakoli operating-model principles — tracks proven, asserted, and aspirational lifecycle statuses and generates a Markdown report from a single canonical source. |
| [**fakoli-plugin-critic**](plugins/fakoli-plugin-critic) | Five specialist critic agents for Claude Code plugin development — agent-critic (frontmatter/color/tools), skill-critic (lazy-loading/no-fuzzy-detection), hook-critic (contract-aware/${CLAUDE_PLUGIN_ROOT}), mcp-critic (schema/actor-validation), structure-critic (manifest/CHANGELOG/version-sync). Audit any plugin with MUST FIX / SHOULD FIX / CONSIDER / NIT verdicts. |
| [**ship-task**](plugins/ship-task) | The mechanical tail of a one-PR-per-task loop, as a single command. After review passes, `/ship` pushes the branch, opens a PR, waits for CI, squash-merges and deletes the branch, syncs the base, and optionally runs a post-merge step (e.g. `anvil apply`) — keeping the repetitive git/gh/CI/merge dance out of the context window. Makes no review decisions; stops if CI fails. |
| [**ship-loop**](plugins/ship-loop) | The full shipping procedure as one invocable skill — sync + worktree isolation, ground-truth scoping, reality-faithful tests, an eight-angle adversarial review as the merge gate, squash-merge, and follow-up closure (promotions ledger, out-of-diff issues). Composes with ship-task for the mechanical tail. |

### Continuity & Personal Workflow

| Plugin | Description |
|--------|-------------|
| [**handoff**](plugins/handoff) | Store durable cross-session project handoff notes shared across same-remote checkouts. |
| [**quick-notes**](plugins/quick-notes) | Capture, search, edit, and export dictation-friendly personal notes. |
| [**session-retro**](plugins/session-retro) | Analyze local Claude Code and Codex session logs into actionable retrospectives. |

---

## Quick Start Examples

```
# Search your Gmail inbox
/triage

# Generate a hero banner for your README
/generate-image "Hero banner with bold headline 'Ship Faster' on dark gradient" --aspect 16:9 --size 2K

# Fetch a webpage without prompt-injection risk
/fetch https://docs.anthropic.com/en/docs/about-claude/models/overview

# Create an architecture diagram from your codebase
/excalidraw Diagram the architecture of this project

# Read the last Claude response aloud (defaults to OpenAI TTS)
/speak

# Switch TTS provider
/provider deepgram

# Scaffold a new plugin
/add-plugin my-new-plugin

# Turn a PRD into claimable, evidence-backed work packets
fakoli-state init --name "My Project"
# (author .fakoli-state/prd.md by hand — see plugins/fakoli-state/docs/prd-template.md)
fakoli-state prd parse                                # PRD → requirements + tasks
fakoli-state prd review                               # gate: draft → reviewed
fakoli-state prd review --approve                     # gate: reviewed → approved
fakoli-state plan && fakoli-state score && fakoli-state review tasks   # generate + score + ready
fakoli-state claim T001                               # lockable claim with lease + heartbeat
fakoli-state submit T001 \
  --commands "pytest" --files-changed src/foo.py      # record evidence (gate input)
fakoli-state apply T001 --approve                     # promote to done with audit trail
```

---

## For Plugin Authors

### Create Your First Plugin in 5 Steps

1. **Scaffold from template**
   ```bash
   cp -r templates/basic plugins/your-plugin-name
   ```

2. **Fill in the manifest** — edit `.claude-plugin/plugin.json` with your plugin's name, version, description, and declared capabilities.

3. **Build your capabilities** — add skills in `skills/`, slash commands in `commands/`, agents in `agents/`, or hooks in `hooks/`.

4. **Run the repository health gate before pushing**
   ```bash
   ./scripts/check-all.sh
   ```
   This is the same combined command CI runs. It performs marketplace
   validation, path-resolution and hook-safety checks, affected plugin tests,
   and the hook validation suite. A zero exit means every step passed; any
   failed step prints the failing layer and exits non-zero, which also fails CI.

5. **Submit a pull request** — the CI pipeline will validate your plugin automatically. See the [Contributing Guide](docs/CONTRIBUTING.md) for review criteria.

### Plugin Structure

```
your-plugin/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest (required)
├── skills/                  # Skill context files
│   └── skill-name/
│       └── SKILL.md
├── commands/                # Slash command definitions
│   └── command-name.md
├── agents/                  # Sub-agent configurations
│   └── agent-name.md
├── hooks/                   # PreToolUse / PostToolUse hooks
│   └── hook-name.md
├── scripts/                 # Supporting scripts (bash, python, node)
├── README.md                # Plugin documentation (required)
└── LICENSE                  # License file
```

### Validation Pipeline

Every pull request runs the same combined repository health gate contributors
should run locally:

```bash
./scripts/check-all.sh
```

The command runs `scripts/validate.sh`, `scripts/test-path-resolution.sh`,
affected plugin tests, and the hook validation suite in sequence. It exits `0`
only after all checks pass. A non-zero exit stops at the failing layer and fails
the CI job.

The CI workflows also run repository-specific follow-up checks:

| Check | What it validates |
|-------|-------------------|
| `validate.yml` | Combined health gate, registry drift, and handoff path resolver |
| `pr-check.yml` | Combined health gate, registry drift, handoff path resolver, and pull request registry preview |
| `update-index.yml` | Auto-regenerates `registry/index.json` on merge to main |

The schema lives in `schemas/plugin.schema.json`. For quick manifest-only
iteration, run `./scripts/validate.sh plugins/your-plugin-name`; before
pushing, run `./scripts/check-all.sh`.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Contributing Guide](docs/CONTRIBUTING.md) | How to safely contribute plugins — review process, security requirements, and merge criteria |
| [Create Your Own Marketplace](docs/CREATE_MARKETPLACE.md) | Fork this repo and run your own private or public plugin marketplace |
| [Plugin Guidelines](docs/PLUGIN_GUIDELINES.md) | Best practices for plugin structure, skill authoring, and command design |
| [Testing Standards](docs/TESTING_STANDARDS.md) | Requirements for plugin test coverage |
| [Anthropic Plugin Docs](https://docs.anthropic.com/en/docs/claude-code/plugins) | Official Claude Code plugin documentation from Anthropic |

---

## Repository Structure

```
fakoli-plugins/
├── .claude-plugin/          # Marketplace-level manifest
├── .github/workflows/       # CI: validate, update-index, pr-check, schema-drift
├── plugins/                 # All active plugins (17)
├── archive/                 # Archived / deprecated plugins
├── registry/                # Auto-generated plugin index (do not edit manually)
├── schemas/                 # JSON Schema definitions for manifests
├── scripts/                 # validate.sh, generate-index.sh, and other tools
├── templates/               # Starter templates for new plugins
│   └── basic/               # Standard plugin scaffold
├── assets/                  # Marketplace assets (banner, logos)
└── docs/                    # Guides and documentation
```

---

## Archived Plugins

Some plugins have been archived and are no longer actively maintained. They remain available in the [`archive/`](archive/) directory for reference.

---

## License

This marketplace is licensed under the [MIT License](LICENSE). Individual plugins may have their own licenses — check each plugin's `LICENSE` file.

---

<p align="center">Built and maintained by <a href="https://github.com/fakoli">@fakoli</a></p>
