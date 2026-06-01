# Agent Communication

Agents in a crew do not share a conversation. Each runs in its own sub-agent window.
Communication happens through files: each agent writes a structured status file that
other agents read before starting their own work.

## Status File Location

Each agent writes its status to the path the orchestrator provides in the dispatch prompt.
The orchestrator must always supply an absolute path. The default scratch root is:

```
.fakoli/runs/<run-id>/
```

Example paths (orchestrator-assigned, not fixed):
- `.fakoli/runs/abc123/agent-guido-status.md`
- `.fakoli/runs/abc123/agent-welder-status.md`
- `.fakoli/runs/abc123/agent-sentinel-status.md`

## Status File Format

```markdown
# Agent <Name> Status

**Status:** IN_PROGRESS | COMPLETE | NEEDS_REVIEW
**Wave:** 1 | 2 | 3 | 4
**Timestamp:** 2024-01-15 14:32 UTC

## Files Modified
- `src/protocols.py` — created new ProviderProtocol with synthesize(), stream()
- `src/providers/__init__.py` — created, exports all provider classes
- `src/providers/openai.py` — refactored to implement ProviderProtocol

## Files Read (not modified)
- `.fakoli/runs/abc123/agent-scout-status.md`
- `src/client.py` — existing interface understood, backward compat required

## Decisions
Key choices that downstream agents must know:

1. **Protocol method signature:** `synthesize(text: str, voice_id: str) -> bytes`
   Welder must use this exact signature when wiring into client.py.

2. **Provider discovery:** Providers are registered via `__init_subclass__` hook,
   not an explicit registry list. Welder does not need to update any list.

3. **Backward compat:** `TTSClient.generate()` is the old public API. It must keep
   working. I have NOT changed client.py — welder owns that refactor.

## Blockers
Issues that prevent downstream agents from proceeding:

- None.

## Notes for Specific Agents
- **welder:** `ProviderProtocol` is in `src/protocols.py`. Import as
  `from mypackage.protocols import ProviderProtocol`. Do not import from `src/providers/`.
- **sentinel:** Version was NOT bumped. That happens after welder integrates.
  Check version only after Wave 3 completes.
- **herald:** The new feature is "multi-provider support" — mention in README that
  users can now switch providers via config without changing code.
```

## Reading Status Files

Every agent that operates in Wave 2 or later must:

1. **Check which upstream agents have status files** using Glob on the orchestrator-provided scratch root:
   ```
   <orchestrator-provided-path>/agent-*-status.md
   ```
2. **Read ALL status files** from upstream waves before writing anything.
3. **Extract the Decisions section** — these are the contracts you must honor.
4. **Extract the Notes for Specific Agents** section — check if your name appears.

## Writing Your Status File

Write your status file in two stages:

**At start of work** (Status: IN_PROGRESS):
```markdown
# Agent Welder Status
**Status:** IN_PROGRESS
**Wave:** 3
**Timestamp:** 2024-01-15 14:45 UTC

## Files Read
- .fakoli/runs/abc123/agent-guido-status.md
- .fakoli/runs/abc123/agent-smith-status.md
- src/client.py
- src/protocols.py
```

**At completion** (Status: COMPLETE or NEEDS_REVIEW):
```markdown
# Agent Welder Status
**Status:** COMPLETE
**Wave:** 3
**Timestamp:** 2024-01-15 15:12 UTC

## Files Modified
- src/client.py — refactored to delegate to ProviderProtocol
- src/compat.py — created, re-exports TTSClient for backward compat
- pyproject.toml — bumped version to 2.0.0

## Decisions
1. Used adapter pattern rather than facade — client.py now wraps provider directly.
2. Kept `TTSClient.generate()` signature unchanged. New providers use it automatically.

## Notes for Specific Agents
- **sentinel:** All 47 tests pass. Version is now 2.0.0 in pyproject.toml, plugin.json,
  and src/__init__.py.
- **herald:** Call out that `TTSClient` API is unchanged — existing users need zero
  migration.
```

## Status Values

| Status | Meaning |
|---|---|
| `IN_PROGRESS` | Agent is currently working; downstream agents should wait |
| `COMPLETE` | Agent finished; all downstream agents may proceed |
| `NEEDS_REVIEW` | Agent finished but found issues that require human judgment |
| `BLOCKED` | Agent cannot proceed; lists what it is waiting for |

## Escalating to the Orchestrator

If your work reveals something that changes the project plan — a hidden dependency,
an architectural conflict, a discovered breaking change — set status to `NEEDS_REVIEW`
and describe the issue clearly. Do not make the decision yourself; surface it.

```markdown
**Status:** NEEDS_REVIEW

## Escalation
Discovered that `src/client.py` has 14 direct callers in `tests/` that use the
internal `_provider` attribute (not the public API). Refactoring without touching tests
will break those calls. Options:

1. Update tests to use the public API (guido's territory — but it's a lot of changes)
2. Keep `_provider` as an internal alias (welder can do this, backward compat preserved)
3. Add a deprecation warning on `_provider` access (requires guido to design the warning)

Recommend option 2 as the safest. Awaiting orchestrator decision.
```

## Status Files Are Ephemeral (Not Archived)

Status files are run-local scratch under `.fakoli/runs/<run-id>/` (gitignored). They have no value once a run completes and must NOT be moved into a tracked directory such as `archive/` — doing so would re-commit scratch and violate P10 (tool scratch lives outside version control). Let them be discarded with the run directory. Only durable plan and spec docs under `docs/plans/` and `docs/specs/` are version-controlled.

Active run directories under `.fakoli/runs/<run-id>/` contain in-progress or recent sessions. The orchestrator is responsible for pointing agents at the correct run directory.
