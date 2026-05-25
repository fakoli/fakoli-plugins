# Task 3 Status — Write the SKILL.md and manifest templates

**Status:** COMPLETE
**Date:** 2026-05-24
**Agent:** Herald

## Files created

- `plugins/cli-to-plugin/templates/group-skill.md` — per-group skill reference using `gh-pr` as the example
- `plugins/cli-to-plugin/templates/meta-skill.md` — workflow meta-skill reference using `gh-review-and-merge` as the example
- `plugins/cli-to-plugin/templates/plugin.json.example` — generated plugin manifest reference using `gh` as the example

## Verification

```
uv run --with jsonschema python -c "..." && grep -l 'Use when' plugins/cli-to-plugin/templates/*.md | wc -l | grep -q 2
```

Output: `OK` then `BOTH CHECKS PASS`

## Key decisions

- All frontmatter keys use **hyphenated** form (`user-invocable`, `disable-model-invocation`, `argument-hint`, `allowed-tools`) — NOT underscore. The `templates/basic/` SKILL.md uses `user_invocable` which is a known schema violation; these templates do not replicate that bug.
- All `description` values start with **"Use when..."** per convention.
- `plugin.json.example` has `author` as an object `{"name": "..."}`, not a bare string.
- `keywords` array includes `"cli-to-plugin"` as the generator provenance tag.
- `description` in `plugin.json.example` is 74 characters — within the schema's `minLength: 10` / `maxLength: 500` bounds.
- Each template file opens with an HTML comment marking it as a structural reference, not a substitution template.
- The `.gitkeep` in `plugins/cli-to-plugin/templates/` was replaced by the three real files.
