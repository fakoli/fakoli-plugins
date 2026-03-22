<p align="center">
  <img src="assets/fakoli-banner.png" alt="Fakoli Plugins Marketplace" width="100%">
</p>

<p align="center">
  <a href="https://github.com/fakoli/fakoli-plugins/actions"><img src="https://github.com/fakoli/fakoli-plugins/actions/workflows/validate.yml/badge.svg" alt="Validation"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="https://github.com/fakoli/fakoli-plugins/stargazers"><img src="https://img.shields.io/github/stars/fakoli/fakoli-plugins?style=social" alt="Stars"></a>
</p>

# Fakoli Plugins Marketplace

**Extend Claude Code with production-grade plugins** for image generation, Google Workspace automation, web security, text-to-speech, and more. Every plugin is validated, tested, and reviewed before merging.

## Install in one command

```
/plugin marketplace add fakoli/fakoli-plugins
```

Then enable any plugin from the list below.

---

## Plugins

### Google Workspace & Productivity

| Plugin | Description |
|--------|-------------|
| **[gws-plugin](plugins/gws-plugin)** | Full Google Workspace automation — 100+ skills, 15 commands, 11 role-based agents, 44 recipes across Gmail, Calendar, Drive, Docs, Sheets, Slides, Tasks, Chat, Meet, Forms, Classroom, Keep, and more |
| **[notebooklm-enhanced](plugins/notebooklm-enhanced)** | Google NotebookLM automation — create notebooks, add sources, generate podcasts/videos/quizzes/slides, and run multi-notebook research workflows |

### AI & Media Generation

| Plugin | Description |
|--------|-------------|
| **[nano-banana-pro](plugins/nano-banana-pro)** | Generate, edit, remix, and optimize images using Google Gemini 3 Pro — style templates, brand-aware remixing, smart presets for GitHub/Slack/web |
| **[fakoli-speak](plugins/fakoli-speak)** | ElevenLabs streaming text-to-speech with cost tracking — `/speak`, `/stop`, `/voices`, `/cost`, `/autospeak` for hands-free output |
| **[excalidraw-diagram](plugins/excalidraw-diagram)** | Generate and modify Excalidraw diagrams from natural language descriptions and code analysis |

### Security & Web

| Plugin | Description |
|--------|-------------|
| **[safe-fetch](plugins/safe-fetch)** | Defense-in-depth web fetching — strips prompt injection vectors from HTML, PDF, and JSON before content reaches the LLM. Drop-in replacement for blocked `WebFetch` |

### DevOps & Infrastructure

| Plugin | Description |
|--------|-------------|
| **[k8s-sidecar-testing](plugins/k8s-sidecar-testing)** | End-to-end testing for nat464-sidecar in IPv6-only Kubernetes clusters using Multipass VMs and k3s |
| **[rust-network-module](plugins/rust-network-module)** | Scaffold Rust async networking modules with Tokio, tracing, and anyhow following established project patterns |

### Marketplace Tools

| Plugin | Description |
|--------|-------------|
| **[marketplace-manager](plugins/marketplace-manager)** | Manage this marketplace — add/remove plugins, validate manifests, regenerate registry indices, run deep scans |

---

## What are Claude Code plugins?

Plugins extend Claude Code with new capabilities: slash commands, autonomous agents, event-driven hooks, MCP tool servers, and workflow skills. They let you automate tasks that Claude Code can't do on its own — like generating images, managing your Google Calendar, or speaking responses aloud.

**This marketplace** gives you a curated set of plugins that are:
- Validated against a strict schema with CI checks on every PR
- Reviewed for security (no hardcoded secrets, safe file access, input validation)
- Tested with deep path resolution scanning and hook safety analysis
- Documented with setup instructions and usage examples

## Quick Start

```bash
# 1. Add the marketplace
/plugin marketplace add fakoli/fakoli-plugins

# 2. Browse plugins
/plugin

# 3. Enable a plugin
/plugin   # select from the list

# 4. Reload to activate
/reload-plugins
```

## For Plugin Authors

We welcome contributions. Every plugin goes through automated validation and manual review.

### Create a plugin in 5 minutes

```bash
# 1. Fork and clone
git clone https://github.com/YOUR-USERNAME/fakoli-plugins.git

# 2. Scaffold from template
cp -r templates/basic plugins/your-plugin-name

# 3. Build your plugin (add skills/, commands/, agents/, or hooks/)

# 4. Validate
./scripts/validate.sh plugins/your-plugin-name
./scripts/test-path-resolution.sh plugins/your-plugin-name

# 5. Submit a PR
```

See the full [Contributing Guide](docs/CONTRIBUTING.md) and [Plugin Guidelines](docs/PLUGIN_GUIDELINES.md).

### Plugin structure

```
your-plugin/
  .claude-plugin/
    plugin.json          # Manifest (name, version, description)
  commands/              # Slash commands (auto-discovered)
  skills/                # Workflow skills (auto-discovered)
  agents/                # Autonomous agents (auto-discovered)
  hooks/                 # Event hooks (hooks.json)
  README.md              # Documentation (required)
```

### Validation pipeline

Every PR is checked automatically:
1. **Schema validation** — JSON syntax, required fields, semver, name format
2. **Deep path scanning** — all component paths resolve, scripts exist
3. **Hook safety** — specific matchers, timeouts, no `set -e`, no `cat | grep`
4. **Registry update** — index regenerated on merge to main

## Documentation

| Guide | Description |
|-------|-------------|
| [Contributing Guide](docs/CONTRIBUTING.md) | How to submit plugins to this marketplace |
| [Create Your Own Marketplace](docs/CREATE_MARKETPLACE.md) | Fork this repo and build your own |
| [Plugin Guidelines](docs/PLUGIN_GUIDELINES.md) | Best practices for plugin development |
| [Claude Code Plugin Docs](https://code.claude.com/docs/en/plugins) | Official Anthropic documentation |

## License

MIT. Individual plugins may have their own licenses — check each plugin's LICENSE file.

---

<p align="center">
  Built and maintained by <a href="https://github.com/fakoli">@fakoli</a>
</p>
