# Dispatch packet template — format v2

This is the canonical skeleton a generated dispatch packet fills in. The
format is versioned so packet telemetry (stall rate, review-finding rate)
can feed template revisions without breaking packets already in flight —
bump the version only when the section set or order changes, not for
wording tweaks. `v2` change: added `## Context reads` and `## Open
decisions (BLOCKING)` sections, a second (stop-and-report) anti-stall
line, and a `MODEL TIER` header field.

Fill every section. An empty `[operator]` section still gets a line saying
so explicitly ("nothing here needs live hosts/credentials") — omission
reads as an oversight, not a deliberate "none".

```markdown
# Dispatch packet: <task title>
WORKING DIRECTORY: <abs path>   BRANCH: <name> (checked out — do NOT switch/commit/push)
MODEL TIER: <sonnet|opus> — <one-line justification against the rubric in dispatch-discipline.md>
Begin editing within ~5 tool calls; the pointers below are sufficient.
If blocked for more than ~5 tool calls on open-ended reading, STOP and report the blocker — do not keep searching.

## Context reads (in order; playbook/spec first, then precedent PRs)
## Why (one incident or persona pain, one paragraph, with the source doc link)
## Open decisions (BLOCKING — none, or the packet is not dispatchable)
## Decided design (numbered; every decision CLOSED — an open one belongs above, never here)
## Wiring (mirror <merged PR #N>: list the exact N edits with file:line anchors)
## Boundaries (files you must NOT touch; who owns them; what happens if you do)
## Tests (file to create; the fixture/helper file to copy patterns from; the specific cases; "tests must fail against a broken implementation")
## Verify (exact commands in order; `git add -A` BEFORE any git-ls-files-based audit; paste tails in your report)
## [operator] (anything needing live hosts/credentials — produce commands, do not run)
## Report back (files changed, chokepoints chosen and why, verify tails, out-of-scope observations — report, don't fix)
```

## Section notes

- **Title line + WORKING DIRECTORY/BRANCH/MODEL TIER lines**: always
  first, always literal — an executor that doesn't know its own
  worktree, branch, and model tier in the first three lines wastes its
  first tool calls finding out.
- **MODEL TIER**: recorded in the packet so the orchestrator can check it
  against the rubric in `dispatch-discipline.md` — including the "never
  the orchestrator's own model" rule — at the moment of dispatch.
- **Anti-stall lines**: both are mandatory, verbatim — the ~5-tool-call
  start deadline, and the stop-and-report line. 2 of 7 freehand-dispatched
  agents stalled in open-ended reading; the second line is what stops it.
- **Context reads**: playbook/spec first, then precedent PRs, in the
  order the executor should read them — this is where a link dump used to
  hide inside `## Why`; keep it out of Why from now on.
- **Why**: one paragraph, no links — the links live in `## Context
  reads`. Not a spec restatement — the executor reads the linked docs for
  depth; this section just motivates the boundaries and decisions that
  follow.
- **Open decisions (BLOCKING)**: the only place an open question may
  live. Non-empty means the header carries `STATUS: BLOCKED — do not
  dispatch until the items below are answered`, and the packet returns to
  the requester, never an executor. Empty means literally `None — every
  decision in the source is closed.`
- **Decided design**: numbered so the executor (and the reviewer of the
  packet) can point at "decision 4" precisely. Every entry must already be
  CLOSED by the source material — an open one belongs in `## Open
  decisions` instead, never here. See `dispatch-discipline.md` for why
  this is non-negotiable.
- **Wiring**: the mirror-PR is the single highest success predictor
  observed; list edits as file:line, not prose descriptions of intent.
- **Boundaries**: always include the no-commit/no-push/no-branch line
  verbatim unless the packet explicitly delegates git ownership (rare —
  flag it if so).
- **Tests**: name the injectable-runner seam (fake `_run`, frozen clock,
  monkeypatched env) the repo already uses; point at the existing fixture
  file to copy, don't describe a new fixture shape from scratch.
- **Verify**: `git add -A` before any `git ls-files`-based audit is a hard
  ordering requirement — a stale index is invisible locally and fails in CI.
- **[operator]**: state explicitly even when empty.
- **Report back**: out-of-scope observations get reported, never silently
  fixed — that is a separate decision for whoever owns the packet.

## Which model gets this packet

| Tier | Give it | Never give it |
|---|---|---|
| sonnet | anchored mechanics, fixtures, migrations, "mirror this PR" builds | an unanchored "figure out where this goes" |
| opus | named design tensions, security/privacy perimeter judgments, adversarial review with attack lines | routine anchored execution |
| the orchestrator's own model | — | anything: a bounded executor must be independently reviewable |

Full rubric, and the reviewer-prompt requirements (REPRO per finding,
severity ranking, explicit SHIP / DO-NOT-SHIP, `SUSPECTED` for anything not
reproduced): `dispatch-discipline.md`.
