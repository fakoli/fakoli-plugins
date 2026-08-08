# Why each packet line exists

Evidence base: one anvil-serving divergence session, two dispatch styles
head-to-head. Freehand subagent prompts: 2 of 7 stalled (open-ended reading
with no anchor to stop at). The same session's packet discipline (anchors,
mirror-PR, anti-stall clause, boundaries, verify list, `[operator]`
markers): 8 of 8 features shipped. The packet is a serialization format for
delegation — what has to be made explicit for a weaker executor to equal a
stronger one on bounded work.

- **Anti-stall clause** ← 2/7 agents stalled in open-ended reading with no
  signal to stop and report instead of continuing to search.
- **Anchors verified by grep, evidence embedded** ← an agent's test guessed
  an API signature from a stale anchor instead of the real one; the fix
  costs one grep at packet-generation time, not a failed test at review
  time.
- **CLOSED-decisions rule** ← delegated judgment is how specs go sideways.
  An executor choosing between two reasonable designs will pick one
  silently; the packet reviewer finds out only when the diff doesn't match
  intent. Any decision the source material leaves open gets flagged back to
  the requester, never resolved by the packet generator or the executor.
- **Mirror-PR reference** ← the single highest success predictor observed
  across dispatched packets. A concrete "here is the shape, here are the N
  edits it made" beats any amount of prose spec.
- **Boundaries (disjoint files / worktree isolation)** ← two parallel agents
  can share one worktree only if their file sets are disjoint; if they
  overlap at all, dispatch with `isolation: "worktree"` instead of hoping
  the diffs don't collide.
- **`git add -A` before ls-files-based audits** ← a stale git index passes
  every local check and fails only in CI, which is the most expensive place
  to discover it.

## Model-tier rubric

- **sonnet**: anchored mechanics, fixtures, migrations, "mirror this PR"
  builds — anything where the packet already supplies the shape and the
  anchors are grep-verified.
- **opus**: named design tensions, security/privacy perimeter judgments,
  adversarial review with attack lines — anything where the executor has to
  weigh competing valid approaches, not just execute a known shape.
- Neither tier gets an unanchored "figure out where this goes" packet — that
  is a sign the packet generator skipped step 3 (anchor verification) or
  step 2 (decision restatement), not a legitimate use of a stronger model to
  paper over an underspecified packet.
- Never dispatch to the orchestrator's own model — that defeats the purpose
  of using a bounded, independently-reviewable executor.

## Reviewer-prompt requirements

When a packet's job is itself a review (adversarial review, security
review, packet-of-a-review), the packet must demand from the reviewer:

- a **REPRO per finding** — a concrete input/state that triggers the
  problem, not a general concern;
- findings **ranked by severity**;
- an explicit **SHIP / DO-NOT-SHIP verdict**, not a bare list;
- any finding the reviewer could not reproduce labeled **`SUSPECTED`**
  rather than presented as confirmed.
