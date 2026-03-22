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
  self-management. Every plugin ships with skills, commands, agents, and CI validation.
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

### Marketplace Tools

| Plugin | Description |
|--------|-------------|
| [**marketplace-manager**](plugins/marketplace-manager) | Create and manage plugins without leaving Claude Code — scaffold new plugins from template with `/add-plugin`, validate manifests, regenerate registry indices, and install GitHub Actions workflows. The tool that maintains this marketplace. |

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

4. **Validate locally before pushing**
   ```bash
   ./scripts/validate.sh plugins/your-plugin-name
   ```

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

Every pull request runs three checks:

| Check | What it validates |
|-------|-------------------|
| `validate.yml` | Plugin manifest schema, required files, JSON validity |
| `pr-check.yml` | Preview of registry changes on pull requests |
| `update-index.yml` | Auto-regenerates `registry/index.json` on merge to main |

The schema lives in `schemas/plugin.schema.json`. Run `./scripts/validate.sh` locally to catch errors before pushing.

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
├── plugins/                 # All active plugins (7)
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
