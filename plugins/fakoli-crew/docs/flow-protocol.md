# Fakoli Flow Integration Protocol

This document defines how fakoli-crew agents integrate with the **fakoli-flow** orchestration plugin (and any compatible orchestrator).

## Agent Dispatch Protocol

Any orchestrator can dispatch a fakoli-crew agent by using the Claude Code Agent tool:

```
/agent:<name> <task description>
```

The orchestrator provides:
- **Task description** — what the agent should do, with enough context to work independently
- **File scope** — which files/packages the agent should focus on
- **Upstream context** — any decisions from prior agents the agent must honor

The agent returns:
- **Modified files** — listed in its status file
- **Decisions** — key choices downstream agents need to know
- **Status** — COMPLETE, NEEDS_REVIEW, or BLOCKED

## Status File Protocol

Every agent writes a status file at `docs/plans/agent-<name>-status.md`. This is the inter-agent communication channel.

### Format

```markdown
# Agent <Name> Status

**Status:** IN_PROGRESS | COMPLETE | NEEDS_REVIEW | BLOCKED
**Wave:** <number>
**Timestamp:** <YYYY-MM-DD HH:MM UTC>

## Files Modified
- `path/to/file.ts` — what was changed

## Files Read (not modified)
- `path/to/file.ts` — why it was read

## Decisions
Key choices downstream agents must honor:
1. Decision with rationale

## Notes for Specific Agents
- **<agent-name>:** specific instructions for that agent

## Blockers (if BLOCKED)
What is preventing progress and what is needed
```

### Status Values

| Status | Meaning | Next Action |
|---|---|---|
| `IN_PROGRESS` | Agent is working | Downstream agents wait |
| `COMPLETE` | Agent finished successfully | Downstream agents may proceed |
| `NEEDS_REVIEW` | Agent found an issue requiring human judgment | Orchestrator reviews before continuing |
| `BLOCKED` | Agent cannot proceed | Orchestrator resolves the blocker |

**Writing rule:** Write `IN_PROGRESS` immediately when the task begins, so the orchestrator
knows the agent is active. Set `COMPLETE` only when all acceptance criteria are met.

> The authoritative status file format, including reading rules, writing rules, and
> complete examples, is defined in
> `fakoli-flow/references/status-protocol.md`. This section summarizes the format for
> crew agents working without the flow plugin.

## Wave Compatibility

fakoli-crew agents are designed for wave-based execution:

| Wave | Agents | Purpose |
|---|---|---|
| Research | scout, critic | Gather information, no code changes |
| Build | guido, smith, herald | Create new artifacts |
| Integrate | welder | Wire new code into existing systems |
| Review | critic, sentinel | Validate, report findings |
| Judge | orchestrator | Review findings, dispatch fixes |

The orchestrator decides which agents run in which wave. Agents within the same wave run in parallel. Agents in different waves run sequentially.

## Agent Capabilities Registry

Each agent declares its capabilities so the orchestrator can match tasks:

| Agent | Creates Files | Modifies Files | Reviews Only | Needs Store Access |
|---|---|---|---|---|
| guido | Yes (new modules, interfaces) | No (existing files) | No | No |
| critic | No | No | Yes | No |
| scout | Yes (research docs) | No | No | Yes (web access) |
| smith | Yes (manifests, commands) | Yes (plugin structure) | No | No |
| welder | Yes (shims, adapters) | Yes (integration) | No | No |
| herald | Yes (READMEs, docs) | Yes (existing docs) | No | No |
| keeper | No | Yes (infra files) | No | No |
| sentinel | No | No | Yes | Yes (runs commands) |

## Orchestrator Requirements

Any orchestrator compatible with fakoli-crew must:

1. **Dispatch agents** via the Agent tool with clear task descriptions
2. **Read status files** between waves to check for BLOCKED or NEEDS_REVIEW
3. **Enforce file ownership** — no two agents modify the same file in the same wave
4. **Run critic after code writes** — this is a standing gate, not optional
5. **Run typecheck between waves** — `npx tsc --noEmit` or equivalent
6. **Handle NEEDS_REVIEW** — surface the issue to the human and wait for resolution

## Integration: fakoli-flow

**fakoli-flow** implements this protocol as a first-class orchestrator. Install it
alongside fakoli-crew for the full workflow:

```bash
claude plugin install fakoli-crew
claude plugin install fakoli-flow
```

fakoli-flow provides:
- `brainstorm` → design specs with 1-question-at-a-time flow
- `plan` → break specs into tasks assigned to crew agents
- `execute` → dispatch agents in waves with critic gates
- `verify` → sentinel validation before completion claims
- `finish` → git merge/PR/keep/discard

The wave engine reads agent status files automatically between waves, enforces file
ownership, and runs the critic gate after every code wave — all behaviors described in
this document are handled without manual orchestration.

See [fakoli-flow README](../../fakoli-flow/README.md) and
[docs/workflow-orchestration.md](workflow-orchestration.md) for setup and usage.
