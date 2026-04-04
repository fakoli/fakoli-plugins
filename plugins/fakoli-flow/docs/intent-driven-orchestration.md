# Intent-Driven Orchestration

The core design philosophy of fakoli-flow.

## The Principle

fakoli-flow tells agents **WHAT** to achieve, never **HOW** to achieve it.

Plans are contracts, not recipes. They describe intent, acceptance criteria, and scope — then trusted specialist agents decide the implementation. The agents have domain expertise (TDD methodology, language-specific patterns, integration best practices) that a plan written in advance cannot match.

## Why Intent-Driven

Traditional plan-driven tools (including SuperPowers) write implementation code directly into plans: full function bodies, complete test files, exact line-by-line instructions. This creates three problems:

1. **Plans go stale.** The moment implementation diverges from the plan (and it always does), the plan becomes misleading. Downstream tasks that reference earlier tasks' code are now wrong.

2. **Plans suppress expertise.** A plan that prescribes `export function retry<T>(fn: () => T, opts: RetryOptions)` prevents the agent from designing a better signature based on what it discovers when it reads the actual codebase. The plan author's snapshot understanding overrides the agent's live understanding.

3. **Plans are unnecessarily long.** A 3,000-line plan with full code blocks is harder to review, harder to modify, and consumes context window that should be available to the agent doing the actual work.

## The Comparison

### Prescriptive Plan (SuperPowers-style)

```markdown
### Task 3: Implement the retry function

- [ ] Step 1: Write failing test
\`\`\`typescript
test("retries with exponential backoff", () => {
  const result = retry(failingFn, { maxRetries: 3, initialDelay: 100 });
  expect(result.attempts).toBe(3);
  expect(result.delays).toEqual([100, 200, 400]);
});
\`\`\`

- [ ] Step 2: Implement
\`\`\`typescript
export function retry<T>(fn: () => T, opts: RetryOptions): RetryResult<T> {
  let attempt = 0;
  let delay = opts.initialDelay;
  while (attempt < opts.maxRetries) {
    try { return { value: fn(), attempts: attempt + 1 }; }
    catch (err) {
      attempt++;
      if (attempt >= opts.maxRetries) throw err;
      sleep(delay + jitter(delay));
      delay *= 2;
    }
  }
}
\`\`\`

- [ ] Step 3: Run test → verify passes
- [ ] Step 4: Commit
```

**Problems:**
- The test assumes a `RetryResult<T>` type that may not exist yet
- The implementation prescribes `sleep()` which may not be the right primitive for this runtime
- If the codebase already has a delay utility, the plan doesn't know about it
- 30+ lines of plan for one function

### Intent-Driven Plan (fakoli-flow-style)

```markdown
### Task 3: Retry with exponential backoff

**Intent:** Failed executions must be retried with increasing delay before routing to the dead letter queue.

**Acceptance criteria:**
- Configurable max retries (default 3) and initial delay (default 1000ms)
- Delay doubles each attempt with ±10% jitter to prevent thundering herd
- Retries exhausted → route to DLQ, not silent failure
- Each retry creates a new execution attempt linked to the same thread

**Scope:** packages/orchestrator/src/retry.ts

**Agent:** welder (TDD enforced — will write failing test first)

**Verify:** `bun test` — retry scenarios pass, DLQ routing confirmed

**Depends on:** Task 2 (queue manager must be in place)
```

**Advantages:**
- 10 lines vs 30+ — the plan is a spec, not a codebase
- The agent reads the actual codebase before implementing
- If a delay utility already exists, the agent uses it
- The acceptance criteria are testable regardless of implementation approach
- A human can review this plan without reading code

## The Trust Model

Intent-driven orchestration requires trusting the agents. This trust is earned through:

1. **Baked-in discipline.** Agents have TDD, systematic debugging, and verification gates in their prompts — not in the plan. The plan doesn't need to say "write a test first" because the agent always does.

2. **Critic gates.** After every wave of execution, a critic agent reviews the output against the acceptance criteria. The plan describes WHAT to check; the critic decides if it's met.

3. **Acceptance criteria as contract.** The criteria are specific enough to verify ("delay doubles each attempt") but not so specific that they constrain implementation ("use `setTimeout` with `Math.pow(2, attempt)`").

4. **Scope boundaries.** Each task names the files it touches. If the agent needs to modify files outside scope, it flags this in its status file rather than silently expanding.

## When Intent-Driven Doesn't Work

Intent-driven plans are wrong for:

- **Schema migrations** — exact SQL matters; intent alone is dangerous. Write the SQL.
- **Security-critical code** — cryptographic operations, auth flows. Prescribe the exact algorithm.
- **API contracts** — if an external system expects a specific request format, specify it.
- **Configuration** — exact config values, env vars, port numbers. Don't let the agent guess.

For these cases, the plan should include the exact content alongside the intent. Intent-driven is the default, not a dogma.

## Real-World Evidence

The BAARA Next project (44,268 lines across 10 packages) was built in 6 phases using a hybrid of prescriptive plans (SuperPowers-style, Phases 4-5) and manual intent-driven dispatch (the orchestrator described what each wave should achieve, then dispatched crew agents).

**Observation:** In phases with prescriptive plans, 30-40% of the plan code was modified by agents during implementation. The plans were still useful as a roadmap, but the code was partially wrong by the time it was executed. In phases with intent-driven dispatch, there was no plan-vs-implementation divergence because the plan never claimed to know the implementation.

**The critic caught the same number of bugs either way** (26 total across prescriptive phases, similar density in intent-driven phases). The quality came from the critic gates and TDD enforcement, not from the plan's level of detail.

## Summary

| Aspect | Prescriptive | Intent-Driven |
|--------|-------------|---------------|
| Plan describes | How (code) | What (criteria) |
| Plan length | Long (full implementations) | Short (intent + scope + verify) |
| Agent autonomy | Low (follow the recipe) | High (achieve the criteria) |
| Plan staleness | Immediate on first divergence | Never (criteria don't change) |
| Trust model | Trust the plan | Trust the agent + verify via critic |
| Review burden | Must read code in plan | Read acceptance criteria only |
| Best for | Schema migrations, security, configs | Features, integrations, refactors |

fakoli-flow defaults to intent-driven. Prescriptive detail is added only when the domain demands it.
