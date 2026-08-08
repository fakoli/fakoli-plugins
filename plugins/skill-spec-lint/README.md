# skill-spec-lint

A deterministic linter for the [Agent Skills spec](https://agentskills.io/specification).
Manifest validators confirm a `SKILL.md`'s frontmatter parses as YAML;
skill-spec-lint checks the *semantic* rules they don't — the ones that make a
skill malformed even when its YAML is perfectly valid.

Python standard library only. No install, no dependency, no CI wiring required —
it runs from a command, a skill, or a plain `python` invocation, on any machine.

## Why

`validate.sh` (and equivalents) answer "is this frontmatter valid YAML?" They do
not answer "is `name` lowercase and does it match the directory?", "is the
description within 1024 chars?", or "is the body under the 500-line ceiling?".
Those are the rules that silently break discovery or trip a spec-strict
consumer, and they are exactly what this fills.

## Use

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/skill_spec_lint.py" [PATH ...]
```

Or invoke the `/skill-spec-lint` command / the `skill-spec-lint` skill in a
session. `PATH` may be a skill directory, a plugin directory, or a repo root;
with no argument it scans the current directory.

Each finding prints as `path: LEVEL: message`. The run exits `1` if there is any
`ERROR`, `0` otherwise — `WARN` findings never fail it.

## Checks

| Rule | Level |
|------|-------|
| `name` required, 1–64 chars, lowercase alnum + single hyphens, matches directory | ERROR |
| `description` required, 1–1024 chars (block scalars measured) | ERROR |
| `compatibility` ≤500 chars when present | ERROR |
| SKILL.md body ≤500 lines | ERROR |
| Frontmatter `--- … ---` opens on line 1 and closes | ERROR |
| SKILL.md nested below an immediate child of `skills/` (undiscoverable) | WARN |
| Frontmatter key outside the spec's optional set | WARN |

## Notes

- Frontmatter is parsed authoritatively with PyYAML when importable; otherwise a
  scalar-only fallback recovers `name`/`description`/`compatibility` and prints a
  reduced-coverage note to stderr. Neither path needs anything installed to run.
- Deterministic conformance only. It does not judge whether a description
  *triggers* well or whether the prose is good — pair it with an LLM skill
  reviewer (e.g. `fakoli-plugin-critic`'s `skill-critic`) for that.
- Deliberately **not** wired into any CI gate. It is a portable tool you point at
  a skill on demand, so it stays usable outside the repo that ships it.

## Development

```bash
python tests/test_skill_spec_lint.py    # offline, no pytest, no network
```

## License

MIT
