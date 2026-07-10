---
description: Run a spec-independent breakage pass over the current change (fail-closed, malformed-input, exhaustion, state-drift)
---

Use the `recall-mode-verifier` skill for: $ARGUMENTS

Default target is `git diff main...HEAD`. Generate breakage probes along the
four axes without re-reading the change's own tests first; report CONFIRMED /
PLAUSIBLE findings ranked by severity. Do not fix.
