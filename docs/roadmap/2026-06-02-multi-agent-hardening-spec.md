# Fakoli Multi-Agent System — Hardening Spec

**Status:** Draft for review
**Date:** 2026-06-02
**Author:** Generated analysis (autonomous run) — review before merge
**Scope:** fakoli-crew v2.5, fakoli-flow v1.1.1, fakoli-state v1.20
**Analyzed at:** `b69cd38` (== `origin/main`)

---

## 1. Context & goal

The Fakoli multi-agent system is three cooperating plugins:

- **fakoli-crew** — 8 specialized subagents (guido, critic, scout, smith, welder, herald,
  keeper, sentinel) + the `crew-ops` orchestration skill.
- **fakoli-flow** — a phase pipeline (`brainstorm → plan → execute → verify → finish`, plus
  `quick`) that dispatches crew agents in dependency-ordered waves with standing critic gates.
- **fakoli-state** — a Python, event-sourced SQLite state engine (PRD → tasks → claim →
  evidence → review) exposed to agents over an MCP server.

The system is production-proven, but risk concentrates at the **seams between layers**. This
spec captures a prioritized hardening roadmap derived from a full read of `main`, with each
item independently actionable: problem, evidence, proposed change, risk, and acceptance test.

### Non-goals
- No public API redesign of the state engine.
- No rewrite of the wave engine.
- No change to the human-in-the-loop review model.

---

## 2. The strategic finding (frames everything below)

**The pipeline and the state engine do not integrate.** `fakoli-flow` tracks live work in
*ephemeral, gitignored* `.fakoli/runs/<run-id>/` status files, while `fakoli-state` is a
*durable, event-sourced, replayable* task store — and neither invokes the other. The flow
skills never call `claim_task` / `submit_completion_evidence`, never touch `.fakoli-state/`.

Result: a rigorous, audit-grade state engine sits *beside* the orchestrator instead of
*under* it. Two parallel notions of "what work is happening" that can disagree, with the
durable one unused during actual runs.

**Recommendation (S1):** make `fakoli-flow:execute` optionally drive `fakoli-state` when a
`.fakoli-state/` project is present — claim a task before dispatching its wave, submit
evidence (the sentinel scorecard) on completion. This unifies the two state mechanisms and
gives the pipeline crash-recovery + an audit trail for free. Designed in §6; not implemented
in this pass (too large for an unattended run) — staged as the headline follow-up.

---

## 3. Priority model

- **P0** — correctness / silent work loss. Fix first.
- **P1** — robustness; failure modes that need an unlucky timing or input.
- **P2** — maintainability/consistency; raises the floor, prevents future drift.
- **S** — strategic; large, design-led.

---

## 4. P0 — correctness / silent work loss

### P0-1 · flow: run-ID collision (silent status overwrite)
- **Problem:** run-id is derived as `<basename>-YYYYMMDDHHmm` independently in 3 skills.
  Two phases (or two projects) in the same wall-clock minute resolve to the **same** id and
  therefore the **same** `.fakoli/runs/<run-id>/` directory; agent status files
  (`agent-<role>-status.md`) silently overwrite each other.
- **Evidence:** `fakoli-flow/skills/execute/SKILL.md` (run-id derivation),
  `…/plan/SKILL.md`, `…/verify/SKILL.md`; minute-granularity timestamp.
- **Change:** (a) add seconds **and** a short collision-resistant suffix (PID or 4-hex nonce)
  to the run-id; (b) extract the derivation into one shared reference
  (`references/run-id.md`) that all three skills cite, removing the 3 independent copies.
- **Risk:** Low — instruction/markdown change; no code path.
- **Acceptance:** the three skills no longer specify minute-only ids; a single canonical
  derivation doc exists and is referenced; the format includes sub-minute + nonce entropy.

### P0-2 · state: schema migration has no rollback on partial failure
- **Problem:** the v2→v3 migration applies several `ALTER TABLE` / `CREATE INDEX` statements,
  each wrapped in a try/except that only swallows the *"duplicate column"* idempotence case.
  Any *other* error (e.g. disk I/O) re-raises **mid-migration**, leaving a partially-upgraded
  schema. Blast radius is the whole DB.
- **Evidence:** `fakoli-state/bin/src/fakoli_state/state/sqlite.py` (schema-version check /
  migration block, ~`:922-952`).
- **Change:** wrap the whole migration body in a single transaction
  (`BEGIN … COMMIT`/`ROLLBACK`), and only stamp `user_version = 3` after all statements
  succeed. Keep the duplicate-column idempotence guard inside the transaction.
- **Risk:** Medium — touches startup/migration; guarded by `test_sqlite`, `test_snapshot`,
  `test_replay_equivalence`.
- **Acceptance:** existing migration tests stay green; a new test simulating a mid-migration
  failure asserts the schema version is **not** advanced and no partial columns persist.

### P0-3 · state: claim-ID reissue can silently misroute
- **Problem:** the `claims` table is `PRIMARY KEY(id)` only. On a reissued `claim.id` bound to
  a *different* `task_id`, `INSERT OR IGNORE` drops the row and the paired task `UPDATE` (guarded
  `WHERE status='ready'`) matches 0 rows — silently. The validation gate defends the common
  case, but the storage layer has no structural guarantee.
- **Evidence:** `sqlite.py` claim insert path (~`:2305-2384`); schema `PRIMARY KEY (id)`.
- **Change:** add a structural guard — `UNIQUE(id, task_id)` (or an explicit pre-insert check
  that rejects an id reuse across task_ids) — via a v3→v4 migration; preserve replay.
- **Risk:** Higher — schema migration + must keep event replay byte-identical.
- **Acceptance:** `test_replay_equivalence` + `test_snapshot` stay green; new test asserts a
  reissued id against a new task_id is rejected at the storage layer, not silently dropped.

### P0-4 · state: unbounded torn-line tolerance (open MUST-FIX)
- **Problem:** `_scan_tail_id` tolerates a torn trailing line by doubling a read window until a
  newline is found, with **no hard cap**. A pathological/large trailing payload can drive the
  scan toward O(file size) memory. Flagged in-code as an SL1-RR-1 critic MUST-FIX.
- **Evidence:** `sqlite.py` `_scan_tail_id` (~`:1013-1073`), in-code "MUST FIX" comment.
- **Change:** cap the backward window at a sane maximum (e.g. 1 MiB); on exceeding it, fail
  loudly with a clear "log tail appears corrupt beyond N bytes" error rather than growing
  unbounded.
- **Risk:** Low/Medium — localized; covered by replay/tail tests.
- **Acceptance:** new test feeds an oversized torn tail and asserts a bounded, explicit error
  (not OOM / not unbounded growth); existing tail/replay tests stay green.

---

## 5. P1 — robustness

### P1-5 · flow: verify and finish are disconnected
- **Problem:** `verify` writes the sentinel pass/fail scorecard into gitignored
  `.fakoli/runs/<verify-run-id>/`; `finish` never reads it and blindly re-runs tests. Two
  independent evidence gates with no coupling — wasted work and possible disagreement.
- **Evidence:** `verify/SKILL.md` (scorecard path), `finish/SKILL.md` (independent re-run).
- **Change:** have `finish` look for the most recent verify scorecard for the branch/plan and
  (a) surface it, (b) treat a fresh PASS as satisfying the pre-merge gate, re-running only when
  the scorecard is stale/absent.
- **Risk:** Low — instruction change.
- **Acceptance:** `finish` documents reading the verify scorecard and the staleness rule.

### P1-6 · flow: no timeout on BLOCKED / NEEDS_REVIEW
- **Problem:** only the `IN_PROGRESS` agent state has a (5-minute) timeout. A wave waiting on a
  `BLOCKED` or `NEEDS_REVIEW` escalation can hang indefinitely with no wall-clock deadline.
- **Evidence:** `execute/SKILL.md` polling section (single IN_PROGRESS timeout).
- **Change:** define a wall-clock deadline for terminal-waiting states and an explicit
  surfaced action ("escalate to user after N minutes / mark wave stalled").
- **Risk:** Low — instruction change.
- **Acceptance:** `execute` specifies deadlines for BLOCKED/NEEDS_REVIEW, not just IN_PROGRESS.

### P1-7 · flow: no plan pre-flight validation
- **Problem:** `execute` assumes a well-formed plan. Circular dependencies, missing
  `Verify`/`Agent` fields, and invalid agent names flow straight into dispatch.
- **Evidence:** `execute/SKILL.md` wave-assignment section (no cycle/field checks).
- **Change:** add a pre-flight validation step: required fields present, agent names valid,
  dependency graph acyclic; abort with a clear report on violation.
- **Risk:** Low — instruction change.
- **Acceptance:** `execute` documents a validation gate run before wave 1.

### P1-8 · state: evidence file-scope unverified
- **Problem:** on `evidence.submitted`, `files_changed` is not checked against the claim's
  `expected_files`. An agent can edit out-of-scope files; conflict detection silently weakens.
- **Evidence:** `claims/manager.py` (~`:193-345`), `transitions.py` evidence gate.
- **Change:** add a warning-or-reject policy comparing `files_changed ⊆ expected_files`
  (configurable strictness; default warn).
- **Risk:** Medium — touches the evidence path; covered by `test_claims`, `test_transitions`.
- **Acceptance:** new test asserts an out-of-scope file is detected per policy; existing
  evidence tests stay green.

### P1-9 · state: audit-write errors silently suppressed
- **Problem:** a failed `audit.jsonl` append only logs and proceeds; the caller never learns
  the audit trail is now incomplete.
- **Evidence:** `sqlite.py` audit append (~`:1244-1257`), try/except OSError → logger only.
- **Change:** surface audit-write failures through a defined channel (raise a typed warning or
  set a `degraded_audit` flag the caller can observe), rather than swallowing.
- **Risk:** Low/Medium — covered by audit-related tests.
- **Acceptance:** new test asserts a simulated audit-write failure is observable to the caller.

---

## 6. P2 — maintainability & consistency

### P2-10 · flow: kill duplicated detection logic (establish SSOT)
- Language detection is copy-pasted **4×** (`hooks/detect-context.sh`, `plan`, `verify`,
  `finish`); run-id derivation **3×**; critic-gate logic **2×**. One bug = many edits.
- **Change:** one canonical reference each (run-id covered by P0-1); skills cite, not copy.

### P2-11 · system: one canonical status-file protocol doc
- Status-file format is defined in **3 places** (crew `crew-ops/references/communication.md`,
  flow `references/status-protocol.md`, crew `wave-patterns.md`) with no sync check.
- **Change:** designate flow `status-protocol.md` canonical; others link to it.

### P2-12 · crew: agent-prompt gaps
- `critic.md` and `welder.md` never instruct the agent to write its status file (every other
  agent does) → downstream context loss.
- `critic` has no `Bash` (reviews on opinion, can't run `tsc`/linters); `herald` has no
  `Grep`/`Bash` (can't link-check a README it rewrites).
- Codex `.toml` companions are all undifferentiated `gpt-5.5` (no per-role tier).
- **Change:** add status-file instructions to critic.md + welder.md (this pass); evaluate tool
  allowlist widening and Codex tiering (follow-up).

### P2-13 · ecosystem: version compatibility
- No min-version declared across crew/flow/state; flow detects crew version via a fragile cache
  glob (`~/.claude/plugins/cache/.../fakoli-crew/*/plugin.json`).
- **Change:** publish a compatibility matrix; replace the cache glob with `claude plugin list`
  parsing.

### P2-14 · tests
- crew: **no agent-frontmatter validator** (a malformed agent merges clean).
- flow: **no skill-handoff/integration tests**.
- state: missing **concurrency / corruption / migration** edge-case tests (this spec adds a few).

---

## 7. S — strategic

### S1 · flow ↔ state integration (headline follow-up)
When a `.fakoli-state/` project exists, `fakoli-flow:execute` should:
1. `claim_task` for each task before dispatching its wave (lease + conflict check).
2. On wave completion, `submit_progress` / `submit_completion_evidence` with the sentinel
   scorecard as evidence.
3. Use the durable store for crash recovery instead of (or alongside) `.fakoli/runs/` scratch.

Benefits: one source of truth for live work, crash recovery, audit trail, file-conflict
enforcement (P1-8 becomes load-bearing). Large; design-led; not in this pass.

---

## 8. Execution order for this unattended pass

Implement lowest-risk-first, full suite green + commit after each:
P0-1, P1-6, P1-5, P1-7 (flow, markdown) → P2-12 status-file lines (crew, markdown) →
P0-4, P1-9 (state, localized) → P0-2 (state, migration txn) → P0-3, P1-8 (state, schema/path).
Anything that can't go green is reverted and documented here as *designed-not-applied*.

### 8.1 Outcome of the unattended pass (2026-06-02)

**Applied, tested, committed** (state suite green at 1257 throughout):

| Item | Plugin | Commit |
|------|--------|--------|
| P0-1 run-id collision | flow | `73e9d3c` |
| P1-5 verify→finish coupling | flow | `73e9d3c` |
| P1-6 missing-status + escalation deadline | flow | `73e9d3c` |
| P1-7 plan pre-flight validation | flow | `73e9d3c` |
| P2-12 critic status-file contract | crew | `c206ce1` |
| P0-4 bounded tail scan | state | `72218dc` |
| P1-9 observable audit health | state | `7aa7270` |
| P0-2 atomic + recoverable migration | state | `eadf94c` |
| 1.21.0 release packaging | state | `b2fd460` |

**Designed, NOT applied** — deferred as too risky to land unattended; both require
threading new state through the correctness-critical event-sourced write path:

- **P0-3 (claim id reissue guard).** Requires a v3→v4 `SCHEMA_VERSION` bump, a new migration
  branch, and regeneration of the replay/snapshot fixtures. Also note a correction to §4: a
  bare `UNIQUE(id, task_id)` does **not** fix the misroute — `PRIMARY KEY(id)` already makes
  `id` unique, so `INSERT OR IGNORE` still drops a reissued id silently. The real fix is to
  stop using blind `INSERT OR IGNORE` for claims and instead detect an id-reuse-against-
  different-task at the check layer (`_check_claim_created`) and reject it explicitly. Land
  this with full attention + fixture regen, not overnight.
- **P1-8 (evidence file-scope).** The evidence gate (`transitions._evidence_complete`) sees
  only `Task` + `Evidence`; the claim's `expected_files` is not in scope there. Surfacing an
  out-of-scope-file warning means plumbing the active `Claim` into the evidence-submission
  validation path — a cross-cutting change to the append/check flow. Do it deliberately with
  a decision on warn-vs-reject policy and a config knob.

Everything else in P2 (SSOT dedup, canonical protocol doc, version matrix, Codex tiering,
tool-allowlist review) and S1 (flow↔state integration) remains open as documented.

## 9. Verification commands
- state: `cd plugins/fakoli-state/bin && uv run pytest -q`
- flow/crew markdown: structural review (no executable tests); changes are additive to skills.
