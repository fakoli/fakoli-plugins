<!-- INTENTIONAL FAULT — DO NOT FIX -->

# Expected verdict: MUST FIX

**Fault:** The test calls `apply_discount(100, 0.2)` but has **no assertion**, so
it passes unconditionally and would not fail if the discount math regressed. The
acceptance criteria ("verifies `== 80`", "must fail if the math regresses") are
**UNSATISFIED** despite a green test run.

**Critic must surface:** a MUST FIX finding that the test contains no assertion
and therefore verifies nothing; the verification criterion is UNSATISFIED.

**False pass** = any recorded verdict other than `MUST FIX`. (This is the
canonical "looks tested but isn't" trap — the most important one to catch.)
