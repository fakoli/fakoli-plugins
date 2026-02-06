<p align="center">
  <img src="assets/fakoli-banner.png" alt="Fakoli Plugins Marketplace" width="100%">
</p>

# Fakoli Plugins Marketplace

A curated collection of Claude Code plugins for enhanced productivity and development workflows.

## Quick Start

### Adding the Marketplace

```bash
/plugin marketplace add https://github.com/fakoli/fakoli-plugins
```

### Installing a Plugin

```bash
# List available plugins
/plugin search

# Install a specific plugin
/plugin install <plugin-name>
```

## Available Plugins

| Plugin | Category | Description |
|--------|----------|-------------|
| [nano-banana-pro](plugins/nano-banana-pro) | Utilities | Image generation using Google Gemini models |
| [marketplace-manager](plugins/marketplace-manager) | Utilities | Manage plugins in this marketplace |
| [k8s-sidecar-testing](plugins/k8s-sidecar-testing) | DevOps | End-to-end testing for nat464-sidecar in IPv6-only K8s clusters |
| [rust-network-module](plugins/rust-network-module) | Productivity | Scaffold Rust async networking modules with Tokio patterns |

## Categories

- **Productivity** - Tools to enhance your development workflow and efficiency
- **Code Quality** - Linting, testing, and code review plugins
- **DevOps** - CI/CD, deployment, and infrastructure plugins
- **Integrations** - Third-party service and API integrations
- **Utilities** - General-purpose helper tools and utilities

## Documentation

| Guide | Description |
|-------|-------------|
| [Contributing Guide](docs/CONTRIBUTING.md) | How to safely contribute plugins to this marketplace |
| [Create Your Own Marketplace](docs/CREATE_MARKETPLACE.md) | Fork this repo and create your own plugin marketplace |
| [Plugin Guidelines](docs/PLUGIN_GUIDELINES.md) | Best practices for plugin development |

## For Plugin Authors

### Creating a New Plugin

1. Copy the template:
   ```bash
   cp -r templates/basic plugins/your-plugin-name
   ```

2. Update `.claude-plugin/plugin.json` with your plugin metadata

3. Add your skills, commands, agents, or hooks

4. Validate before submitting:
   ```bash
   ./scripts/validate.sh plugins/your-plugin-name
   ```

5. Submit a pull request (see [Contributing Guide](docs/CONTRIBUTING.md))

### Plugin Structure

```
your-plugin/
├── .claude-plugin/
│   └── plugin.json       # Plugin manifest (required)
├── skills/               # Skill definitions
│   └── skill-name/
│       └── SKILL.md
├── commands/             # Command definitions
├── agents/               # Agent configurations
├── hooks/                # Hook definitions
├── README.md             # Plugin documentation
└── LICENSE               # License file
```

## Repository Structure

```
fakoli-plugins/
├── .claude-plugin/       # Marketplace configuration
├── plugins/              # First-party plugins
├── external_plugins/     # Modified external plugins
├── registry/             # Auto-generated indices
├── scripts/              # Validation and build tools
├── templates/            # Plugin starter templates
├── schemas/              # JSON Schema definitions
└── docs/                 # Documentation
```

## Contributing

We welcome contributions! Please read our [Contributing Guide](docs/CONTRIBUTING.md) before submitting plugins.

## License

This marketplace is licensed under the MIT License. Individual plugins may have their own licenses - check each plugin's LICENSE file.

---

Maintained by [@fakoli](https://github.com/fakoli)
