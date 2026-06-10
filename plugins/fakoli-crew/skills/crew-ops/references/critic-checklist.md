# Critic Review Checklist

The full working checklist for critic reviews. The critic agent keeps the MUST FIX
safety floor inline in its prompt; this file carries the complete, evolvable detail.
Add new patterns here — the agent prompt does not need a version bump for checklist
growth.

## Safety and Correctness (MUST FIX)

- [ ] Unvalidated state transitions — any status change that bypasses the transition validator
- [ ] API contract violations — implementation behavior doesn't match interface/method name
- [ ] Arbitrary code execution — shell commands from user input without sandboxing
- [ ] Resource leaks — unclosed connections, unbounded maps, timers never cleared
- [ ] Security — API keys logged, spoofable auth, unauthenticated mutation endpoints
- [ ] Circular dependencies — trace the import graph manually
- [ ] Dead code paths — code that is constructed/imported but never invoked
- [ ] Read-after-write ordering — reading state after a mutation that invalidates the read

## Quality (SHOULD FIX)

- [ ] Missing type safety — `any` types, unsafe casts, unvalidated external data
- [ ] Inconsistent naming — mixing conventions, wrong suffixes on errors
- [ ] No error handling on external calls (HTTP, subprocess, file I/O)
- [ ] N+1 query patterns — per-item queries in a loop
- [ ] Off-by-one errors in limits, counters, and pagination
- [ ] Interface compliance — does the class actually implement all required methods?
- [ ] Error type accuracy — throwing the wrong error type for the failure mode
- [ ] Frontend/backend contract mismatch — wrong HTTP methods, mismatched URLs, divergent types
- [ ] Silent fail-open — error handlers that swallow and continue where the safe default is to stop
- [ ] Concurrency assumptions — single-writer logic reachable from concurrent call sites

## Polish (CONSIDER / NIT)

- [ ] Missing doc comments on public API
- [ ] Minor style issues (import order, unused imports)
- [ ] Redundant code that could use standard library or utility types
