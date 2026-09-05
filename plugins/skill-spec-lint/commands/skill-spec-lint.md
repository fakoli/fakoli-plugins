---
description: Lint SKILL.md files against the deterministic Agent Skills spec rules
---

Use the `skill-spec-lint` skill from the skill-spec-lint plugin for: $ARGUMENTS

- No argument -> lint every skill under the current directory.
- A path (skill dir, plugin dir, or repo root) -> lint the skills under it.
- Report each finding as `path: LEVEL: message`; ERROR fails, WARN does not.

Run the linter directly:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/skill_spec_lint.py" [PATH ...]
```
