# Task 8 — De-duplicate agent roster from /crew command

**Status:** DONE
**Date:** 2026-05-25
**Agent:** smith

## Changes Made

### `plugins/fakoli-crew/commands/crew.md`

Removed the 8-row inline agent roster table (old lines 14-23):

```
| Agent | Color | Role | Invoke When |
...
| sentinel | orange | QA engineer | ... |
```

Replaced with a single link to the canonical roster:

```markdown
See [`skills/crew-ops/references/agent-roster.md`](../skills/crew-ops/references/agent-roster.md) for the canonical 8-agent roster (names, colors, roles, and file paths).
```

## Acceptance Criteria

- [x] 8-row roster table (`| guido | blue |` pattern) is gone from `commands/crew.md`
- [x] `agent-roster.md` is referenced by name in the file
- [x] "Pre-Built Crews" section is preserved intact (Code Quality, Plugin Development, Research & Build, Documentation Sprint, Full Overhaul)
- [x] Command frontmatter (`description`, `argument-hint`, `allowed-tools`) is unchanged
- [x] Verify command exits 0: `PASS`

## Preserved Content

The following sections are unchanged:
- Frontmatter (lines 1-6)
- Intro prose linking to `crew-ops` skill
- All 5 Pre-Built Crews with wave patterns and agent lists
- Usage section with `/agent:` invocation examples
