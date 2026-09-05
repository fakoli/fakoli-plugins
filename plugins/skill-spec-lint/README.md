# skill-spec-lint

Validate Agent Skills using complete YAML parsing and deterministic field checks. Native Codex skills and Claude commands are both included.

## Run

Requires Python 3.10+ and PyYAML. `uv` resolves the declared dependency in an isolated environment:

```bash
uv run --script scripts/skill_spec_lint.py [PATH ...]
```

Run from this plugin directory, or use an absolute script path from any directory. A path may be a `SKILL.md`, skill directory, plugin, or repository. Overlapping inputs count once. `--help` prints usage.

The first `uv` run may download dependencies. Validation itself is local. Direct Python execution works when PyYAML is installed; absence of the parser fails clearly instead of reporting a partial pass.

## Checks

| Check | Result |
|---|---|
| Required name/description strings; name length, syntax, and directory match | Error |
| Description and compatibility limits; optional field types; string metadata | Error |
| Invalid YAML, duplicate keys, missing/unterminated frontmatter | Error |
| A discovered skill directory without a readable SKILL.md | Error |
| Recommended 500-line body budget | Warning |
| Nested discovery layout or unknown host extensions | Warning |

Errors return 1. CLI or dependency failures return 2. Warnings return 0. Host discovery rules differ; the immediate-child check describes this repository's package convention. Structure checks do not establish whether a skill triggers well or produces useful results.

## Development

```bash
uv run --with pyyaml python tests/test_skill_spec_lint.py
uv run --with pyyaml python -m unittest discover -s tests -p 'test_yaml_contract.py'
```

Source: [Agent Skills specification](https://agentskills.io/specification). License: MIT.
