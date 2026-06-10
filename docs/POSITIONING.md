# Fakoli vs. the Field: Prior Art and Positioning

*Last reviewed: June 2026. This is the honest version — what fakoli invented, what it
reinvented, and where the moat actually is. Update it when the landscape moves.*

## Why this document exists

The fakoli trinity (flow + crew + state) was built largely in parallel with — not in
response to — a wave of similar systems. Knowing exactly where we overlap and where we
differ keeps the roadmap honest: invest where we're differentiated, adopt where someone
else solved it better, and retire what the platform absorbs.

## The landscape

| System | What it is | Overlap with fakoli | What they have that we don't |
|---|---|---|---|
| [Beads](https://github.com/steveyegge/beads) (~24k stars) | Graph issue tracker DB for coding agents: ready-work detection, atomic claims, git-synced JSONL | Closest prior art to **fakoli-state**: local SQLite, ready queue, claims, GitHub sync | Git-backed JSONL as the *merge-friendly source of truth* (SQLite is a disposable cache); hash-based IDs that don't collide across branches; memory-decay compaction |
| [claude-task-master](https://github.com/eyaltoledano/claude-task-master) (~27k stars) | PRD → tasks with complexity scoring, MCP + CLI | fakoli-state's PRD pipeline is the same shape | Complexity score that *drives recursive expansion* (score > threshold → auto-breakdown), not just prioritization |
| [GitHub spec-kit](https://github.com/github/spec-kit) (~111k stars) | Spec-driven development: constitution → specify → clarify → plan → tasks → analyze → implement | fakoli-flow's pipeline is the same shape | The **constitution** (durable project principles every phase must honor) and `/analyze` (PRD↔tasks coverage check before implementation) |
| [obra/superpowers](https://github.com/obra/superpowers) (~220k stars) | Process-as-skills: brainstorm, worktree isolation, plans, per-task subagents, TDD, review | fakoli-flow's nearest competitor; validates the critic-gate idea | Two-stage review (spec compliance, then code quality — adopted into fakoli-crew v2.3); fresh subagent per task to dodge context rot |
| [Claude Flow / Ruflo](https://github.com/ruvnet/ruflo) | Swarm meta-harness: queens, 60+ agent types, consensus topologies | Cautionary tale, not prior art | Nothing to adopt. Its documented failure mode — orchestration state living only in a coordinator process — is exactly what fakoli-state exists to prevent |
| Anthropic native: Agent Teams + Dynamic Workflows | Shared task list with claiming + file locks + dependency blocking; self-orchestrating parallel subagents with adversarial verification | **Commoditizes most of fakoli-flow's dispatch mechanics** | Native, zero-install, maintained by the platform. But state is ephemeral (`~/.claude/tasks` is destroyed on cleanup) |
| CrewAI / LangGraph / AG2 | Python frameworks where you program the agents | Conceptual cousin of fakoli-crew's role model | Different lineage — they own the runtime; fakoli rides the harness. The market moved fakoli's way in 2025–26 |

## What fakoli got genuinely right (defend these)

1. **Evidence-backed completion as a database-enforced transition.** `submit_completion_evidence`
   → `needs_review` → human disposition, enforced by the state machine, not by prompt
   convention. The field's 2026 writing converged on "verifiers must inspect artifacts,
   never transcripts" — almost nobody else ships it as a hard gate. Beads, task-master,
   and spec-kit all lack it.
2. **Predictive file-conflict detection at claim time.** `check_conflicts` + conflict
   groups at planning time. Published practice still leans on worktree isolation and
   merge-time pain; checking *before* the work starts is ahead of the field.
3. **Lease-based claims with expiry and renewal.** Beads has a claim flag; Claude Code
   teams have file locks. Timed leases that recover work from crashed agents are rare
   outside Steve Yegge's Gas Town.
4. **The integrated triad.** Pipeline + crew + durable state designed together. Every
   competitor has at most two of the three.
5. **Event-sourced state with full replay.** JSONL log as source of truth, SQLite as a
   rebuildable projection. This is the architecture Claude Flow's own issue tracker
   wishes it had.

## What fakoli reinvented (be honest, don't over-claim)

- PRD → tasks parsing (task-master shipped it in early 2025)
- Local task graph + ready-work + GitHub sync (Beads)
- brainstorm → plan → execute with review gates and per-task subagents (superpowers)
- Wave-based parallel dispatch (now native via Agent Teams / Dynamic Workflows)
- 8 specialist archetypes (standard practice per Anthropic's own subagent guidance)

Reinvention isn't failure — several of these were parallel invention — but marketing
copy should not claim novelty for them.

## Strategic position (June 2026)

**The moat is fakoli-state, not fakoli-flow.** Anthropic's Agent Teams and Dynamic
Workflows now cover wave dispatch, task claiming, file locking, and dependency blocking
natively — and they will keep improving without us. What they don't have, and what is
structurally hard for a platform feature to have, is **durable, project-scoped,
evidence-bearing state that survives sessions** and belongs to the repo rather than to
`~/.claude`.

Implications:

- **fakoli-flow** should trend toward a *thin policy layer*: the intent-driven plan
  format, the critic-gate policy (now hook-enforced as of v1.2), and the evidence rules
  — while delegating raw dispatch mechanics to native orchestration as it matures.
- **fakoli-crew** stays valuable as the opinion layer (role discipline, tool
  allowlists, language style references) — cheap to maintain, portable via the Agent
  Skills standard.
- **fakoli-state** is where engineering investment compounds. Roadmap candidates, in
  the order the field suggests: git-committed JSONL for Beads-style multi-machine sync;
  complexity-score → auto-expansion; a constitution/coverage gate before planning;
  adversarial second-verifier passes.

## Retired ideas (rejected with evidence)

| Date | Idea | Why it died |
|---|---|---|
| 2026-06-10 | Unify fakoli-state's CLI + MCP into one dispatch layer | Reconnaissance showed both surfaces are already thin wrappers over the shared managers (ClaimManager et al., 70–100% reuse per operation). A unified layer would add ~200 lines of indirection to save ~50 lines of boilerplate. Investment goes to the shared managers instead. Recorded in the git-backed-events spec's decision log |

## Adopted from the field (changelog of stolen ideas)

| Date | Idea | Source | Where it landed |
|---|---|---|---|
| 2026-06 | Two-stage review: spec compliance before code quality | superpowers | fakoli-crew critic, fakoli-flow critic-gate prompt |
| 2026-06 | Hook-enforced (not prompt-enforced) review gates | Anthropic Agent Teams' blocking hooks | fakoli-flow gate-check/gate-track hooks |
| 2026-06 | Machine-readable verifier verdicts | — (enabler for automation) | fakoli-crew sentinel, fakoli-flow execute/verify |
| 2026-06 | Adversarial refutation pass (second verifier tries to break PASS verdicts) | Anthropic Dynamic Workflows | fakoli-flow verify Step 5.5 |
| 2026-06 | Complexity score drives recursive task expansion | claude-task-master | fakoli-state scoring/plan flow |
| 2026-06 | Security auditor as a standing review role | unanimous across field rosters + 3 first-party Anthropic surfaces | fakoli-crew warden (ninth agent) |
