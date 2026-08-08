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
`v1`) · rationale + model-tier rubric: `references/dispatch-discipline.md`
· worked example: `references/example-packet-377.md`.

## 1. Read context first

Read the source issue/task, its linked playbook or design doc, and any
"mirror this PR" precedent before drafting anything. Playbook first, then
persona/spec docs, then the precedent PRs.

## 2. Restate the decided design — never resolve an open one

Enumerate the decisions the source already closed. If you hit an
`OPEN-DECISION`, an unresolved question, or a design tension the source
doesn't settle, **stop and flag it back to the requester** — do not choose
for them. This is the single highest-leverage rule: delegated judgment is
how specs go sideways.

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

State it explicitly in every packet: if blocked for more than ~5 tool calls
on open-ended reading, stop and report the blocker rather than continuing to
search. 2 of 7 freehand-dispatched agents stalled this way.

## 9. `[operator]` markers

Anything needing live hosts, credentials, or SSH gets an `[operator]`
section: the executor produces the exact command but does not run it. A
packet with nothing operator-shaped says so rather than omitting it.

## 10. Report back

Require: files changed (path + line count), chokepoints chosen and why,
verify-command tails verbatim, and any out-of-scope observation — reported,
not silently fixed. **If the dispatched task is itself a review**, the
packet must additionally require a REPRO per finding, severity ranking, an
explicit SHIP / DO-NOT-SHIP verdict, and `SUSPECTED` on anything the
reviewer could not reproduce (`references/dispatch-discipline.md`).

## Refuse rather than guess

If the source material lacks decisions, emit the packet skeleton from
`packet-template.md` with `OPEN-DECISION` markers in place and STOP — do not
fabricate a design. If a packet would be oversized, link to reference docs
instead of inlining them, EXCEPT hardened/security code, which is always
inlined — executors must not go spelunking for it.

## No auto-dispatch

This skill only generates the packet. Dispatching it to an agent is a
separate, human-reviewed step — the review of the packet itself is the
quality gate, not a downstream review of what the agent did with it.
