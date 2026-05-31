<!-- INTENTIONAL FAULT — DO NOT FIX -->

# Expected verdict: MUST FIX

**Fault:** The `if config is None` guard was deleted. On the documented first-run
path (`config is None`), `config.timeout` raises `AttributeError`. The acceptance
criterion ("when `config` is `None`, return the default `30`") is **UNSATISFIED**,
and the comment's "callers always pass a config now" claim contradicts the spec.

**Critic must surface:** a MUST FIX correctness/error-handling finding on the
removed `None` guard, and mark the default-on-`None` criterion UNSATISFIED.

**False pass** = any recorded verdict other than `MUST FIX`.
