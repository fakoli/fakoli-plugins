# Contributing to Fakoli Plugins

Thank you for your interest in contributing to the Fakoli Plugins Marketplace!

## Before You Start

### Plugin Requirements Checklist

Your plugin must meet these requirements:

- [ ] **Valid manifest** - `.claude-plugin/plugin.json` with `name` field (kebab-case)
- [ ] **At least one component** - skill, command, agent, or hook
- [ ] **Documentation** - README.md with installation and usage instructions
- [ ] **No secrets** - No API keys, credentials, or sensitive data in code
- [ ] **Passes validation** - `./scripts/validate.sh plugins/your-plugin`

### Security Considerations

**Do:**
- Validate all user inputs
- Use secure defaults
- Document any required permissions
- Handle errors gracefully

**Don't:**
- Include API keys or secrets (use environment variables)
- Execute arbitrary code without user confirmation
- Access files outside expected directories
- Make undocumented network requests

## Submitting a New Plugin

### Step 1: Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/fakoli-plugins.git
cd fakoli-plugins
```

### Step 2: Create Your Plugin

```bash
# Copy the template
cp -r templates/basic plugins/your-plugin-name

# Edit the manifest
# plugins/your-plugin-name/.claude-plugin/plugin.json
```

Example `plugin.json`:
```json
{
  "name": "your-plugin-name",
  "version": "1.0.0",
  "description": "A clear description of what your plugin does",
  "author": {
    "name": "Your Name",
    "url": "https://github.com/your-username"
  },
  "repository": "https://github.com/your-username/your-plugin",
  "license": "MIT",
  "keywords": ["relevant", "tags"]
}
```

### Step 3: Add Your Components

Add your plugin functionality:
- **Skills**: `skills/skill-name/SKILL.md`
- **Commands**: `commands/command-name.md`
- **Agents**: `agents/agent-name.md`
- **Hooks**: `hooks/hooks.json` or inline in manifest

### Step 4: Write Documentation

Update `README.md` with:
- What the plugin does
- How to install it
- How to use each feature
- Any configuration options
- Required dependencies

### Step 5: Validate

```bash
./scripts/validate.sh plugins/your-plugin-name
```

Fix any errors before proceeding.

### Step 6: Submit Pull Request

```bash
git checkout -b add-your-plugin-name
git add plugins/your-plugin-name
git commit -m "feat: add your-plugin-name plugin"
git push origin add-your-plugin-name
```

Open a Pull Request on GitHub.

## What Reviewers Look For

Reviewers will check:

1. **Validation passes** - No errors from `validate.sh`
2. **Clear purpose** - Description explains what the plugin does
3. **Working components** - Skills/commands function correctly
4. **Good documentation** - README explains usage clearly
5. **No security issues** - No hardcoded secrets, safe file access
6. **Proper licensing** - License specified in manifest or LICENSE file

## PR Checklist

Include this in your PR description:

```markdown
## Checklist

- [ ] Plugin passes validation (`./scripts/validate.sh`)
- [ ] `plugin.json` has name, version, and description
- [ ] README.md includes installation and usage instructions
- [ ] No sensitive information (API keys, credentials)
- [ ] License is specified
```

## External Plugins

To submit a modified version of an existing plugin:

1. Place it in `external_plugins/` instead of `plugins/`
2. Create `UPSTREAM.md` documenting the original source:

```markdown
# Upstream Source

- **Original Repository**: https://github.com/original/plugin
- **Original Author**: Original Author Name
- **Original License**: MIT
- **Fork Date**: YYYY-MM-DD

## Modifications

- List each change made to the original
```

## Improving Existing Plugins

For bug fixes or improvements to existing plugins:

1. Fork the repository
2. Make your changes
3. Test thoroughly
4. Submit a PR with a clear description of what you changed and why

## Review Process

1. Automated validation runs on all PRs
2. A maintainer reviews your submission
3. We may request changes or clarifications
4. Once approved, your plugin is merged and indexed

## Getting Help

- Open an issue with the `question` label
- Check existing plugins for examples
- Read the [Plugin Guidelines](PLUGIN_GUIDELINES.md)

---

Thank you for contributing to the Fakoli Plugins ecosystem!
