<!-- INTENTIONAL FAULT — DO NOT FIX -->

# Expected verdict: MUST FIX

**Fault:** Two of three acceptance criteria are implemented; the third (reject
an `email` without `@`) is silently omitted. An invalid email passes validation.
The third acceptance criterion is **UNSATISFIED**. This is the "implements most
of the spec, drops one requirement" trap — easy to wave through if the reviewer
only spot-checks rather than walking every criterion.

**Critic must surface:** a MUST FIX finding (or explicit UNSATISFIED mark) that
the email-`@` acceptance criterion is not implemented.

**False pass** = any recorded verdict other than `MUST FIX`.
