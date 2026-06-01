# Example Dispatch Prompt

When constructing the prompt sent to an agent via the `Agent` tool from the `execute` skill, include the six required fields documented in `skills/execute/SKILL.md` (Task name **and intent**, Acceptance criteria, Scope, Upstream context, Verify command, Status file instruction). In the example below, Task and Intent are written as two adjacent labeled sections — they form a single required field but are kept visually separate for readability.

The following is a concrete, complete example showing all six fields. Use it as a template — copy the shape, swap in the values from the current plan task and prior-wave status files.

```
Task: Implement retry with exponential backoff

Intent: Failed executions must be retried with increasing delay before routing to the dead letter queue.

Acceptance criteria:
- Configurable max retries (default 3) and initial delay (default 1000ms)
- Delay doubles each attempt with +/-10% jitter to prevent thundering herd
- Retries exhausted -> route to DLQ, not silent failure
- Each retry creates a new execution attempt linked to the same thread

Scope: packages/orchestrator/src/retry.ts

Upstream context (from Wave 1 scout):
- packages/orchestrator/src/queue-manager.ts exists with enqueueTimer()
- No existing delay utility found; implement one inline

Verify: bun test packages/orchestrator/src/retry.test.ts

When done, write your status to: /abs/project/.fakoli/runs/2026-06-01-retry-mechanism-202606011430/agent-welder-status.md
Use the standard format: Status, Wave, Timestamp, Files Modified, Files Read, Decisions, Notes for Specific Agents.
```

## What makes this a good dispatch prompt

- **Intent comes before acceptance criteria.** Agents need to understand the "why" before the "what" — it lets them flag scope creep or surface better alternatives.
- **Scope is a list of exact file paths**, not a directory or a vague description. This is what file ownership enforces — no two agents in the same wave touch the same path.
- **Upstream context is verbatim from prior status files**, not a paraphrase. The wave engine extracts "Decisions" sections from completed agents and pastes them into the next wave's prompt.
- **The verify command is exactly what the agent should run before declaring COMPLETE.** It usually matches the `Verify:` field in the plan task.
- **The status-file instruction names the exact absolute path and lists the required sections**, so the agent does not have to infer the protocol from prior context. The orchestrator derives the absolute path from the run ID (plan basename + UTC timestamp) and injects it; the agent writes where told.

For the full status-file format the agent will write back, see `references/status-protocol.md`.
