# Fakoli Stack Architecture

*Core document. Last reviewed 2026-06-10 (flow 1.3.0, crew 2.8.0, state 1.21.0).
Companion to [POSITIONING.md](POSITIONING.md), which covers the field; this covers
how the thing is built and which guarantees are real.*

## The shape of the system

Three plugins, designed together, each useful alone:

```
            ┌─────────────────────────────────────────────────┐
            │                   fakoli-flow                   │
            │   policy layer: brainstorm → plan → execute →   │
            │   verify → finish · wave engine · critic gates  │
            └───────────────┬─────────────────┬───────────────┘
                 dispatches │                 │ reads/writes
                            ▼                 ▼
            ┌───────────────────────┐   ┌─────────────────────────────┐
            │      fakoli-crew      │   │         fakoli-state        │
            │ opinion layer: 8 role │   │ truth layer: event-sourced  │
            │ agents, tool allow-   │   │ task/claim/evidence engine  │
            │ lists, style refs     │   │ (JSONL log → SQLite proj.)  │
            └───────────────────────┘   └─────────────────────────────┘
```

**flow** decides how work moves. **crew** decides who does it and with what
discipline. **state** decides what is true — durably, with receipts. The repo also
ships satellite plugins (gws, safe-fetch, nano-banana-pro, …) that share the
marketplace infrastructure but not this architecture.

## The five design positions

Every structural choice below traces to one of these:

1. **Intent over prescription.** Plans carry intent + acceptance criteria, never
   implementation code. Agents read the live codebase; plans written yesterday don't.
   (Measured basis: 30–40% of plan-embedded code required modification during
   execution in the BAARA Next phases that used prescriptive plans.)
2. **Enforcement lives in hooks, not prose.** Any rule described as "mandatory" must
   be backed by a mechanism that fires regardless of what the model decides. Prose
   gates fail in both directions — models rationalize past them ("this task is
   simple, so I'll skip review") and over-apply them (ceremony on trivial edits).
   The field's largest skills framework has both failure modes in its top-ten issue
   clusters; we adopted the lesson structurally.
3. **State is durable, project-scoped, and evidence-bearing.** Task status, claims,
   and completion evidence live in the repository's `.fakoli-state/`, not in a
   session, a context window, or a home-directory cache. Sessions die; state doesn't.
4. **A small fixed crew beats a sprawling roster.** Nine role agents with explicit
   tool allowlists. Roles are functional (architect, reviewer, integrator…), not
   domain-themed. Growth requires evidence of demand, not enthusiasm — the ninth
   seat (warden) was added only after a field scan found the security auditor to be
   the single consensus archetype every serious roster has and we lacked.
5. **Defaults with escape hatches, never mandates.** Branch isolation, gates, and
   auto-expansion are on by default and each has a documented opt-out
   (`FAKOLI_FLOW_NO_GATE=1`, `auto_expand: false`, …). Forced workflow is the
   single angriest complaint cluster in competitor issue trackers.

## fakoli-flow — the policy layer

Six skills: `brainstorm`, `plan`, `execute`, `verify`, `finish`, plus `quick` (the
calibration valve — single agent, one review cycle, no waves, for ≤2-file tasks).

### The wave engine (`skills/execute/SKILL.md`)

- Tasks declare `Depends on:`; the engine assigns Wave 1 to dependency-free tasks
  and Wave N+1 to tasks whose dependencies all sit ≤ N. Same-wave tasks must have
  disjoint file scope.
- Each dispatch prompt carries exactly six things: intent, acceptance criteria,
  scope, upstream context (extracted from prior status files), verify command, and
  the absolute status-file path. Agents never receive the whole plan — work packets
  over monoliths.
- Run identity: `<sanitized-plan-basename>-<YYYYMMDDHHmmss UTC>`, scratch root
  `.fakoli/runs/<run-id>/` (gitignored).

### The critic gate — what is actually guaranteed

The gate's state machine is maintained by two hooks
(`plugins/fakoli-flow/hooks/gate-track.sh`, `gate-check.sh`) and armed per-run via
`.fakoli/gate-armed`:

```
                 writer completes (guido|smith|welder)
   CLEAR ────────────────────────────────────────────▶ PENDING
     ▲                                                    │
     │            critic completes a review               │ PreToolUse denies
     └────────────────────────────────────────────────────┤ every dispatch except
                                                          │ critic & welder
                 welder fix completes ───────────────────▶│ (re-PENDING — fix
                                                            cycles force re-review)
```

The invariant: **no new wave starts after a write without a critic review that
happened after that write.** The hook cannot know whether the critic said PASS or
MUST FIX — and doesn't need to: a welder fix re-pends the gate, so the documented
fix-cycle semantics fall out of two state transitions.

Fail-open properties (deliberate): 24-hour stale-arm expiry, `FAKOLI_FLOW_NO_GATE=1`,
malformed hook input ignored, generic-fallback (non-crew) dispatches not tracked.
The hook emits both the current PreToolUse deny contract
(`hookSpecificOutput.permissionDecision`) and the legacy top-level fields.

### Verification (`skills/verify/SKILL.md`)

Two layers, both evidence-gated:

1. **Sentinel scorecard** — every PASS must cite fresh command output from this
   session; scorecards end with a machine-readable JSON verdict
   (`{"verdict", "pass", "fail", "na", "failures":[{"check","fix_owner"}]}`).
2. **Adversarial refutation (Step 5.5)** — a second sentinel is dispatched to
   *break* every PASS with its own commands. A criterion passes only when both
   agree; disagreements surface to the user rather than being silently resolved.

## fakoli-crew — the opinion layer

| Agent | Role | Writes? | Model | Notes |
|---|---|---|---|---|
| guido | architect / design | yes | opus | polyglot; quantified language detection (≥80% silent, 50–79% stated, <50% ask) |
| critic | code reviewer | **no** | opus | two-stage: spec compliance (`[SPEC]` MUST FIX) before code quality; checklist lives in an evolvable reference, safety floor inline |
| scout | researcher | refs only | sonnet | Bash for read-only liveness checks; facts marked VERIFIED vs DOCUMENTED; standard output template |
| smith | plugin engineer | yes | sonnet | owns manifests/hooks/commands internals |
| welder | integrator | yes | sonnet | facades, re-exports, shims; the only agent allowed through a pending gate besides critic |
| herald | docs writer | docs only | sonnet | reads source before claiming anything |
| keeper | repo infrastructure | yes | sonnet | surgical edits; Iron Rule scoped to edited + directly referenced files |
| sentinel | QA validator | **no** | haiku | deterministic validation; sonnet override for oversized scorecards; must declare partial reads |
| warden | security auditor | **no** | opus | second review gate, parallel to critic: exploitability (injection, secrets, supply chain, plugin permission surfaces); scanner absence is N/A, never PASS |

Contracts that make the crew composable:

- **Iron Rule** (`skills/crew-ops/references/iron-rule.md`): read every file in
  scope before editing any.
- **Status files** (`references/communication.md`): the inter-agent protocol —
  required fields, `IN_PROGRESS | COMPLETE | NEEDS_REVIEW | BLOCKED`, structured
  Decisions. Schema-validated by orchestrators; malformed → NEEDS_REVIEW.
- **File ownership** (`references/file-ownership.md`): one writer per file per
  session; secondary agents request changes via status files.
- Read-only roles are enforced by **tool allowlists**, not by promises — critic and
  sentinel physically lack Write/Edit.

## fakoli-state — the truth layer

The moat. ~23k LOC Python, 1,275 tests, test:code ratio ≈ 1.35.

### Event-sourced core

```
append(event):
  validate (Pydantic) → flock(events.jsonl) + thread lock
    → assign id E{N:06d} → write JSONL line (log-first)
    → BEGIN IMMEDIATE → project into SQLite → COMMIT
```

- `events.jsonl` is the **source of truth**; `state.db` is a projection that
  `replay_from_empty()` reconstructs byte-for-byte. Torn trailing lines are
  tolerated; forward catch-up heals post-COMMIT skew on the next initialize.
- Lock contention uses exponential backoff with jitter (10ms → 500ms cap, 5s
  budget) measured on an injectable **monotonic** clock — wall-clock NTP steps
  cannot stretch or truncate the timeout.
- All time flows through a `Clock` protocol (`SystemClock` / `FrozenClock`);
  no naked `datetime.now()` in production paths. This is why the suite is
  deterministic.

### Work lifecycle

```
PRD → requirements → features → tasks(scored 6-dim) → ready
  → claim (lease, TTL 60m default, renewable, conflict-checked)
  → in_progress → submit evidence → needs_review → accepted | rejected
```

- **Claims are leases**, not flags: expiry returns abandoned work to the pool;
  stale detection runs idempotently on every mutating call.
- **Conflict prediction at claim time**: `check_conflicts` intersects the claim's
  likely files against active claims; conflict groups block incompatible parallel
  claims before any work starts.
- **Evidence is a state transition, not a vibe**: `needs_review` is reachable only
  via `submit_completion_evidence` (commands run, files changed, commit SHA,
  output excerpts). Verifiers inspect artifacts, never transcripts.
- **Scores drive expansion** (1.21.0): complexity ≥ `auto_expand_threshold`
  (default 4) queues the task for decomposition — CLI prints the EXPANSION QUEUE,
  MCP returns `expansion_queue`, the plan skill auto-dispatches the planner.

### Surfaces

CLI (23 commands) and MCP (22 tools) are both **thin wrappers over the same
managers** (ClaimManager et al.). A 2026-06 reconnaissance measured 70–100% logic
reuse per operation and the unification refactor was rejected — recorded in
[POSITIONING.md](POSITIONING.md). Invest in the managers, not in dispatch layers.

### Sync and reconciliation

Three sources of truth can drift: SQLite, the filesystem (packets, worktrees), and
git/GitHub. The reconciliation engine scans for orphan branches/packets, stale
claims, and sync drift, reports discrepancies, and fixes only behind
`sync --fix --yes`. GitHub Issues sync is bidirectional with per-mapping conflict
strategies.

### Where it's going

[`plugins/fakoli-state/docs/specs/2026-06-10-git-backed-events.md`](../plugins/fakoli-state/docs/specs/2026-06-10-git-backed-events.md):
hash-chained event IDs replace machine-local `E{N}`, the log commits to git with a
`merge=union` driver, replay becomes order-tolerant and idempotent, and git becomes
the sync layer. State stops being machine-scoped and starts traveling with the
repository. Phased: A (IDs + replay + migration), B (cross-branch claim
reconciliation via `claim.superseded`), C (cross-machine actor identity).

## Integration contracts

| From | To | Contract |
|---|---|---|
| flow → crew | Agent dispatch | six-field prompt + absolute status path; model pinned per role in the call |
| crew → flow | status files | schema in `communication.md`; BLOCKED/NEEDS_REVIEW must surface to the user |
| crew → flow | sentinel verdict | fenced JSON block; orchestrator branches without scraping prose |
| flow → state | (when installed) | plan tasks from `ready` queue; claims before dispatch; evidence on completion |
| state → anyone | work packets | `generate_work_packet` renders task intent + criteria + context — agents never read the whole plan |
| hooks → everyone | gate state | `.fakoli/gate-armed` + `gate-state.json`; deny via PreToolUse contract |

## The enforcement ladder (honest version)

What is mechanically guaranteed vs. convention. Keeping this table truthful is a
standing maintenance obligation — the original sin this stack corrected was calling
a prose rule "unskippable."

| Rule | Mechanism | Grade |
|---|---|---|
| Critic review after every code-writing wave | PreToolUse/PostToolUse hooks + arming file | **Hard** (when armed, crew-typed dispatches) |
| Critic/sentinel cannot modify code | tool allowlists in agent frontmatter | **Hard** |
| Evidence before `needs_review` | state-machine transition in fakoli-state | **Hard** |
| Claim exclusivity + lease expiry | DB constraints + idempotent stale reaping | **Hard** |
| Conflict-group parallel exclusion | claim-time check in ClaimManager | **Hard** |
| WebFetch/WebSearch interception (safe-fetch) | PreToolUse deny | **Hard** |
| Intent-driven plan format | plan skill instructions + review | Convention |
| File ownership within a wave | orchestrator assignment + status files | Convention |
| Status-file completeness | schema + orchestrator validation | Convention (validated) |
| Iron Rule (read before edit) | agent prompts | Convention |
| Generic-fallback runs (no fakoli-crew) | prompt rules only | Convention |

Direction of travel: conventions migrate up this ladder when they prove load-bearing
(the critic gate made that trip in flow 1.2.0). Anything marketed as enforced must
sit in the top half.

## Invariants — do not break these

1. `events.jsonl` is append-only and is the source of truth; SQLite is disposable.
2. Local-mode replay is byte-equal: same log → same DB, always.
3. Every "PASS" cites fresh evidence from the current session.
4. Read-only agents stay read-only (allowlists, not intentions).
5. Hooks fail open — a broken hook must never block unrelated work.
6. Three marketplace sources stay in sync: README table, `registry/index.json`,
   `marketplace.json` (regenerate, never hand-edit).
7. Version bump on any plugin file change; consumers cache by version.
8. The enforcement ladder above stays honest — docs never claim a guarantee the
   code doesn't provide.
