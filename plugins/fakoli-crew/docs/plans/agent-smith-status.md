# Agent Smith — Task 7 Wave 2 Status

Completed: 2026-05-25

## Files Modified

| File | Changes |
|------|---------|
| `plugins/fakoli-crew/agents/critic.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, added `<commentary>` to all 3 examples, replaced `### The Iron Rule` section with pointer to iron-rule.md |
| `plugins/fakoli-crew/agents/guido.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, added `<commentary>` to all 3 examples (no Iron Rule section to remove) |
| `plugins/fakoli-crew/agents/herald.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, `color: magenta` → `color: pink`, added `<commentary>` to all 3 examples, replaced `## Iron Rule` section with pointer to iron-rule.md |
| `plugins/fakoli-crew/agents/keeper.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, added `<commentary>` to all 3 examples, replaced `## Iron Rule` section with pointer to iron-rule.md |
| `plugins/fakoli-crew/agents/scout.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, added `<commentary>` to all 3 examples (no Iron Rule section to remove) |
| `plugins/fakoli-crew/agents/sentinel.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, added `<commentary>` to all 3 examples (no Iron Rule section to remove) |
| `plugins/fakoli-crew/agents/smith.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, added `<commentary>` to all 3 examples, replaced `## Iron Rule` section with pointer to iron-rule.md |
| `plugins/fakoli-crew/agents/welder.md` | `allowed-tools:` → `tools:`, `model: sonnet` → `model: inherit`, added `<commentary>` to all 3 examples, replaced inline `**The Iron Rule:**` paragraph with pointer + retained test-driven integration rule sentence |

## Verify Command Result

```
ALL CHECKS PASSED
```

Command run:
```bash
for f in plugins/fakoli-crew/agents/*.md; do
  grep -q "<commentary>" "$f" || { echo "missing commentary: $f"; exit 1; }
  grep -qE "^tools:" "$f" || { echo "missing tools: $f"; exit 1; }
  ! grep -q "^model: sonnet$" "$f" || { echo "still sonnet: $f"; exit 1; }
done && grep -q "^color: pink$" plugins/fakoli-crew/agents/herald.md
```

## Notes

- `guido.md` and `scout.md` had no dedicated Iron Rule section (no `## Iron Rule` or `### The Iron Rule` heading). Their embedded "read before recommending" prose was left intact as part of their workflow guidance — it is not duplicated canonical text.
- `welder.md`'s `**The Iron Rule:**` appeared inside the Test-Driven Integration section. It was replaced with the pointer plus the retained integration-specific sentence ("Never modify existing code without a failing test...") since that sentence is welder's own rule, not a copy of the canonical Iron Rule prose.
- `smith.md` body contains `allowed-tools:` in code block examples (Command Frontmatter section) — these are intentional documentation, not frontmatter fields, and were not modified.
- Colors confirmed: herald `pink`, sentinel `orange` (unchanged), keeper `purple` (unchanged).

Status: COMPLETE
