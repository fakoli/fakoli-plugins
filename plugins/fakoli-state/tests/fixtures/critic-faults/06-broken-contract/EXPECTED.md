<!-- INTENTIONAL FAULT — DO NOT FIX -->

# Expected verdict: MUST FIX

**Fault:** `parse()` now returns a 3-tuple instead of the documented
`{"items": ..., "ok": ...}` dict. Every existing caller doing `result["items"]`
or `result["ok"]` breaks (`TypeError`/wrong indexing). The acceptance criterion
("preserve the public contract of `parse()`") is **UNSATISFIED**. The added
count could have been delivered without breaking the shape (e.g. a `count` key).

**Critic must surface:** a MUST FIX finding that the public return contract was
changed, breaking callers; mark the "preserve the public contract" criterion
UNSATISFIED.

**False pass** = any recorded verdict other than `MUST FIX`.
