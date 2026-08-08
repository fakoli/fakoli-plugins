---
name: dispatch-packet
description: Generate a dispatch packet — a self-contained subagent packet / implementer prompt that lets a weaker executor equal a stronger one on bounded work. Use when asked to generate a subagent packet, dispatch an implementer, turn issue N into an agent prompt, or write a delegation prompt for a sonnet/opus executor from an issue or task description. Never auto-dispatches — a human/orchestrator reviews the generated packet before any agent runs it.
user-invocable: true
---

# Dispatch Packet

Turn an issue (`gh issue view N --json title,body,comments`) or a task
description into a dispatch packet: a delegation prompt with every decision
closed, every anchor grep-verified, and a mirror-PR to copy the shape of.
Freehand subagent prompts stalled 2/7 in practice; packets with this
discipline shipped 8/8. Template: `references/packet-template.md` (format
`v2`) · rationale + model-tier rubric: `references/dispatch-discipline.md`
· worked example: `references/example-packet-377.md`.

## 1. Read context first

Read the source issue/task, its linked playbook or design doc, and any
"mirror this PR" precedent before drafting anything. Playbook first, then
persona/spec docs, then the precedent PRs.

## 2. Restate the decided design — never resolve an open one

Enumerate the decisions the source already closed under `## Decided
design`, and record `MODEL TIER: <sonnet|opus>` per the rubric in
`dispatch-discipline.md`. An `OPEN-DECISION` or unresolved tension goes
under `## Open decisions (BLOCKING)` instead, never Decided design — that
marks the header `STATUS: BLOCKED` and returns the packet to the
requester, not an executor.

## 3. Anchor every file:line reference

For every anchor you plan to cite (`file.py:123`, a function name to grep),
run the grep yourself against the target repo/worktree and embed the
evidence line in the packet. A stale anchor sent an agent chasing an API
signature that had moved. If you cannot run the grep (wrong repo checked
out), say so in the packet rather than presenting a guess as fact.

## 4. Mirror a merged PR

Point at the closest merged PR that shipped the same shape of change and
list the exact edits it made, file:line — the single highest success
predictor observed.

## 5. Boundaries

List files/directories the executor must NOT touch and why (who owns them,
what breaks). State explicitly: no `git commit`, `git push`, `git checkout`,
or branch creation — the orchestrator owns git. Two agents may share one
worktree only if their file sets are disjoint; otherwise use
`isolation: "worktree"`.

## 6. Tests

Name the test file to create, the fixture/helper to copy patterns from
(injectable-runner pattern: fake the subprocess/`_run` seam, don't shell
out in tests), the specific cases, and require tests to fail against a
broken implementation.

## 7. Verify

Exact commands, in order. `git add -A` MUST run before any tooling that
reads `git ls-files` (a stale index passes locally, fails in CI). Require
verbatim command tails in the report, not a summary.

## 8. Anti-stall clause

Every packet header carries the two-line anti-stall block verbatim from
`packet-template.md` — start deadline plus stop-and-report. 2 of 7
freehand-dispatched agents stalled in open-ended reading.

## 9. `[operator]` markers

Anything needing live hosts, credentials, or SSH gets an `[operator]`
section — exact commands produced, not run. State it even when empty.

## 10. Report back

Require: files changed (path + line count), chokepoints chosen and why,
verify-command tails verbatim, and any out-of-scope observation — reported,
not silently fixed. **If the dispatched task is itself a review**, the
packet must additionally require a REPRO per finding, severity ranking, an
explicit SHIP / DO-NOT-SHIP verdict, and `SUSPECTED` on anything the
reviewer could not reproduce (`references/dispatch-discipline.md`).

## Refuse rather than guess

If the source material lacks decisions, emit the skeleton from
`packet-template.md` with the gaps under `## Open decisions (BLOCKING)`
and `STATUS: BLOCKED` in the header — return it to the requester, not an
executor. Do not fabricate a design; link oversized detail to reference
docs instead of inlining it, EXCEPT hardened/security code, always
inlined.

## No auto-dispatch

This skill only generates the packet — dispatching it is a separate,
human-reviewed step; reviewing the packet itself is the quality gate.
