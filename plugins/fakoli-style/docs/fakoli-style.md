<!-- generated — do not hand-edit. Source: data/principles.json. Regenerate: uv run --script scripts/generate.py -->

# Fakoli Style — Operating-Model Principles

This ledger is the governed record of the Fakoli Style operating model. Each principle declares the failure it prevents and an honest lifecycle status: **proven** (machine-verified), **asserted** (claimed with a pointer, not yet machine-verified), or **aspirational** (not yet built).

Entries are ordered most load-bearing yet least-proven first — by credibility risk, then by status — so the claims that would most damage the project if false are confronted before the easy wins.

## At a glance

| ID | Principle | Status | Embodied in |
| --- | --- | --- | --- |
| P2 | Verifiable proof beats pattern-matching | aspirational |  |
| P3 | Measure your own gates (false-pass rate) | aspirational |  |
| P4 | Prove invariants in CI, don't assert them | aspirational |  |
| P7 | Coordinate through canonical state, not status files | aspirational |  |
| P9 | Score spec assumptions, not just tasks | aspirational |  |
| P6 | Close the loop on failure, not just success | aspirational |  |
| P8 | Conflicts live at the contract level, not the file level | aspirational |  |
| P5 | Sequence by credibility risk, not demonstrability | asserted | `plugins/fakoli-state/docs/roadmap.md` |
| P1 | Advisory and enforcing share one code path | proven | `plugins/fakoli-state/bin/src/fakoli_state/state/transitions.py` |
| P10 | Tool scratch lives outside version control | proven | `.gitignore`<br>`plugins/fakoli-flow/references/status-protocol.md` |

## Principles

### P2 — Verifiable proof beats pattern-matching

**Status:** aspirational  
**Credibility risk:** high

**Principle.** Gates accept typed, verifiable evidence, never free-text that happens to contain the right substring.

**Why.** A substring gate is trivially satisfiable by writing the required string into any field, so it passes work that was never done.

**Open work.** SL-3 (typed ProofArtifact evidence replacing the substring gate)

### P3 — Measure your own gates (false-pass rate)

**Status:** aspirational  
**Credibility risk:** high

**Principle.** A gate is only trusted once its false-pass rate is measured against injected faults and the baseline is committed.

**Why.** An unmeasured gate can wave through broken work indefinitely because nobody knows how often it lets failures pass.

**Open work.** SL-2 (fault-injection harness + committed baseline)

### P4 — Prove invariants in CI, don't assert them

**Status:** aspirational  
**Credibility risk:** high

**Principle.** Critical invariants are checked by an executable test in CI, not asserted in prose or a comment.

**Why.** An invariant that is only asserted drifts silently the first time someone changes one of its two sides without anyone noticing.

**Open work.** SL-1 (replay equivalence check in CI)

### P7 — Coordinate through canonical state, not status files

**Status:** aspirational  
**Credibility risk:** high

**Principle.** Agents coordinate by reading and writing canonical Events, not by parsing each other's free-form status files.

**Why.** Status files have no schema and no ordering guarantees, so coordination built on them races and silently disagrees.

**Open work.** SL-4 (promote status-file coordination to canonical Events)

### P9 — Score spec assumptions, not just tasks

**Status:** aspirational  
**Credibility risk:** high

**Principle.** Risk scoring ranks the spec's assumptions by blast radius and uncertainty, not just its enumerated tasks.

**Why.** Scoring only tasks leaves the most dangerous wrong assumptions unranked, so the plan optimizes effort while ignoring the real risk.

**Open work.** SL-6 (score assumptions by blast_radius x uncertainty)

### P6 — Close the loop on failure, not just success

**Status:** aspirational  
**Credibility risk:** med

**Principle.** A failed wave is recorded as a first-class learnable event, the same way a successful one is.

**Why.** If only successes are captured, every failure is forgotten and the system relearns the same mistake on the next run.

**Open work.** make a failed wave a first-class learnable event (substrate: events.jsonl)

### P8 — Conflicts live at the contract level, not the file level

**Status:** aspirational  
**Credibility risk:** med

**Principle.** Conflicts between agents are detected against declared output contracts and a post-apply drift check, not against raw file overlap.

**Why.** File-level conflict detection both misses semantic clashes in non-overlapping files and flags harmless coincidental edits as conflicts.

**Open work.** SL-5 (OutputContract + post-apply drift check)

### P5 — Sequence by credibility risk, not demonstrability

**Status:** asserted  
**Credibility risk:** med

**Principle.** Work is sequenced so the most load-bearing yet least-proven claims are addressed first, not the easiest ones to demo.

**Why.** Sequencing by demonstrability ships the impressive parts while the claims that would sink the project's credibility stay unproven.

**Proof.** `plugins/fakoli-state/docs/roadmap.md`

**Embodied in:**

- `plugins/fakoli-state/docs/roadmap.md` (fakoli-state) — integrity-first track orders SL-1..SL-6 by credibility risk ahead of demonstrability

**Open work.** encode the ordering as an automated check

### P1 — Advisory and enforcing share one code path

**Status:** proven  
**Credibility risk:** med

**Principle.** The advisory preview and the enforcing transition call the exact same gate predicate, never two parallel implementations.

**Why.** Two implementations of the same gate drift apart, so the preview a reviewer trusts stops matching the check that actually enforces.

**Proof.** `plugins/fakoli-state/tests/test_transitions.py::TestEvidenceGateDelegation::test_transition_gate_agrees_with_review_gate`

**Embodied in:**

- `plugins/fakoli-state/bin/src/fakoli_state/state/transitions.py` (fakoli-state) — transitions._evidence_complete delegates to review.gates.evidence_complete (single source of truth)

**Open work.** extend the agreement-test pattern to fakoli-flow's preview/enforce paths

### P10 — Tool scratch lives outside version control

**Status:** proven  
**Credibility risk:** med

**Principle.** Run-local process artifacts are gitignored; only intent (specs and plans) is committed.

**Why.** Committing scratch clutters history and PR diffs with mechanics that have no value after the run.

**Proof.** `tests/test-scratch-not-tracked.sh`

**Embodied in:**

- `.gitignore` (repo) — gitignores .fakoli/ so run scratch cannot be committed
- `plugins/fakoli-flow/references/status-protocol.md` (fakoli-flow) — status files write to .fakoli/runs/<run-id>/, not docs/plans/

**Open work.** Status scratch is now proven untracked under both .fakoli/ and docs/plans/. Extend the check to non-status scratch (server PID/logs, screenshots) if those ever risk being committed.
