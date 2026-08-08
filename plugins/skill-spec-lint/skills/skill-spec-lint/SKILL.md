---
name: skill-spec-lint
description: Lint Agent Skills against the deterministic rules of the spec — name charset/length and directory match, description length, SKILL.md body line ceiling, and immediate-child placement under skills/. Use before publishing or reviewing a skill, when the user asks to "validate a skill", "lint SKILL.md", "check a skill against the spec", "does this skill follow the spec", or after authoring/editing any SKILL.md. Deterministic and stdlib-only — complements manifest-validity checks and LLM skill reviewers, not a replacement for either.
user-invocable: true
---

# Skill Spec Lint

Deterministic conformance check for the [Agent Skills spec](https://agentskills.io/specification).
Manifest validators confirm a `SKILL.md`'s frontmatter is *valid YAML*; this
checks the *semantic* rules they don't. No dependencies — `python` and the
standard library only, so it runs on any machine with nothing installed.

## Run it

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/skill_spec_lint.py" [PATH ...]
```

`PATH` may be a skill directory (contains `SKILL.md`), a plugin directory
(contains `skills/`), or a repo root (scanned for `plugins/*/skills/*/SKILL.md`
and `skills/*/SKILL.md`). With no argument it lints the current directory.

## What it checks

Each finding prints as `path: LEVEL: message`. **ERROR** fails the run (exit 1);
**WARN** never does (exit 0).

- **`name`** (ERROR): required; 1–64 chars; lowercase alnum words joined by
  single hyphens (no leading, trailing, or consecutive hyphens); must equal the
  skill's directory name.
- **`description`** (ERROR): required; 1–1024 characters. Folded (`>`) and
  literal (`|`) block scalars are measured as their joined text.
- **`compatibility`** (ERROR): if present, ≤500 characters.
- **SKILL.md body** (ERROR): ≤500 lines after the frontmatter — move detail to
  `references/`.
- **Frontmatter block** (ERROR): a `--- … ---` block must open on line 1 and
  close; a leading-prose file has no discoverable frontmatter.
- **Placement** (WARN): a `SKILL.md` nested deeper than an immediate child of a
  `skills/` directory is never discovered.
- **Unknown keys** (WARN): frontmatter keys outside the spec's optional set
  (`license`, `compatibility`, `metadata`, `allowed-tools`) plus the
  Claude Code `user-invocable` extension.

## Notes

- Frontmatter is parsed authoritatively with PyYAML when it is importable;
  otherwise a scalar-only parser recovers `name`/`description`/`compatibility`
  and a reduced-coverage note is printed to stderr.
- This is deterministic conformance only. It does not judge whether a
  description will *trigger* well or whether the body is good — pair it with an
  LLM skill reviewer for that.
