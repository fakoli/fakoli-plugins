---
name: debugging
description: This skill should be used when a test is failing inexplicably, when a runtime error appears in production, when a bug reproduces unpredictably, or when two or more prior fix attempts have failed. Provides a 4-phase systematic debugging workflow — investigate, analyze patterns, form hypothesis, fix with test — to prevent random-fix loops.
---
# Systematic Debugging

A structured approach to debugging that prevents "try random fixes until something works."

## When to Use

Activate this skill when any of the following hold:

- A test is failing without an obvious cause.
- A runtime error appears in production.
- A bug report describes unexpected behavior whose source is unclear.
- Two or more fix attempts have already failed.

## The 4 Phases

### Phase 1: Root Cause Investigation
1. Read the error message completely — every line
2. Reproduce the failure consistently
3. Check recent changes: `git diff HEAD~5` and `git log --oneline -10`
4. Trace data flow backward from the symptom to the source
5. Gather evidence: which inputs trigger the bug? Which don't?

### Phase 2: Pattern Analysis
1. Find a working example of similar code in the codebase
2. Compare the broken path against the working path — line by line
3. Identify every difference, not just the obvious one
4. Check: does the working example handle an edge case the broken code doesn't?

### Phase 3: Hypothesis & Test
1. Form a single, specific hypothesis: "X fails because Y does Z when W"
2. Design a minimal test that confirms or disproves the hypothesis
3. Run the test
4. If disproved → return to Phase 1 with new information
5. If confirmed → proceed to Phase 4

### Phase 4: Implementation
1. Write a failing test that reproduces the exact bug
2. Implement the single, minimal fix
3. Run the failing test → should now pass
4. Run ALL tests → should still pass
5. If new failures appear → the fix is wrong, return to Phase 3

## Red Flags (Violations)

Stop immediately if you catch yourself:
- "Let me just try changing X" (no hypothesis)
- Making multiple changes at once (untestable)
- "This fix should work" without running the test
- Fixing a different bug than the one reported
- Deleting or modifying a test to make it pass

## Escalation

If 3+ fix attempts have failed:
1. Stop fixing
2. Question the architecture — the bug may be a design problem
3. Write up what you've learned and escalate to the orchestrator
4. Include: what you tried, what happened, what you now suspect

## Integration with Crew

- **critic** uses this during code review when failures are present
- **welder** uses this when integration breaks existing tests
- **sentinel** uses Phase 1 to diagnose failing checks before reporting
