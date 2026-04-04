# Agent Status File Protocol

Agents communicate between waves by writing status files. The wave engine reads these
after each wave to confirm completion, detect blockers, extract modified files for the
critic gate, and pass decisions to the next wave's dispatch prompts.

## File Location

```
docs/plans/agent-<name>-status.md
```

`<name>` is the agent's role name (e.g., `welder`, `critic`, `sentinel`, `scout`,
`guido`, `smith`, `herald`). When multiple agents of the same role run in one wave,
append a disambiguator: `agent-welder-packages-store-status.md`.

## Format Template

```markdown
# Agent Status: <role>

**Status:** <status-value>
**Wave:** <wave-number>
**Timestamp:** <YYYY-MM-DD HH:MM UTC>

## Files Modified

- path/to/file.ts
- path/to/other.ts

## Files Read

- path/to/file.ts — why it was read

<!-- NOTE: The "Files Read" section is informational for downstream agents only.
     It is NOT processed by the wave engine. The wave engine reads only "Files Modified"
     (for the critic gate) and "Decisions" (for next-wave upstream context).
     List files here so that downstream agents know what context the writing agent had —
     this avoids redundant reads in subsequent waves. -->

## Decisions

Key decisions made during this task that downstream agents should know about:

- Used `RetryOptions` interface from `src/types.ts` rather than inline type
- Chose exponential backoff over linear — matches existing pattern in queue-manager.ts
- DLQ routing implemented via existing `enqueueTimer()` rather than new method

## Notes

Any additional context, warnings, or observations:

- The retry module depends on clock injection for deterministic testing
- See `src/retry.test.ts` for the full test matrix
```

## Status Values

| Status | Meaning | Wave engine action |
|--------|---------|-------------------|
| `IN_PROGRESS` | Agent is currently working | Wait — do not proceed |
| `COMPLETE` | Task finished, all criteria met | Read decisions, extract files, proceed |
| `NEEDS_REVIEW` | Agent hit an ambiguity requiring human judgment | Surface to user immediately — halt wave |
| `BLOCKED` | Agent cannot proceed (missing dependency, conflicting state) | Surface to user immediately — halt wave |

## Reading Rules

The wave engine reads status files after every agent completes:

1. **Confirm COMPLETE.** If any agent is still `IN_PROGRESS`, wait. If any agent is
   `BLOCKED` or `NEEDS_REVIEW`, surface to the user before proceeding.

2. **Extract Files Modified.** Collect all file paths listed under "Files Modified" from
   all status files in the completed wave. These are the files dispatched to the critic.

3. **Extract Decisions.** Copy the "Decisions" section from each status file into the
   next wave's dispatch prompt as "Upstream context". This is how Wave 3 agents know what
   Wave 2 agents built.

4. **Do not edit status files.** The wave engine reads them; only the writing agent
   modifies them.

## Writing Rules

Agents writing a status file must:

1. **Write to the correct path.** Always `docs/plans/agent-<role>-status.md` relative to
   the project root. Use an absolute path if the project root is ambiguous.

2. **Set status at the start.** Write `IN_PROGRESS` immediately when the task begins, so
   the wave engine knows the agent is active.

3. **List every modified file.** The critic receives exactly this list. If a file is
   modified but omitted, the critic will not review it.

4. **Write decisions, not summaries.** The "Decisions" section exists to reduce
   re-reading by downstream agents. Write what they need to know — interface names, which
   existing utilities were reused, patterns chosen — not a narrative of what you did.

5. **Set COMPLETE only when done.** Do not set `COMPLETE` until all acceptance criteria
   are met and the verify command passes.

6. **Use BLOCKED and NEEDS_REVIEW honestly.** If you cannot proceed without human input,
   set the status, explain why in "Notes", and stop. Do not attempt to work around an
   unresolved blocker.

## Example: Welder Agent

```markdown
# Agent Status: welder

**Status:** COMPLETE
**Wave:** 2
**Timestamp:** 2026-04-02 14:33 UTC

## Files Modified

- packages/orchestrator/src/retry.ts
- packages/orchestrator/src/retry.test.ts

## Decisions

- Implemented `RetryOptions` as a separate exported interface (not inline) so callers
  can type their options objects independently
- Used `shouldRetry(status: number): boolean` as a pure function — no class wrapping
- Jitter applied as `delay * (0.9 + Math.random() * 0.2)` matching the spec's ±10%
- DLQ routing delegates to `queue-manager.ts:enqueueTimer()` — no new method needed

## Notes

- All 12 retry test cases pass: `bun test packages/orchestrator -- retry`
- Clock injection pattern used for deterministic backoff timing in tests
```

## Example: Critic Agent

```markdown
# Agent Status: critic

**Status:** COMPLETE
**Wave:** 4
**Timestamp:** 2026-04-02 14:51 UTC

## Files Modified

(none — critic reads files, does not modify them)

## Decisions

- PASS on packages/orchestrator/src/retry.ts — all acceptance criteria met
- SHOULD FIX: `RetryOptions.maxRetries` could use a JSDoc comment explaining the default
- NIT: test file has two blank lines between describe blocks instead of one

## Notes

- No MUST FIX findings. Proceeding to next wave is safe.
- SHOULD FIX logged for post-ship cleanup.
```
