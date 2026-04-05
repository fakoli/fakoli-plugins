# Intent-Driven Orchestration: Why AI Agent Plans Should Describe What, Not How

There is a temptation, when writing plans for AI agents, to be exhaustive. To write the function signatures. To include the test cases. To spell out every step so nothing is left to chance. It feels rigorous. It feels safe.

It is neither.

---

## The Problem with Prescriptive Plans

When you write a plan that includes implementation code, you are making a bet: that the code you wrote in your planning session will still be correct when an agent executes it later. That bet almost always loses.

Here is what actually happens. You write a plan on Tuesday. The plan includes a function signature: `export function retry<T>(fn: () => T, opts: RetryOptions): RetryResult<T>`. On Wednesday, the agent starts executing. It reads the codebase. It discovers that `RetryResult<T>` does not exist yet. Or that the project already has a delay utility with a different interface. Or that the runtime does not support `sleep()` the way you assumed. The plan is now wrong. The agent either halts, improvises, or — worst of all — faithfully implements the wrong thing.

This is not a hypothetical. When building BAARA Next, a 10-package TypeScript monorepo, we tracked how often agents had to modify plan code during execution. The answer: **30 to 40 percent of implementation code in prescriptive plans was changed before the task was complete.** The plans were useful as roadmaps. The code in them was partially wrong by the time it ran.

Prescriptive plans have three structural problems:

**Plans go stale immediately.** The moment an agent's implementation diverges from the plan — and it always does, because the agent reads the actual codebase and you did not — the plan becomes misleading. Downstream tasks that reference earlier tasks' code are now referencing code that no longer exists as written.

**Plans suppress expertise.** An agent reading a codebase has live, accurate information. A plan written yesterday has a snapshot of information that was already incomplete. When the plan prescribes `export function retry<T>(fn: () => T, opts: RetryOptions)`, it prevents the agent from designing a better signature based on what it finds. The plan author's snapshot overrides the agent's live understanding.

**Plans consume context unnecessarily.** A 3,000-line plan packed with function bodies is harder to review, harder to modify mid-execution, and burns context window that should be available to the agent doing the actual work.

---

## The Comparison

Here is the same task — implement a retry function with exponential backoff — written two ways.

### Prescriptive (SuperPowers-style)

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

Thirty-plus lines. Four problems visible without even running it: `RetryResult<T>` may not exist, `sleep()` may not be the right primitive, the project may already have a delay utility, and the test hardcodes a structure that the agent may reasonably implement differently.

### Intent-Driven (fakoli-flow-style)

```markdown
### Task 3: Retry with exponential backoff

**Intent:** Failed executions must be retried with increasing delay before routing to
the dead letter queue.

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

Ten lines. No implementation code. The acceptance criteria are specific enough to verify — "delay doubles each attempt with ±10% jitter" is testable — but they do not constrain implementation approach. The agent reads the codebase, finds the existing delay utilities, and designs the interface to fit the actual system rather than a remembered snapshot of it.

A human can review this plan without reading any code. That matters.

---

## The Trust Model

Intent-driven orchestration requires trusting agents to make implementation decisions. That trust is not blind faith. It is earned through three mechanisms.

**Baked-in discipline.** The fakoli-crew agents have TDD, systematic debugging, and verification behavior built into their system prompts — not into the plan. The plan does not need to say "write a failing test first" because the `welder` agent always writes a failing test first. The plan does not need to specify error handling patterns because `guido` applies the project's established conventions. The expertise lives in the agent, not the plan.

**Critic gates.** After every wave of execution, the `critic` agent — a Staff Engineer-level code reviewer — reads every modified file against the acceptance criteria. The critic does not trust what the agent said it did. It reads the code. It checks the contracts. It flags state machine violations, API contract mismatches, unauthenticated execution paths, and dead code. The plan says WHAT to verify; the critic decides if it is met.

**Acceptance criteria as contract.** The criteria in an intent-driven plan are written at exactly the right level of specificity: concrete enough to be testable ("delay doubles each attempt"), abstract enough not to prescribe implementation. "Use `setTimeout` with `Math.pow(2, attempt)`" is too specific. "Delay doubles each attempt" is the right level. The agent can satisfy this with any approach that actually works.

---

## Real Evidence: BAARA Next

BAARA Next is a 10-package TypeScript monorepo: 44,268 lines of code, 218 files, built in 6 phases with a mix of prescriptive and intent-driven planning approaches.

Phases 4 and 5 used prescriptive plans (SuperPowers-style, with full function bodies and test cases written in advance). The intent-driven approach was used in phases where the orchestrator described what each wave should achieve and dispatched crew agents against acceptance criteria.

Two findings were consistent across both approaches.

First, the 30-40% modification rate in prescriptive phases. This is not a criticism of prescriptive plans as a starting point — the plans still provided useful structure. But the code in them required significant agent override before it was correct. The agents were more accurate about the codebase than the plans were.

Second, and more important: **the critic caught the same number of bugs either way.** 26 bugs total across the prescriptive phases — 10 MUST FIX in Phase 1 alone, including state machine violations, broken API contracts, and an unauthenticated remote code execution path. Similar bug density in the intent-driven phases.

This is the key insight. Quality did not come from the plan's level of detail. Quality came from the critic gates and the agents' built-in TDD discipline. A prescriptive plan that specifies the implementation does not produce better code. It produces longer plans that go stale faster.

---

## When Intent-Driven Is Wrong

Intent-driven plans are the default, not a dogma. There are cases where prescriptive detail is not just acceptable but required.

**Schema migrations.** The exact SQL matters. Intent alone is dangerous — "migrate the user table to support multi-tenancy" could mean twenty different things with twenty different data consequences. Write the SQL.

**Security-critical code.** Cryptographic operations, authentication flows, and secret handling need exact algorithms, not goals. "Implement secure token generation" is not a plan. The specific algorithm, key length, and rotation schedule belong in the plan.

**API contracts.** If an external system expects a specific request format, wire protocol, or field ordering, specify it. The agent cannot discover this from the codebase — it requires external knowledge the plan must supply.

**Configuration values.** Exact env var names, port numbers, feature flags. Do not let agents guess at configuration. Write the values.

For these cases, the plan includes exact content alongside the intent. The intent grounds the purpose; the prescription handles the parts where the agent's live codebase reading cannot substitute for external or domain knowledge.

---

## The Takeaway

Prescriptive plans are a form of premature implementation. They commit to how before anyone has read the codebase they are supposed to change. They go stale the moment execution diverges from planning — and execution always diverges.

Intent-driven plans stay correct because acceptance criteria do not change when implementation details change. "Delay doubles each attempt with ±10% jitter" is as true at the end of execution as it was at the start. The test the agent writes from that criterion either passes or it does not.

The discipline that produces quality code — TDD, systematic debugging, API contract verification — lives in the agents and the critic gates, not in the plan. The plan's job is to describe the destination clearly enough that a trusted specialist can navigate to it independently.

Write the what. Trust the who. Verify the result.

---

*fakoli-flow implements intent-driven orchestration end to end: brainstorm → intent-driven plan → wave execution → critic gates → evidence-based verification. fakoli-crew provides the specialist agents that execute the plans.*
