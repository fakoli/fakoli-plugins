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
| *Coming soon* | - | - |

## Categories

- **Productivity** - Tools to enhance your development workflow and efficiency
- **Code Quality** - Linting, testing, and code review plugins
- **DevOps** - CI/CD, deployment, and infrastructure plugins
- **Integrations** - Third-party service and API integrations
- **Utilities** - General-purpose helper tools and utilities

## For Plugin Authors

### Creating a New Plugin

1. Copy the template:
   ```bash
   cp -r templates/basic plugins/your-plugin-name
   ```

2. Update `.claude-plugin/plugin.json` with your plugin metadata

3. Add your skills, commands, agents, or hooks

4. Update README.md and CHANGELOG.md

5. Submit a pull request

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
├── assets/
│   └── screenshots/      # Marketplace screenshots
├── README.md             # Plugin documentation
├── CHANGELOG.md          # Version history
└── LICENSE               # License file
```

### Validation

Before submitting, validate your plugin:

```bash
./scripts/validate.sh plugins/your-plugin-name
```

## Documentation

- [Contributing Guide](docs/CONTRIBUTING.md) - How to contribute plugins
- [Plugin Guidelines](docs/PLUGIN_GUIDELINES.md) - Best practices for plugin development

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
