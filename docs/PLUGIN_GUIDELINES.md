# Plugin Development Guidelines

Best practices for creating high-quality Claude Code plugins.

## Plugin Quality Standards

### Required Elements

Every plugin must have:

1. **Valid manifest** - `.claude-plugin/plugin.json` with required fields
2. **Unique name** - Lowercase, alphanumeric, hyphens only
3. **Semantic versioning** - Follow [semver](https://semver.org/)
4. **Clear description** - 10-500 characters explaining the plugin's purpose
5. **At least one component** - skill, command, agent, or hook
6. **README** - Installation and usage documentation

### Recommended Elements

For better discoverability and user experience:

1. **CHANGELOG** - Document version history
2. **LICENSE** - Clear licensing terms
3. **Screenshots** - Visual documentation in `assets/screenshots/`
4. **Extended metadata** - Category, tags, compatibility info
5. **Examples** - Usage examples in documentation

## Naming Conventions

### Plugin Names

- Use lowercase letters, numbers, and hyphens
- Be descriptive but concise
- Avoid generic names like "utils" or "tools"
- Don't include "plugin" in the name

```
✓ git-workflow-helper
✓ code-review-assistant
✓ api-documentation-gen

✗ MyPlugin
✗ Utils
✗ code_review_plugin
```

### Skill Names

- Use kebab-case for file names
- Use descriptive names that hint at functionality
- Keep names reasonably short

## Version Guidelines

Follow Semantic Versioning (semver):

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes
- **MINOR** (1.0.0 → 1.1.0): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backward compatible

### Pre-release Versions

Use pre-release tags for testing:

```
1.0.0-alpha.1
1.0.0-beta.2
1.0.0-rc.1
```

## Writing Good Skills

### Skill File Structure

```markdown
---
name: skill-name
description: Brief description shown in skill list
user_invocable: true
---

# Skill Name

Clear explanation of what this skill does.

## Usage

How users invoke and use this skill.

## Instructions

Detailed instructions for Claude on how to execute this skill.

## Examples

Real-world usage examples.
```

### Best Practices

1. **Be specific** - Clear, actionable instructions
2. **Handle edge cases** - What if input is missing or invalid?
3. **Provide examples** - Show expected inputs and outputs
4. **Stay focused** - One skill, one purpose

## Documentation Standards

### README.md Structure

```markdown
# Plugin Name

Brief description.

## Installation

How to install the plugin.

## Features

List of main features.

## Skills/Commands

Documentation for each component.

## Configuration

Any configuration options.

## Requirements

Dependencies and compatibility.

## License

License information.
```

### Writing Style

- Use clear, concise language
- Include code examples
- Document all options and parameters
- Keep it up to date with code changes

## Security Guidelines

### Do

- Validate all user inputs
- Use secure defaults
- Document any required permissions
- Handle errors gracefully

### Don't

- Include API keys or secrets
- Execute arbitrary user code without warnings
- Access files outside expected directories
- Make undocumented network requests

## Compatibility

### Platform Compatibility

Specify supported platforms in `extended.compatibility.platforms`:

```json
{
  "extended": {
    "compatibility": {
      "platforms": ["darwin", "linux", "win32"]
    }
  }
}
```

### Version Requirements

Document Claude Code version requirements:

```json
{
  "extended": {
    "compatibility": {
      "claudeCodeVersion": ">=1.0.0"
    }
  }
}
```

## Dependencies

### Declaring Dependencies

List required dependencies in the manifest:

```json
{
  "extended": {
    "dependencies": {
      "npm": ["lodash@^4.0.0"],
      "pip": ["requests>=2.25.0"],
      "binaries": ["git", "node"]
    }
  }
}
```

### Dependency Guidelines

- Pin major versions to avoid breaking changes
- Keep dependencies minimal
- Document installation steps for non-standard dependencies
- Prefer widely-available packages

## Testing Your Plugin

### Before Submission

1. **Validate manifest**
   ```bash
   ./scripts/validate.sh plugins/your-plugin
   ```

2. **Test all components**
   - Invoke each skill manually
   - Test edge cases
   - Verify on multiple platforms if claiming cross-platform support

3. **Review documentation**
   - All features documented
   - Examples work correctly
   - No placeholder text

## Maintenance

### Active Maintenance

- Respond to issues and PRs
- Keep dependencies updated
- Fix bugs promptly
- Communicate breaking changes

### Deprecation

If you need to deprecate a plugin:

```json
{
  "extended": {
    "deprecated": "Use new-plugin instead"
  }
}
```

---

Following these guidelines helps ensure a consistent, high-quality plugin ecosystem for all Claude Code users.
