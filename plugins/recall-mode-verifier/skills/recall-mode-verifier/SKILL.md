---
name: recall-mode-verifier
description: Generate spec-INDEPENDENT breakage probes for a change — attack it along fail-closed, malformed-input, resource-exhaustion, and state-drift axes, not by re-reading its own tests. Use before opening a PR, as anvil execute's verify-left stage, when the user asks to "recall-mode verify", "red-team this change", "what breaks this", "find failure modes", or wants an independent breakage pass that doesn't reuse the implementer's assumptions. Reports findings; does not fix.
user-invocable: true
---

# Recall-Mode Verifier

**Recall mode** = verify from an independent model of what *must not* break,
NOT from the change's own spec or tests (which encode the implementer's
assumptions — the exact blind spots that ship bugs). This is the focused,
spec-independent specialization of ship-loop's review angles; run it as the
"verify-left" pass before a PR, or as `anvil execute`'s pre-PR stage.

## How to run it

1. Scope the change: `git diff main...HEAD` (or the target diff). Read the
   changed code AND its callers/consumers — a breakage probe often lives at a
   boundary the diff doesn't touch.
2. Do NOT open the change's own tests first. Build your model of the
   invariants from the code's *purpose*, then attack it along the four axes
   below. Only after generating probes, check whether existing tests already
   cover them (uncovered probe = a real gap).
3. For each probe: state the **concrete input/state → the wrong
   output/crash/corruption**. Rank CONFIRMED (constructible from the code) /
   PLAUSIBLE (realistic path, not disproven) / REFUTED (guarded — cite the
   guard). Report CONFIRMED + PLAUSIBLE; **do not fix** — that's the
   implementer's call.

## The four axes (spec-independent)

### 1. Fail-closed
When the state needed to make a safety decision can't be read, does the change
**refuse**, or proceed-with-warning / fail-open?
- Force every external read to fail (missing file, empty output, non-zero
  exit, timeout, permission denied) — does the code default to the SAFE or the
  PERMISSIVE branch?
- A guard that logs-and-continues on an unreadable precondition is fail-open.
- Probe: the incident class the corpus names — an unreadable host RAM figure
  that silently skips the floor; a lease/claim check that proceeds when state
  is ambiguous.

### 2. Malformed input
Feed every input the shape it doesn't expect.
- Empty / null / missing-optional-field / wrong-type / extra-field (does a
  strict parser reject-loudly or crash? does a lenient one silently
  mis-behave?).
- Boundary values: 0, negative, off-by-one at the exact limit the code
  doesn't exclude; falsy-zero treated as "missing" (`||` vs `??`).
- Adversarial content: shell/format metacharacters in a value that reaches a
  command, a template, a path, a regex, or a query. Names with spaces,
  quotes, `$(...)`, `;`, newlines. (The gate-router `{files}`→`bash -c` RCE
  and the composite-id colon split were exactly this axis.)
- Encoding: non-ASCII where ASCII is assumed; the CRLF/`\r` boundary.

### 3. Resource exhaustion
What is unbounded?
- Retry loops around a destructive/global op (one attempt, then diagnose — a
  `wsl --shutdown` retry loop is what wedged the host).
- Unbounded growth: a cache/map/list/log that never evicts; a per-request I/O
  or subprocess with no dedup/cap; a read of "the whole file" that scales with
  input.
- Timeouts and their absence: a blocking call with no deadline; a poll with no
  backoff; a wait that hangs instead of failing.

### 4. State drift
Does the change assume state that another actor can move underneath it?
- TOCTOU: a check outside the transaction that writes; two concurrent
  loops/processes/tabs sharing an actor/lease/worktree/file.
- Stale reads: a base that moved (origin/main advanced), a claim that
  expired/released, a config reloaded since, a session id resolved from a
  different process than the one that wrote the record.
- Cross-process seams (the highest-yield): who else constructs/calls this, in
  which process, with which env, on which stdin? MCP servers, hook
  subprocesses, spawned CLIs — the boundary where the last several PRs'
  worst bugs lived.

## Output

A ranked list, most-severe first, each with the concrete failing
scenario and axis. State plainly what is CONFIRMED vs PLAUSIBLE, and which
probes the existing tests already cover (so the gaps are unambiguous). No
fixes — the deliverable is the attack surface, verified.
