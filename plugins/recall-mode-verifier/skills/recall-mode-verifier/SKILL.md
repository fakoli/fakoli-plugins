---
name: recall-mode-verifier
description: Review a change for concrete failure modes in malformed inputs, required preconditions, resource use, and concurrent state. Use for an independent breakage review or when asked what could break. Reports findings and evidence; fixes follow the user’s requested scope.
---

# Recall-Mode Verifier

**Recall mode** = verify from an independent model of what *must not* break,
Build the initial probe list from the purpose and callers before consulting
the change’s tests. Then use the contract and existing tests to distinguish
a defect from intended behavior. This workflow works without another plugin.

## How to run it

1. Establish the review scope from the user's request and the working tree.
   For a PR, resolve its actual base and head; for local work include staged,
   unstaged, and relevant untracked files. Record the refs or paths reviewed.
   Do not assume a branch called `main`, silently fetch or switch branches,
   or omit local edits because a three-dot comparison is empty.
2. Read changed code and its callers. Build candidate probes from invariants
   and boundaries before consulting the new tests. Then compare with the
   documented contract and existing coverage; optional data failures may
   correctly degrade while required authorization preconditions must hold.
3. Execute safe probes in temporary fixtures when they add confidence.
   Keep destructive operations, external writes, secrets, and real user state
   outside probes. A mock failing dependency is usually enough.
4. Label **REPRODUCED** only when a probe actually ran and observed the failure;
   **SUPPORTED BY CODE** for a complete reachable path shown in source; and
   **PLAUSIBLE** for a risk with a specific unverified assumption. Cite the
   failing input, observed or predicted result, file/line, and relevant guard.
   Refuted probes are coverage context, not defects. Rank by practical impact.
5. In review-only scope, report findings without editing production code. If
   the user already requested fixes, implement supported fixes after reviewing
   and rerun the relevant probes; do not add another permission round.

## The four axes (spec-independent)

### 1. Fail-closed
When the state needed to make a safety decision can't be read, does the change
**refuse**, or proceed-with-warning / fail-open?
- For required preconditions, make the relevant external read fail (missing file, empty output, non-zero
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

Report actionable findings by severity, with evidence labels, concrete inputs,
and paths. State what was tested, what was only inspected, and remaining gaps.
If no supported defect is found, say so without inventing findings to fill the
four axes. Avoid claiming the change is safe merely because a sample passed.
