# Fakoli Architecture View — Patterns We Already Practice

> **Status: research reference, not governance.** Hand-authored; not part of the
> principles ledger, not generated. It maps the external pattern vocabulary in
> [`agentic-patterns-glossary.md`](./agentic-patterns-glossary.md) onto the three Fakoli
> plugins and the governing principles in [`../fakoli-style.md`](../fakoli-style.md).

## Why this document exists

Fakoli was built from operating experience, not from a pattern catalogue. When that
experience is held up against an independent, well-articulated taxonomy of agentic
patterns, most of Fakoli's design choices turn out to have **names** — and, more
tellingly, most already have a corresponding **ledger principle**. This document records
that correspondence so the team can *recognize* the patterns it adopted intuitively, and
see precisely where an external lens surfaces something not yet governed.

The four operating invariants Fakoli is built on — **Intent over Recipe, Specialist over
Generalist, Evidence over Claim, Durability over Chat** — are the lens that decided which
patterns Fakoli adopted and which it declined. Read every mapping below through them.

---

## The three plugins in one line each

- **fakoli-state** — durable, event-sourced record of specs, tasks, claims, and evidence.
  *(Durability over Chat; Evidence over Claim.)*
- **fakoli-flow** — intent-driven orchestration pipeline (brainstorm → plan → execute →
  verify → finish) with critic gates. *(Intent over Recipe.)*
- **fakoli-crew** — roster of narrow specialist agents coordinated in waves.
  *(Specialist over Generalist.)*

---

## Pattern → embodiment → governing principle

| External pattern | Where Fakoli embodies it | Governing principle |
| --- | --- | --- |
| Coordinator / router | fakoli-flow `execute` dispatches crew agents by role at runtime | — (orchestration mechanic) |
| Hierarchical decomposition | brainstorm → plan → tasks → waves → agents | — |
| Parallel | wave engine runs all tasks *within* a wave concurrently | — |
| Sequential | the five flow stages; dependency-ordered waves | — |
| Review & critique | **critic gate after every code-writing wave** | embodies the spirit of **P1** (advisory/enforce parity); informs **P3** |
| Iterative refinement / Loop | critic→welder fix cycles; verify fix loops | **P13** (bounded refinement) |
| Human-in-the-loop | spec approval, scout-halt, BLOCKED/NEEDS_REVIEW, finish's 4 options | — (Intent over Recipe, human = governance) |
| Custom logic | `quick` fast-path; conflict-group routing | — |
| Single-agent / ReAct | each subagent internally; `quick` = one-agent dispatch | — |
| Swarm | **deliberately declined** (see below) | — |
| A2A — typed, schema'd handoffs | status files today; canonical Events as the target | **P7** (coordinate through canonical state, not status files) |
| Typed evidence / verifiable proof | evidence gate (substring today → typed target) | **P2** (verifiable proof beats pattern-matching) |
| Evaluation — output | critic (quality) + sentinel (acceptance scorecard) | embodies **P4** discipline |
| Evaluation — trajectory / failure | failed waves not yet first-class | **P6** (close the loop on failure) |
| Observability — durable record | event log + deterministic replay (state); ephemeral status files (flow) | **P10** + **P6** + **P7** combine toward this |
| State / context engineering | work-packet model: each agent gets only its intent + criteria + upstream decisions | — (Specialist over Generalist) |
| Least-privilege access | read-only tool allow-lists on critic/sentinel/state-keeper/docs-scribe | embodied in agent frontmatter; **not yet a stated principle** |
| Conflict detection | file-ownership matrix (file-level today → contract-level target) | **P8** (conflicts at the contract level) |
| State determinism boundary | derived/model data kept out of canonical state | **P11** (derived indexes outside the replay boundary) |
| Input/output inspection | **no inspection point today** | **P12** (untrusted content is data, not instruction) |
| Default-deny / tool scratch hygiene | `.fakoli/` run scratch gitignored | **P10** (tool scratch outside version control) |
| Credibility-risk sequencing | integrity-first roadmap (SL-1..SL-6) | **P5** (sequence by credibility risk) |
| Persona / responsibility separation | fakoli-style governs; state/flow/crew implement | the existence of this ledger |

---

## Patterns Fakoli adopted *and already governs*

These are the cases where the external taxonomy simply put a name on something the
ledger already tracks. No action needed; recorded for recognition.

- **Review & critique** as a standing, non-optional gate. The external material treats
  critique as one optional pattern; Fakoli makes it mandatory after every code wave.
  This is the same discipline **P1** enforces inside state (the preview a reviewer trusts
  *is* the check that enforces).
- **Typed A2A handoffs** → **P7**. The external A2A protocol's core idea — inter-agent
  messages are a typed, authenticated contract — is exactly the gap P7 already names:
  promote status-file coordination to canonical Events.
- **Typed evidence** → **P2**. Their "screen for the right content, not a substring" maps
  onto P2's "typed, verifiable evidence, never free-text that happens to contain the
  right substring."
- **Trajectory/failure evaluation** → **P6**. Their "evaluate the trajectory, not just the
  output" is P6's "record a failed wave as a first-class learnable event."
- **Contract-level conflict detection** → **P8**.
- **State-determinism boundary** → **P11**.
- **Credibility-risk sequencing** → **P5**.
- **Scratch hygiene / default-deny side effects** → **P10**.

That eight of the external taxonomy's load-bearing concepts already have ledger
principles is the headline finding: **Fakoli converged on the same forces independently.**

---

## A pattern Fakoli deliberately declined: Swarm

The taxonomy's **Swarm** (all-to-all peer agents, no central supervisor) is rated the most
complex and costly pattern, with a real risk of failing to converge. Fakoli declines it on
principle: crew agents never talk directly to each other. All coordination is mediated by
an orchestrator and a durable record. This is **Specialist over Generalist** plus the P7
target (coordinate through canonical state) — the opposite of a swarm. The decline is
correct and is worth keeping explicit so it is never "simplified" into peer chatter later.

---

## Where the external lens surfaced something not yet governed

Two items had **no corresponding ledger principle** when this review was done. Both relate
directly to what Fakoli is building, so both were added to the ledger (see
[`../fakoli-style.md`](../fakoli-style.md)):

- **P12 — Untrusted external content is data, never instruction.** Fakoli ingests
  untrusted text (scout's web fetches, user/external PRD and spec markdown) and acts on it
  with no inspection boundary. A poisoned input could be read as direction rather than
  data — which would directly undermine *Evidence over Claim*. Status: **aspirational**.
- **P13 — Bounded refinement with explicit escalation.** Every refinement loop in flow has
  a hard iteration cap and a defined escalation path (critic fix cycle ≤ 3, welder/verify
  fix ≤ 2, 5-minute poll timeout, no silently-swallowed escalations). This is a pattern
  Fakoli adopted intuitively to avoid the taxonomy's "infinite loop" failure mode — it was
  simply never *named* as a principle. Status: **asserted** (documented in the flow skills;
  not yet machine-enforced).

One more pattern is **embodied but unstated**: **least-privilege tool allow-lists** (the
read-only agents). It is genuinely practiced, so it is not a gap — but it is also not yet a
named principle. Left as a candidate; promote it the day a test asserts that read-only
agents carry no write tools (which would make it *proven*, P4-style), rather than adding it
as unverified prose now.

---

## How to keep this document honest

This file is **corroboration, not foundation.** If a future external taxonomy disagrees
with a Fakoli choice, the ledger principle and its proof win — not the external document.
Update this view when a principle changes status or a new plugin embodiment appears; never
let it drift into a second source of truth. The ledger remains the only governance record.
