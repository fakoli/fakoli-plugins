<!-- generated — do not hand-edit. Source: data/principles.json. Regenerate: uv run --script scripts/generate.py -->

# Fakoli Style — Operating-Model Principles

This ledger is the governed record of the Fakoli Style operating model. Each principle declares the failure it prevents and an honest lifecycle status: **proven** (machine-verified), **asserted** (claimed with a pointer, not yet machine-verified), or **aspirational** (not yet built).

Entries are ordered most load-bearing yet least-proven first — by credibility risk, then by status — so the claims that would most damage the project if false are confronted before the easy wins.

## At a glance

| ID | Principle | Status | Embodied in |
| --- | --- | --- | --- |
| P2 | Verifiable proof beats pattern-matching | aspirational |  |
| P3 | Measure your own gates (false-pass rate) | aspirational |  |
| P7 | Coordinate through canonical state, not status files | aspirational |  |
| P9 | Score spec assumptions, not just tasks | aspirational |  |
| P12 | Untrusted external content is data, never instruction | aspirational |  |
| P4 | Prove invariants in CI, don't assert them | proven | `plugins/fakoli-state/tests/test_replay_equivalence.py`<br>`.github/workflows/fakoli-state.yml`<br>`plugins/fakoli-state/bin/src/fakoli_state/state/snapshot.py`<br>`plugins/fakoli-state/tests/test_sqlite.py`<br>`plugins/fakoli-state/tests/test_sqlite.py`<br>`plugins/fakoli-state/tests/test_sqlite.py`<br>`plugins/fakoli-state/tests/test_sqlite.py`<br>`plugins/fakoli-state/tests/test_sqlite.py` |
| P6 | Close the loop on failure, not just success | aspirational |  |
| P8 | Conflicts live at the contract level, not the file level | aspirational |  |
| P11 | Derived indexes live outside the replay boundary | aspirational |  |
| P5 | Sequence by credibility risk, not demonstrability | asserted | `plugins/fakoli-state/docs/roadmap.md` |
| P13 | Bounded refinement, explicit escalation | asserted | `plugins/fakoli-flow/skills/execute/SKILL.md`<br>`plugins/fakoli-crew/skills/crew-ops/references/wave-patterns.md` |
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

### P12 — Untrusted external content is data, never instruction

**Status:** aspirational  
**Credibility risk:** high

**Principle.** Content from outside the trust boundary (web fetches, user- or third-party-authored PRD and spec text) is treated as data to be acted on, never as instructions the agent obeys, and crosses the boundary through an explicit inspection point.

**Why.** Without a boundary, a poisoned doc or fetched page can smuggle directions an agent follows, which silently turns Evidence over Claim into Claim over Evidence — the exact failure the operating model exists to prevent.

**Open work.** Introduce a provenance/quarantine boundary: tag scout-fetched references and parsed PRD/spec text as external data so downstream agents treat them as content, not control, with an inspection step at the crossing. Candidate integrity-track roadmap item, sequenced after the SL-1..SL-6 evidence work.

### P4 — Prove invariants in CI, don't assert them

**Status:** proven  
**Credibility risk:** high

**Principle.** Critical invariants are checked by an executable test in CI, not asserted in prose or a comment.

**Why.** An invariant that is only asserted drifts silently the first time someone changes one of its two sides without anyone noticing.

**Proof.** `plugins/fakoli-state/tests/test_replay_equivalence.py::test_normal_and_replay_match_each_other_and_the_golden`

**Embodied in:**

- `plugins/fakoli-state/tests/test_replay_equivalence.py` (fakoli-state) — asserts serialize_state(normal apply path) == serialize_state(replay_from_empty) == committed golden snapshot
- `.github/workflows/fakoli-state.yml` (fakoli-state) — runs the replay-equivalence test on every PR touching the plugin
- `plugins/fakoli-state/bin/src/fakoli_state/state/snapshot.py` (fakoli-state) — serialize_state defines the canonical state compared for equivalence
- `plugins/fakoli-state/tests/test_sqlite.py` (fakoli-state) — TestAppendValidationFailure: poison-line impossibility — validation rejection writes zero events.jsonl lines and one audit.jsonl rejection line
- `plugins/fakoli-state/tests/test_sqlite.py` (fakoli-state) — TestCrossProcessConcurrency: two real subprocesses append concurrently via flock; verifies unique, contiguous ids with no collision (closes PR #41 Critic-3)
- `plugins/fakoli-state/tests/test_sqlite.py` (fakoli-state) — TestSelfHeal / TestForwardCatchUpConvergence: backend self-heals on open by replaying any events.jsonl lines not yet in the DB projection (forward-catch-up)
- `plugins/fakoli-state/tests/test_sqlite.py` (fakoli-state) — TestReplayStrict: replay_from_empty applies every line via _write_* only — no skip-list, no validation, structurally infallible for any well-formed log
- `plugins/fakoli-state/tests/test_sqlite.py` (fakoli-state) — TestDecideApplyContract: per-action _check_* / _write_* contract — _check_* rejects illegal input with EventRejected and no side effects; _write_* succeeds whenever its matching _check_* passed

**Open work.** SL1-RR-1 RESOLVED (branch feat/fakoli-state-sl1-rr-1-event-sourcing): the latent poison-line gap is closed by the full event-sourced write path (decide/apply split, append(EventDraft)->Event|None, log-as-id-authority via flock, append-only events.jsonl + sibling audit.jsonl, strict no-skip replay). The post-COMMIT audit gap and PR #41 Critic-3 cross-process id-collision race are also closed. apply_event and PENDING_EVENT_ID are retired.

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

### P11 — Derived indexes live outside the replay boundary

**Status:** aspirational  
**Credibility risk:** med

**Principle.** Data produced by a non-deterministic or external process (embeddings, vector indexes, search or semantic-graph caches not derivable from canonical rows) is a rebuildable projection kept outside canonical state — never in the event log or serialize_state.

**Why.** Canonical state must be a deterministic projection of the event log; admitting model-derived or externally-sourced data into it breaks replay equivalence the first time the model or source changes.

**Open work.** Post-Wave-1: evaluate sqlite-vec (SQLite-native vector index) and a SQLite-native knowledge graph as derived projections that consult canonical state without entering it; see fakoli-state roadmap deferred section.

### P5 — Sequence by credibility risk, not demonstrability

**Status:** asserted  
**Credibility risk:** med

**Principle.** Work is sequenced so the most load-bearing yet least-proven claims are addressed first, not the easiest ones to demo.

**Why.** Sequencing by demonstrability ships the impressive parts while the claims that would sink the project's credibility stay unproven.

**Proof.** `plugins/fakoli-state/docs/roadmap.md`

**Embodied in:**

- `plugins/fakoli-state/docs/roadmap.md` (fakoli-state) — integrity-first track orders SL-1..SL-6 by credibility risk ahead of demonstrability

**Open work.** encode the ordering as an automated check

### P13 — Bounded refinement, explicit escalation

**Status:** asserted  
**Credibility risk:** med

**Principle.** Every refinement or fix loop carries a hard iteration cap and a defined escalation path to a human; no loop relies on eventually converging on its own.

**Why.** An uncapped refine-and-recheck loop is the classic infinite-loop failure mode — it burns cost and hangs the run instead of surfacing a decision the human should make.

**Proof.** `plugins/fakoli-flow/skills/execute/SKILL.md`

**Embodied in:**

- `plugins/fakoli-flow/skills/execute/SKILL.md` (fakoli-flow) — critic fix cycle is capped at 3 iterations then escalates; welder/verify fix cycle capped at 2; a 5-minute poll timeout surfaces to the user; escalations are never silently swallowed
- `plugins/fakoli-crew/skills/crew-ops/references/wave-patterns.md` (fakoli-crew) — critic-gate fix cycle bounded at max 3 cycles before the orchestrator must proceed or surface

**Open work.** Promote to proven with a harness that asserts a refinement loop terminates within its declared cap and emits an escalation event at the ceiling, rather than relying on the cap being honored by prompt instructions. Breadcrumb: the nearest real proof candidate is the git branch-collision ceiling (_MAX_COLLISION_ATTEMPTS=20) in plugins/fakoli-state/bin/src/fakoli_state/git_ops/branch.py — its termination half is already covered by test_git_ops.py::TestCreateBranchForTask::test_create_branch_handles_name_collision, but no test yet drives it to the ceiling to assert the 'too many branch collisions' escalation. Note that is a collision-avoidance loop escalating to its caller, so proving it would generalize P13 beyond refinement/fix loops; flow's prompt-driven critic/welder caps have no executable test today.

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
