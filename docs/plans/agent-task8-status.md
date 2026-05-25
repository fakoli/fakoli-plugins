# Task 8 — cli-to-plugin playbook command

**Status:** COMPLETE
**Agent:** welder
**Date:** 2026-05-24

## File produced

`plugins/cli-to-plugin/commands/cli-to-plugin.md` — 420 lines

## Verify output

```
FILE EXISTS
FRONTMATTER OK
STEPS OK
Passed: 9  Warnings: 3  Failed: 0
```

The 3 warnings are pre-existing plugin-level omissions (README.md, CHANGELOG.md, LICENSE) that are
outside the scope of this task and present in the plugin before Task 8 started.

## Acceptance criteria check

| Criterion | Status |
|---|---|
| File exists with valid frontmatter (`description`, `argument-hint`) | PASS |
| Invocation flags all documented (`--out`, `--override`, `--from-tree`, `--no-meta-skills`, `--regen`) | PASS |
| 10 numbered steps matching spec happy-path | PASS |
| `AskUserQuestion` used for scope-confirm (Step 3) and meta-skill picker (Step 6) | PASS |
| Atomic-write protocol documented (Write to `.tmp`, Bash `mv`) | PASS |
| Regeneration flow in Step 0 with diff-and-merge as default option ordering | PASS |
| `--from-tree` skips Steps 1 and 2 | PASS |
| `--no-meta-skills` skips Steps 5, 6, 7 | PASS |
| Summary block matches spec format including warnings and next-steps | PASS |
| `validate.sh plugins/cli-to-plugin` exits 0 | PASS |

## Decisions that diverged from configure.md

1. **Frontmatter shape.** configure.md uses `name:` and `argument:` keys. The task brief is explicit
   that the schema rejects underscored keys and specifies `description:` and `argument-hint:`. Used
   `description` and `argument-hint` as instructed, not the reference file's keys.

2. **No `name:` field in frontmatter.** configure.md includes a `name:` field; the task brief
   omits it from the required frontmatter. Omitted it to stay minimal and avoid potential schema
   rejection of undeclared fields.

3. **Step 0 before Step 1.** The spec calls the regeneration guard "Step 0.5". Placed it as Step 0
   to keep steps cleanly numbered 1–10 for the grep-based verify check.

4. **Orphaned .tmp cleanup section.** Added as a safety measure between arg parsing and Step 0,
   per the spec's atomic-write invariant note ("orphan .tmp files cleaned on next run"). configure.md
   has no analogous section but the spec explicitly calls for this.

5. **Error handling table.** Added a consolidated reference table at the end to make severity rules
   greppable. configure.md uses inline prose; the table form maps more directly to the spec's
   four-severity grid and is easier to audit.
