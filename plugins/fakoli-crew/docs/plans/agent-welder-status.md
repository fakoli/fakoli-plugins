# Welder Status — Fix Cycle 1 (Critic Wave 2 MUST FIX items)

**Date:** 2026-05-25
**Task:** Resolve 2 MUST FIX + 1 SHOULD FIX items from critic report

## Changes Made

### MUST FIX 1 — agent-roster.md herald color
**File:** `plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md`
**Change:** Herald row color updated from `magenta` to `pink` to match `agents/herald.md` frontmatter.

### MUST FIX 2 — guido.md Iron Rule pointer
**File:** `plugins/fakoli-crew/agents/guido.md` (line 98, "Your Process" section item 1)
**Change:** Replaced inline Iron Rule prose with pointer: `**Iron Rule:** See \`skills/crew-ops/references/iron-rule.md\`.`

### SHOULD FIX — sentinel.md obsolete field reference
**File:** `plugins/fakoli-crew/agents/sentinel.md`
**Change:** Replaced `allowed-tools` with `tools` in two locations:
- Section 4 validation checklist (line 95)
- Description example block assistant response (line 36)

Note: The verify command targets `! grep -q "allowed-tools"` across the whole file, so both occurrences required updating.

## Verification

```
grep -q "^| herald | pink |" plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md
grep -q "iron-rule.md" plugins/fakoli-crew/agents/guido.md
! grep -q "allowed-tools" plugins/fakoli-crew/agents/sentinel.md
```

Result: **ALL 3 CHECKS PASS**

## Status

DONE — no remaining failures from Fix Cycle 1 critic report.
