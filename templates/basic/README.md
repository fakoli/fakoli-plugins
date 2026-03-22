# My Plugin

> One-sentence description of what this plugin does and who it helps.

## Installation

```
/plugin marketplace add fakoli/fakoli-plugins
/plugin install my-plugin
```

## Features

- **Feature name** — What it does and why it matters
- **Feature name** — What it does and why it matters
- **Feature name** — What it does and why it matters

## Quick Start

```
/example-command Do something useful
```

## Commands

| Command | Description |
|---------|-------------|
| `/example` | What this command does |
| `/example-config` | Configure the plugin |

## Skills

### `skill-name`

When this skill is active, Claude can... (describe the capability).

**Trigger phrases**: "do the thing", "run example", "use my-plugin"

## Configuration

Configure via `.claude/settings.json`:

```json
{
  "plugins": {
    "my-plugin": {
      "option1": "value1",
      "option2": "value2"
    }
  }
}
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `option1` | `"value1"` | What this option controls |
| `option2` | `"value2"` | What this option controls |

## Requirements

- Claude Code
- Node.js >= 18 / Python >= 3.10 / bash (pick what applies)
- Any external dependencies and how to install them

## Plugin Structure

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json       # Plugin manifest
├── skills/
│   └── skill-name/
│       └── SKILL.md      # Skill definition
├── commands/
│   └── example.md        # /example slash command
├── agents/
│   └── agent-name.md     # Sub-agent (if needed)
├── hooks/
│   └── hook-name.md      # PreToolUse / PostToolUse hook (if needed)
├── scripts/              # Supporting scripts
├── README.md
└── LICENSE
```

## Contributing

Contributions are welcome. Please read the [Contributing Guide](../../docs/CONTRIBUTING.md) before opening a pull request.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

Your Name ([@your-handle](https://github.com/your-handle))
