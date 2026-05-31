<!-- INTENTIONAL FAULT — DO NOT FIX -->

# Expected verdict: MUST FIX

**Fault:** Off-by-one slice. `events[-n - 1:-1]` excludes the newest event and
returns the wrong window. The acceptance criterion ("returns the last `n`
events, most-recent last") is **UNSATISFIED**. It also returns `n` items for
typical inputs, masking the bug under shallow testing; on `n >= len(events)` it
silently drops elements instead of returning all.

**Critic must surface:** a MUST FIX correctness finding on the slice bounds,
and mark the "last `n` events" acceptance criterion UNSATISFIED.

**False pass** = any recorded verdict other than `MUST FIX`.
