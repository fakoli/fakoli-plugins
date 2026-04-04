# File Ownership

Conflicts happen when two agents modify the same file concurrently. The ownership model
prevents this: every file belongs to exactly one primary agent per session. Secondary
agents that need information from a file read it but do not modify it — they communicate
their required changes to the primary via a status file.

## Ownership Assignment Rules

1. **Primary ownership is set at Wave 2 planning time**, before any agent starts work.
2. **One file, one primary owner**. No exceptions for concurrent waves.
3. **Readers never become writers** without a handoff through a status file.
4. **The orchestrator resolves conflicts** if two agents claim the same file.

## Default Ownership Table

| File / Pattern | Primary Owner | Secondary (read-only) |
|---|---|---|
| `agents/*.md` | smith | critic, sentinel |
| `skills/**/*.md` | guido | herald |
| `commands/*.md` | smith | welder |
| `plugin.json` | smith | sentinel, keeper |
| `pyproject.toml` | welder | sentinel, keeper |
| `src/**/*.ts` (new files) | guido | welder, critic |
| `src/**/*.ts` (existing files) | welder | critic, sentinel |
| `README.md` | herald | keeper, sentinel |
| `CLAUDE.md` | keeper | sentinel |
| `marketplace.json` | keeper | sentinel |
| `registry.json` | keeper | sentinel |
| `.github/workflows/*.yml` | keeper | sentinel |
| `docs/contributing.md` | keeper | herald |
| `docs/plans/agent-*.md` | (each agent owns their own) | sentinel |
| `tests/**/*.test.ts` | guido | sentinel |
| `archive/**` | keeper | — |

## How to Handle Overlapping Needs

### Scenario: herald needs smith to add a field to plugin.json

herald does NOT modify plugin.json. Instead:

1. herald writes its status file:
```markdown
# agent-herald-status.md
Status: COMPLETE
Files Modified: README.md

Decisions:
- Added "providers" section to README referencing plugin.json `providers` key
- NOTE FOR SMITH: README references plugin.json field `providers[].display_name`
  which does not exist yet. Smith should add this field before release.
```

2. smith reads herald's status file during its own pass and adds the field.

### Scenario: welder needs guido's new module to be importable from an old path

welder does NOT modify guido's new module. Instead:

1. welder creates a compatibility shim in `src/compat.ts` (owned by welder):
```typescript
export { NewProcessor as Processor } from './new-module';
```

2. welder's status file records:
```markdown
Files Modified: src/compat.ts, package.json
Decision: Old import path `import { Processor } from 'mypackage'` preserved via compat.ts.
          guido's new_module.py was NOT modified.
```

## Example Ownership Tables for Common Projects

### Plugin Development Session

```
plugin.json          → smith (primary)
agents/guido.md      → smith (primary)
agents/critic.md     → smith (primary)
src/loader.ts (new)  → guido (primary)
src/hooks.ts (new)   → guido (primary)
src/client.ts (existing) → welder (primary)
README.md            → herald (primary)
CLAUDE.md            → keeper (primary)
marketplace.json     → keeper (primary)
docs/plans/*.md      → each agent owns their own
```

### Marketplace Overhaul Session

```
plugins/*/README.md  → herald (primary, one instance per plugin)
plugins/*/plugin.json → smith (primary, one instance per plugin)
marketplace.json     → keeper (primary)
CLAUDE.md            → keeper (primary)
.github/workflows/   → keeper (primary)
```

### Multi-Provider Refactor Session

```
src/protocols.ts (new)          → guido (primary)
src/providers/elevenlabs.ts (new) → guido (primary)
src/providers/azure.ts (new)    → guido (primary)
src/client.ts (existing)        → welder (primary)
src/compat.ts (new)             → welder (primary)
plugin.json                     → smith (primary)
pyproject.toml                  → welder (primary)
README.md                       → herald (primary)
```

## Conflict Resolution

If two agents were assigned the same file by mistake:

1. **Stop both agents** before either writes.
2. **Designate a primary** based on which agent's change is more structural.
3. **The secondary** writes its required changes to its status file.
4. **The primary** reads the secondary's status file and incorporates the changes.

The orchestrator (main window) is responsible for detecting and resolving conflicts at
Wave 2 planning time, not after the fact.
