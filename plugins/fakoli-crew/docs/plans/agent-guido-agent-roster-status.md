# Status: agent-roster (guido, Wave 1, Task 3)

**Status:** COMPLETE

## Task

Create canonical agent roster reference at `plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md`.

## Decisions

- Synthesized columns from both sources: SKILL.md contributed "Best For", crew.md contributed "Color" and "Invoke When" (renamed "Best For" from both). The merged table uses Agent | Color | Role | Best For | File.
- "File" column uses paths relative to plugin root (`agents/<name>.md`), matching the actual directory layout.
- Added a "Notes" section covering the Color field's purpose, critic's standing-gate role, and sentinel's evidence-based approach — information that was implicit across the two sources.
- Prose is objective/descriptive throughout; no "use this agent when" framing.
- Word count: 303 (within 200–800 target).

## Files Modified

- `plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md` — created (new canonical source)
- `plugins/fakoli-crew/docs/plans/agent-guido-agent-roster-status.md` — this file

## Verify

```
test -f plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md && [ "$(grep -c "^| " plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md)" -ge 9 ]
```

Result: PASS

## Handoff Notes for Wave 2

- Task 4 (updates to SKILL.md) and Task 8 (updates to crew.md) may now replace their inline 8-row roster tables with a link to `skills/crew-ops/references/agent-roster.md`.
- The roster file is complete and should not need further edits unless an agent is added, renamed, or its color changes.
