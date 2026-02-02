# Contributing to Fakoli Plugins

Thank you for your interest in contributing to the Fakoli Plugins Marketplace!

## Ways to Contribute

1. **Submit a new plugin** - Share your Claude Code plugins with the community
2. **Improve existing plugins** - Bug fixes, features, or documentation
3. **Report issues** - Help us identify bugs or suggest improvements
4. **Improve documentation** - Help make our docs clearer and more complete

## Submitting a New Plugin

### Prerequisites

- Your plugin must be compatible with Claude Code
- Include at least one skill, command, agent, or hook
- Follow the [Plugin Guidelines](PLUGIN_GUIDELINES.md)

### Step-by-Step Guide

1. **Fork this repository**

2. **Create your plugin directory**
   ```bash
   # Copy the template
   cp -r templates/basic plugins/your-plugin-name
   ```

3. **Configure your plugin manifest**

   Edit `.claude-plugin/plugin.json`:
   ```json
   {
     "name": "your-plugin-name",
     "version": "1.0.0",
     "description": "A clear description of what your plugin does",
     "author": {
       "name": "Your Name",
       "email": "you@example.com"
     },
     "license": "MIT",
     "extended": {
       "category": "utilities",
       "tags": ["relevant", "tags"]
     }
   }
   ```

4. **Add your plugin components**
   - Skills go in `skills/skill-name/SKILL.md`
   - Commands go in `commands/command-name.json`
   - Agents go in `agents/agent-name.json`
   - Hooks go in `hooks/hook-name.json`

5. **Write documentation**
   - Update `README.md` with usage instructions
   - Update `CHANGELOG.md` with version history
   - Add screenshots to `assets/screenshots/` (optional but recommended)

6. **Validate your plugin**
   ```bash
   ./scripts/validate.sh plugins/your-plugin-name
   ```

7. **Submit a Pull Request**
   - Create a feature branch: `git checkout -b add-your-plugin-name`
   - Commit your changes with a clear message
   - Push to your fork
   - Open a Pull Request against the `main` branch

### PR Checklist

- [ ] Plugin passes validation (`./scripts/validate.sh`)
- [ ] `plugin.json` has all required fields
- [ ] README.md includes installation and usage instructions
- [ ] CHANGELOG.md documents the initial release
- [ ] License is specified (in file or manifest)
- [ ] No sensitive information (API keys, credentials, etc.)

## External Plugins

If you want to submit a modified version of an existing plugin:

1. Place it in `external_plugins/` instead of `plugins/`
2. Create `UPSTREAM.md` documenting the original source
3. Clearly document your modifications

### UPSTREAM.md Format

```markdown
# Upstream Source

- **Original Repository**: https://github.com/original/plugin
- **Original Author**: Original Author Name
- **Original License**: MIT
- **Fork Date**: YYYY-MM-DD
- **Last Synced**: YYYY-MM-DD

## Modifications

- List of changes made to the original
```

## Code of Conduct

- Be respectful and constructive
- No malicious code or harmful content
- Respect intellectual property and licenses
- Help maintain a welcoming community

## Review Process

1. Automated validation runs on all PRs
2. A maintainer will review your submission
3. We may request changes or clarifications
4. Once approved, your plugin will be merged

## Questions?

- Open an issue for questions about contributing
- Tag issues with `question` label

---

Thank you for contributing to the Fakoli Plugins ecosystem!
