# Dispatch packet template — format v1

This is the canonical skeleton a generated dispatch packet fills in. The
format is versioned so packet telemetry (stall rate, review-finding rate)
can feed template revisions without breaking packets already in flight —
bump to `v2` only when the section set or order changes, not for wording
tweaks.

Fill every section. An empty `[operator]` section still gets a line saying
so explicitly ("nothing here needs live hosts/credentials") — omission
reads as an oversight, not a deliberate "none".

```markdown
# Dispatch packet: <task title>
WORKING DIRECTORY: <abs path>   BRANCH: <name> (checked out — do NOT switch/commit/push)
Begin editing within ~5 tool calls; the pointers below are sufficient.

## Why (one incident or persona pain, one paragraph, with the source doc link)
## Decided design (numbered; every decision CLOSED — if you find an open one, STOP and flag it back instead of choosing)
## Wiring (mirror <merged PR #N>: list the exact N edits with file:line anchors)
## Boundaries (files you must NOT touch; who owns them; what happens if you do)
## Tests (file to create; the fixture/helper file to copy patterns from; the specific cases; "tests must fail against a broken implementation")
## Verify (exact commands in order; `git add -A` BEFORE any git-ls-files-based audit; paste tails in your report)
## [operator] (anything needing live hosts/credentials — produce commands, do not run)
## Report back (files changed, chokepoints chosen and why, verify tails, out-of-scope observations — report, don't fix)
```

## Section notes

- **Title line + WORKING DIRECTORY/BRANCH line**: always first, always
  literal — an executor that doesn't know its own worktree and branch in the
  first two lines wastes its first tool calls finding out.
- **Why**: one paragraph, one link. Not a spec restatement — the executor
  reads the linked doc for depth; this section is just enough to motivate
  the boundaries and decisions that follow.
- **Decided design**: numbered so the executor (and the reviewer of the
  packet) can point at "decision 4" precisely. Every entry must already be
  CLOSED by the source material — see `dispatch-discipline.md` for why this
  is non-negotiable.
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
