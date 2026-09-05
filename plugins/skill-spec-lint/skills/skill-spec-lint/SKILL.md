---
name: skill-spec-lint
description: Validate Agent Skills YAML, field types, naming, lengths, and discovery layout. Use when authoring, reviewing, or checking SKILL.md files. Requires PyYAML; uv runs it in an isolated environment.
---

# Skill Spec Lint

Resolve the plugin root from the loaded skill (`../..`) or the host's plugin-root variable, then run:

```bash
uv run --script "<plugin-root>/scripts/skill_spec_lint.py" [PATH ...]
```

Inputs may be `SKILL.md`, a skill directory, a plugin, or a repository. Overlapping paths are counted once. `--help` shows the CLI. With no paths, scan the current directory.

The linter parses complete YAML, rejects duplicate keys, and validates name/directory agreement, required strings, optional types, string metadata, and length bounds. A missing YAML dependency is an error, never a reduced-coverage pass. `uv` may download PyYAML on first use; validation itself is local. If PyYAML is already installed, direct Python invocation also works.

Errors return 1; CLI/dependency errors return 2. Unknown host extensions, nested discovery layout, and the recommended 500-line body budget are warnings. Warnings do not fail the run. Discovery layout is a repository convention, not a universal host guarantee.

Report concrete findings. This validates structure, not whether a skill activates appropriately or supports good decisions. See [README](../../README.md) and the [Agent Skills specification](https://agentskills.io/specification).
