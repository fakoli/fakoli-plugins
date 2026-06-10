# Spec: fakoli-flow on Native Agent Teams — Thin Policy Over Native Orchestration

**Status:** PROPOSED
**Date:** 2026-06-11
**Owner:** fakoli-flow
**Depends on:** Agent Teams (Claude Code v2.1.32+, experimental, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`); fakoli-state git-backed events (PROPOSED, see `plugins/fakoli-state/docs/specs/2026-06-10-git-backed-events.md`)
**Related:** fakoli-flow execute skill (`skills/execute/SKILL.md`), critic-gate hooks (`hooks/gate-check.sh`, `hooks/gate-track.sh`)

## Why

fakoli's whole positioning is **"a thin policy layer over native orchestration"** — hammers (specialist agents + the discipline that drives them), not a re-implementation of the anvil (dispatch, claiming, locks). Until June 2026, fakoli-flow had to ship the anvil too: the wave engine *is* a hand-rolled orchestrator (in-context dependency graph, parallel `Agent()` dispatch, status-file polling, a shell-hook-enforced critic gate). Every line of that is scaffolding we maintain because the platform didn't offer it.

Anthropic now offers it. **Agent Teams** (`code.claude.com/docs/en/agent-teams`) ships exactly the primitives the wave engine emulates: a team lead spawning teammates with their own context windows, a shared task list with `pending`/`in_progress`/`completed` states, dependency-blocked claiming, file locking on claim, self-claim after finishing, an inter-agent mailbox (`SendMessage`), plan-approval gates, and — critically — three lifecycle hooks (`TaskCreated`, `TaskCompleted`, `TeammateIdle`) that **block with exit code 2** (`code.claude.com/docs/en/hooks`).

This is the stack's single biggest strategic opportunity. superpowers' hottest open issue (#429, 112 reactions) is users begging for native Agent Teams integration. The orchestration layer is being commoditized by the platform. fakoli-flow's job is to stop owning the commodity and double down on what stays scarce: **the intent-driven plan format, the critic-gate policy, the evidence rules, and the durable state layer.** The critic gate is the cleanest win — fakoli already proved hook-enforced gating works (`gate-check.sh` denies non-critic dispatch via a `PreToolUse` deny while a write is un-reviewed); `TaskCompleted` exit-2 is the same idea, now a first-class platform event instead of a `PreToolUse` workaround.

There is one gap the platform does **not** close, and it is the gap fakoli-state was built for. Team and task state is ephemeral: `~/.claude/teams/{team}/config.json` and `~/.claude/tasks/{team}/` are "removed when the team is cleaned up or when the session ends." The native task list is a *working set*, not a *system of record*. fakoli-state is the durable backbone underneath it — the source of truth that survives cleanup, carries evidence, and travels with the repo.

### Scope note: Agent Teams, not Dynamic Workflows

Anthropic shipped a second parallel-orchestration feature in the same window: **Dynamic Workflows** (`code.claude.com/docs/en/workflows`) — a JavaScript script Claude writes, executed by a background runtime, with intermediate state in **script variables**. The two differ on *who holds the plan*: in a workflow the **script** decides what runs next; in agent teams **the lead agent** decides turn by turn, and results live in a **shared task list**.

fakoli-flow maps onto **Agent Teams**, not Dynamic Workflows, and the reason is load-bearing: fakoli-flow's value is a *lead-driven, gate-interrupted, human-steerable* loop (the user approves the spec, the critic gate halts between waves, escalations surface to the user). That is the agent-teams shape. A Dynamic Workflow buries the loop in code and only surfaces the final answer — which is the right tool for a 500-file bug sweep but the wrong tool for a gated, intent-driven feature build where the human checkpoint *is* the product. The relationship is covered as an open question (§6), not a mapping target.

## Design

### 1. Primitive mapping: wave engine → Agent Teams

The wave engine and Agent Teams describe the same problem at the same altitude. The table below is the spine of this spec: for each fakoli-flow concept, the native primitive that subsumes it, and the fidelity of the match.

| fakoli-flow concept | Native Agent Teams primitive | Fidelity | Notes |
|---|---|---|---|
| **Wave** (dependency-ordered batch of parallel tasks) | Shared task list + dependency-blocked claiming ("a pending task with unresolved dependencies cannot be claimed until those dependencies are completed") | **Clean** | The wave engine's level-by-level topological sort becomes implicit. We stop computing waves in-context; we declare `dependsOn` and let teammates self-claim the unblocked frontier. Waves were always a *scheduling artifact* of doing this by hand. |
| **Parallel dispatch within a wave** (`Agent()` calls in one message) | Teammates self-claiming unblocked tasks; each in its own context window | **Clean** | Native teammates are persistent sessions, not fire-and-forget subagents — strictly more capable (they can be messaged mid-flight). |
| **File ownership / conflict-groups** (plan-time rule: no two same-wave tasks touch the same file) | **File locking on claim** ("Task claiming uses file locking to prevent race conditions") | **Partial** | Native locking prevents *claim* races; it does **not** know fakoli's *semantic* conflict-groups (files that must not be edited concurrently even across waves). See §6. Plan-time ownership stays as advisory metadata; native locking is the runtime enforcer. |
| **Critic gate** (hook-denied dispatch until critic PASS) | **`TaskCompleted` blocking hook (exit 2)** | **Clean — the marquee win** | Re-expressed in §3. The platform now has a native "you may not mark this done" event; the gate moves from a `PreToolUse` workaround onto the event built for it. |
| **Language verification** (`tsc`/`ruff`/`cargo` between wave and critic) | **`TeammateIdle` blocking hook (exit 2)** | **Clean** | "Exit with code 2 to send feedback and keep the teammate working." A teammate that finishes with a broken typecheck is held, not idled. |
| **Status files** (`agent-<name>-status.md`: files-modified, decisions, escalations) | **Shared task list** (status, claims) **+ mailbox / `SendMessage`** (decisions, escalations, hand-off context) | **Partial** | Two native channels replace one file convention. Structured status (done/blocked) → task list; freeform context (decisions, "notes for welder") → mailbox. The *evidence* portion of a status file has **no** native home → fakoli-state (§4). |
| **Run scratch root** (`.fakoli/runs/<run-id>/`) | **No durable native equivalent** | **None → fakoli-state** | Native scratch is `~/.claude/tasks/{team}/`, destroyed on cleanup. The run's identity, evidence, and audit trail must live in fakoli-state to outlive the team. The run-id concept is preserved as a fakoli-state project/run key. |
| **Sentinel verdict** (final evidence scorecard, machine-readable `{"verdict": "READY"…}`) | **No native equivalent** (a final `TaskCompleted` hook on a terminal "ship" task can *gate* on it, but does not *produce* it) | **None → fakoli-state** | Sentinel is a fakoli *role* producing a fakoli *artifact* (evidence-bearing scorecard). The platform offers an enforcement point (the terminal task's `TaskCompleted` hook reads the verdict and blocks if `NOT_READY`); it does not offer the verdict. Evidence rules stay fakoli's. |
| **Critic / sentinel / guido / welder roles** | **Subagent definitions used as teammate types** ("reference a subagent type … the definition's body is appended to the teammate's system prompt") | **Clean** | fakoli-crew agents become teammate types. Their *expertise* is fakoli's; the *spawning* is native. Caveat: a subagent definition's `skills` and `mcpServers` frontmatter are **not** applied when run as a teammate — teammates load skills/MCP from project+user settings (§6). |
| **Graceful degradation** (generic subagents when no crew) | **Subagent definitions are optional**; teammates work without a referenced type | **Clean** | Same fallback shape; native teammates with a plain spawn prompt replace `general-purpose` subagents. |
| **BLOCKED / NEEDS_REVIEW escalation to user** | **Mailbox to lead + direct teammate messaging**; lead surfaces to user | **Clean** | "When a teammate finishes and stops, they automatically notify the lead." The user can message any teammate directly (Shift+Down) — strictly better than status-file polling. |
| **Brainstorm / plan phases** (spec → intent plan) | **Plan-approval gate** (teammate plans in read-only mode; lead approves) | **Partial — different altitude** | Native plan-approval is *per-teammate, per-task* ("should this teammate's approach proceed"). fakoli's brainstorm/plan is *whole-project, pre-dispatch* ("what is the spec, what are the tasks"). They compose rather than collide (§6), but the overlap must be called out so we don't double-gate. |

**Reading the fidelity column.** Eight rows are **Clean** — the platform genuinely subsumes the mechanism, and fakoli should delete its copy. Three are **Partial** — the native primitive covers the common case but misses a fakoli-specific guarantee (semantic conflict-groups, evidence in status, whole-project planning). Three are **None** — run scratch, sentinel verdict, and (the heart of it) durable state have *no* native equivalent and define fakoli's remaining surface area.

### 2. Division of labor: hammers vs. anvil

The positioning resolves cleanly against the mapping. **The platform is the anvil; fakoli forges the hammers and dictates how they strike.**

**What fakoli DELEGATES to the platform (the anvil — stop owning these):**

- **Raw dispatch.** `Agent()`-per-task in a single message → native teammate spawning. Delete the parallel-dispatch choreography.
- **Claiming mechanics.** In-context wave computation + "who picks up what" → native self-claim from the unblocked frontier. Delete the topological sort.
- **File locks.** Plan-time "don't put these in the same wave" as the *only* guard → native file-locking-on-claim as the runtime guard.
- **Status transport.** `agent-<name>-status.md` polling loop → native task list (status) + mailbox (context). Delete the 10-second poll.
- **Idle/done detection.** "Wait for all status files to show terminal state" → native idle notifications ("they automatically notify the lead").

**What fakoli KEEPS owning (the hammers and the rules — these stay scarce):**

- **Intent-driven plan format.** Acceptance-criteria-not-code, the prescriptive exceptions (schema/security/contracts/config), the scout-verify-before-planning step. This is fakoli's answer to superpowers #895 and the platform has no opinion here. The plan format is what *populates* the native task list with `dependsOn` edges and per-task acceptance criteria.
- **Critic-gate POLICY.** Native `TaskCompleted` gives the *enforcement point*; fakoli supplies the *policy that runs there*: two-stage review (spec-compliance before code-quality), the MUST/SHOULD/CONSIDER/NIT taxonomy, the max-3 fix-cycle, "no new work after a write without a critic pass that happened after that write." The hook is the platform's; the verdict logic is fakoli's.
- **Evidence rules.** The sentinel's evidence gate (exit-code-0-not-"should-work", fresh-this-session-not-prior-output). The machine-readable `READY/NOT_READY` verdict. The platform offers no evidence semantics; this is pure fakoli.
- **The durable state layer.** fakoli-state as source of truth under the ephemeral team (§4). This is the moat the June 2026 positioning names explicitly, and Agent Teams *sharpens* the case for it by making the working set provably disposable.
- **Roles + expertise.** The fakoli-crew agent definitions (guido/welder/scout/critic/sentinel/…) supplied as teammate types. The platform spawns them; their judgment is fakoli's.

The boundary test: **if the platform changing its dispatch internals would break it, it was the anvil — delegate it. If it encodes engineering judgment or durable truth, it is a hammer — keep it.** Wave-scheduling is anvil. Two-stage critic review is hammer.

### 3. The critic gate as a `TaskCompleted` exit-2 hook (the cleanest win)

fakoli already proved hook-enforced gating works. Today's gate is a *`PreToolUse` deny*: while `.fakoli/gate-armed` exists and `gate-state.json` shows `pending=true`, `gate-check.sh` denies dispatch of any subagent except `*critic`/`*welder` (returning `permissionDecision: deny`), and `gate-track.sh` (`PostToolUse`) flips `pending` true when a writer (`guido`/`smith`/`welder`) completes and clears it when the critic completes. It is a *workaround*: `PreToolUse` was the only blocking surface available, so the gate is expressed as "deny the next dispatch" rather than the thing it actually means — "this work is not done until a critic has passed it."

Agent Teams gives the gate its native home. `TaskCompleted` "runs when a task is being marked complete. Exit with code 2 to prevent completion and send feedback." That is the gate's actual semantics, first-class.

**Re-expression:**

```
TaskCompleted hook (fires when any code-writing task is marked complete):
  1. Read the task's modified-files set (from the claim's file locks / task metadata)
     and acceptance criteria (carried from the fakoli plan into the task).
  2. Has a critic PASS been recorded *after the last write to those files*?
       - Look up the critic verdict for this task in fakoli-state
         (durable; survives the teammate that produced it — see §4).
     YES, PASS / SHOULD-FIX / NIT (no MUST FIX) → exit 0 (allow completion).
     NO critic pass yet, or MUST FIX open        → exit 2.
         stderr: "fakoli critic gate: task <id> has un-reviewed writes.
                  Dispatch the critic on [files]; resolve MUST FIX before completing.
                  (To bypass: FAKOLI_FLOW_NO_GATE=1.)"
  3. exit 2 keeps the task in_progress and feeds stderr back to the teammate —
     which is exactly the fix-cycle trigger, now driven by the platform.
```

**Why this is strictly better than the `PreToolUse` workaround:**

| Property | Today (`PreToolUse` deny) | Native (`TaskCompleted` exit 2) |
|---|---|---|
| Semantic fit | "deny next dispatch" — a proxy for the real rule | "you may not mark this done" — the rule itself |
| What it gates | the *orchestrator's next `Agent()` call* | the *unit of work's completion*, per-task |
| Granularity | whole-run (one armed flag, one pending bit) | per-task (each task's own completion event) |
| Parallel-safe | fragile: one global `pending` bit can't track N concurrent writers | native: each task carries its own completion gate |
| Self-cleanup | manual disarm on every exit path (`rm .fakoli/gate-armed`) | no arming/disarming; the event only fires on completion |
| Fix-cycle re-pend | manual (`gate-track.sh` re-pends on welder completion) | automatic (a re-completion re-fires `TaskCompleted`) |

The `gate-armed`/`gate-state.json` machinery — and the `PreToolUse`/`PostToolUse` pair that maintains it — is **deleted** in team mode. The escape hatch (`FAKOLI_FLOW_NO_GATE=1`) and the fail-open discipline (any parse error → exit 0) carry over verbatim; both are battle-tested and orthogonal to which event fires.

**One wrinkle, resolved.** The native gate needs the critic verdict to be *durable and queryable at hook time*, because the teammate that ran the critic review may already be idle or gone. A verdict that lives only in a status file or a teammate's context is invisible to the `TaskCompleted` hook of a *different* task. This is why the gate reads the verdict from **fakoli-state** (§4), not from a scratch file — the gate and the durable layer are co-designed, not independent.

### 4. fakoli-state as the durable backbone under ephemeral team state

Native team state is explicitly disposable: `~/.claude/teams/{team}/config.json` (runtime state — session IDs, tmux pane IDs) and `~/.claude/tasks/{team}/` (the task list) are "removed when the team is cleaned up or when the session ends." The docs are blunt: don't hand-edit or pre-author the config; it's overwritten on every state update. This is correct design for a *working set* and disqualifying for a *system of record*.

fakoli-state is the system of record. Its event-sourced, git-backed log (per the git-backed-events spec) is durable, evidence-bearing, repo-scoped, and survives any number of team create/cleanup cycles. The relationship is a **projection + reconciliation** pattern, the same shape fakoli-state already uses internally (JSONL log = truth, SQLite = disposable projection):

```
        AUTHORITATIVE                              WORKING SET (ephemeral)
   ┌───────────────────────┐   project()    ┌──────────────────────────────┐
   │     fakoli-state      │ ─────────────▶ │      Native Agent Team        │
   │  events.jsonl (git)   │                │  ~/.claude/tasks/{team}/      │
   │  • tasks + dependsOn   │                │  • pending/in_progress/done   │
   │  • acceptance criteria │ ◀───────────── │  • file-lock claims           │
   │  • critic verdicts     │   reconcile()  │  • mailbox                    │
   │  • sentinel evidence   │                └──────────────────────────────┘
   │  • claim history       │                         (destroyed on cleanup)
   └───────────────────────┘
```

**Sync direction and authority:**

- **Seed (fakoli-state → team), at team creation.** The fakoli plan, already in fakoli-state as tasks with `dependsOn` edges and acceptance criteria, *projects* into the native task list. The lead creates native tasks from the fakoli task graph. fakoli-state is authoritative for *what the work is*.
- **Mirror (team → fakoli-state), during the run.** As teammates claim/progress/complete, those transitions are written back to fakoli-state as events (`claim.created`, `task.completed`, evidence submissions). The native list is authoritative for *live status during the run*; fakoli-state records the durable trail. This write-back is what makes the §3 gate possible — the critic verdict and the completion event land in fakoli-state where the `TaskCompleted` hook can read them.
- **Reconcile (on init / after cleanup), fakoli-state wins.** When a team is cleaned up (or a session dies mid-run), the native list evaporates. On the next fakoli-state `initialize()`, reconciliation is a no-op for anything already mirrored and a *recovery* for anything the team knew but didn't write back (a task the team marked done in its dying breath). **fakoli-state is the tiebreaker**: its event log, ordered by hybrid logical clock, is ground truth. A native "completed" with no corresponding evidence event in fakoli-state reconciles to "completed-but-unverified" and is re-surfaced, not silently trusted.

**Who is authoritative, by phase, in one line:** fakoli-state owns *definition and history*; the native list owns *live execution status*; on any conflict or after any cleanup, **fakoli-state wins** because it is the only layer that still exists.

This inverts the ephemerality problem into fakoli-state's clearest value statement yet. Before Agent Teams, "durable state" was a nice-to-have over a system (the old wave engine) that already kept everything in-context. With Agent Teams, the platform *advertises* that its task list is destroyed on cleanup — so the durable layer stops being fakoli's nice-to-have and becomes the only thing standing between the user and a lost run. The native cross-machine actor-identity gap (git-backed-events Phase C: "who is `agent-3` on another laptop?") maps directly onto native teammate names, which fakoli-state must canonicalize since native names are lead-assigned per session and non-durable.

### 5. Migration and coexistence

The two modes must coexist; team mode is strictly opt-in, and the legacy wave engine remains the default until Agent Teams graduates from experimental.

**How a user runs flow today (legacy wave engine):**

```
/flow:execute  → load plan → compute waves in-context → Agent()-per-task →
                 poll status files → shell-hook critic gate → sentinel
```

Unchanged. Hook-enforced gate via `.fakoli/gate-armed`. No native dependency. This is the default and stays the default until the platform feature is GA.

**How a user runs flow on teams (new mode):**

```
/flow:execute --teams  (or CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 detected)
   → seed native task list from fakoli-state task graph (§4 seed)
   → lead spawns teammates (fakoli-crew agents as teammate types)
   → teammates self-claim the unblocked frontier (native dependency-blocking)
   → TaskCompleted exit-2 critic gate (§3) + TeammateIdle exit-2 verify gate
   → mirror transitions to fakoli-state (§4 mirror)
   → terminal "ship" task gated on sentinel READY verdict
```

**Coexistence rules:**

- **Opt-in, never auto.** Team mode requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` *and* an explicit `--teams` (or a `flow.teams: true` project setting). The docs are clear teams are "experimental and disabled by default" with known limitations (no session resumption for in-process teammates, task-status lag, slow shutdown) — fakoli must not surprise a user into an experimental path. This also honors the fakoli/superpowers lesson on silent autonomous mode-switching (superpowers #992): never switch execution strategy without consent.
- **Detect, don't assume.** The execute skill detects team availability (env var + `claude --version` ≥ 2.1.32) the same way it detects fakoli-crew today. If unavailable or not opted-in → legacy wave engine. If available + opted-in → team mode.
- **One gate policy, two enforcement backends.** The critic-gate *policy* (two-stage review, MUST-FIX fix-cycle) is shared code. Legacy mode enforces it via `PreToolUse` deny; team mode via `TaskCompleted` exit 2. The policy module doesn't know which backend called it — same separation that lets fakoli-state's managers back both CLI and MCP.
- **Mutually exclusive per run.** A single `/flow:execute` invocation is one mode or the other, never both — the native task list and the in-context wave graph cannot both be authoritative for the same run. (Across runs in a session, mode can vary.)

**Migration is additive, not a rewrite.** Nothing in legacy mode is removed; team mode is a parallel dispatch backend behind the same plan format and the same gate policy. The intent-driven plan (skill `plan`), the brainstorm phase, finish/verify, and quick mode are backend-agnostic and unchanged.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Agent Teams is experimental**; API/primitives may change (hook names, task-state model, file paths) | High | Isolate all native-team calls behind one adapter module; legacy wave engine stays the default and the fallback. Pin to the documented v2.1.32 contract; treat team mode as preview-only until GA. A breaking team-API change degrades to legacy, never to broken. |
| **Native file-locking may not obviate semantic conflict-groups** (locks prevent claim races, not cross-wave logical conflicts on the same file) | Medium | Keep fakoli conflict-groups as advisory plan metadata that shapes `dependsOn` edges (force a dependency between tasks that share a conflict-group so they can't be claimed concurrently). Native locking handles the race; fakoli `dependsOn` handles the semantics. Validate empirically before deleting conflict-groups (§6 Q1). |
| **Plan-approval may duplicate brainstorm/plan**, double-gating the user | Medium | Use native plan-approval *only* for per-task implementation approach (its actual scope); keep fakoli brainstorm/plan for whole-project spec+tasks. Default team mode to **no** per-task plan-approval (the critic gate already enforces quality post-hoc); offer it opt-in for high-risk tasks. (§6 Q2) |
| **Critic verdict invisible to `TaskCompleted` hook** if it lives in teammate context / scratch | High | Verdicts are written to fakoli-state (§3 wrinkle, §4 mirror); the hook reads durable state, never a teammate's memory. This is a hard dependency on the §4 write-back, not optional. |
| **Subagent `skills`/`mcpServers` frontmatter not applied to teammates** — fakoli-crew agents that rely on a bundled skill lose it as teammates | Medium | Audit fakoli-crew agents for skill/MCP dependencies; move any load-bearing skill content into the agent body (which *is* appended to the teammate prompt) or into project/user settings teammates inherit. Document which agents are team-safe. |
| **Ephemeral state lost mid-run** (session dies; no resumption for in-process teammates) | Medium | The §4 mirror writes transitions to fakoli-state continuously, so a dead run reconciles to last-mirrored truth on restart rather than starting blind. This is the durable layer earning its keep. |
| **Token cost**: each teammate is a full session ("significantly more tokens than a single session") | Low | Inherited platform property, surfaced to the user at opt-in. fakoli policy can cap team size (docs recommend 3-5) and route non-critical roles to a smaller default teammate model. |
| **Two code paths to maintain** (legacy + team) | Low | The shared gate-policy + plan-format + fakoli-state core is the bulk; only the dispatch/claim/status backend forks. The fork is the part the platform is absorbing, so it *shrinks* over time as legacy is eventually retired. |
| **Lead may shut down before work is done / start doing work itself** (documented limitation) | Low | fakoli policy in the lead's standing instructions: "wait for teammates; do not implement tasks yourself; do not clean up until the sentinel returns READY." Encoded once in the team-mode lead prompt. |

## Phasing

- **Phase A (ship first): the critic gate on `TaskCompleted`.** The cleanest, highest-signal win and the smallest dependency surface. Re-express the existing gate policy as a `TaskCompleted` exit-2 hook (§3) reading critic verdicts from fakoli-state. Requires the §4 *mirror* write-back for verdicts only (not full bidirectional sync). Behind `--teams`, default off. Proves hook-enforced gating transfers to the native event verbatim — which it should, since fakoli already proved the pattern on `PreToolUse`.
- **Phase B: seed + mirror the task graph.** Project the fakoli-state task graph into the native task list at team creation (§4 seed), and mirror claim/progress/complete transitions back (§4 mirror). Full coexistence: `/flow:execute --teams` runs a real plan end-to-end on native dispatch, with fakoli-state as the durable trail. Add the `TeammateIdle` exit-2 verification gate.
- **Phase C: retire the in-context wave scheduler in team mode.** Once seed+mirror+gates are proven, delete the in-context wave computation and status-file polling *from the team path* (legacy path keeps them). The `gate-armed`/`gate-state.json` machinery is removed in team mode. This is the "stop owning the anvil" payoff — fakoli-flow's team mode becomes genuinely thin.
- **Phase D (gated on platform GA): default team mode on, evaluate retiring legacy.** Only when Agent Teams graduates from experimental and the known limitations (session resumption, status lag, shutdown) are resolved. Until then, legacy is the default. Possibly never fully retire legacy if a no-native-dependency path stays valuable for constrained environments.
- **Out of scope (depends on git-backed-events Phase C):** cross-machine teammate identity canonicalization. Native teammate names are lead-assigned, per-session, non-durable; mapping them to stable fakoli-state actors needs the actor-identity work that git-backed-events itself defers. Not blocking A-C.

## Decision log

- **2026-06-11: Target Agent Teams, not Dynamic Workflows.** fakoli-flow's value is a lead-driven, gate-interrupted, human-steerable loop — the agent-teams shape (lead holds the plan, state in shared task list). Dynamic Workflows move the plan into a JS script and surface only the final answer (state in script variables), which is the wrong altitude for gated intent-driven builds where the human checkpoint is the product. Workflows are tracked as an open question, not a mapping target. (`code.claude.com/docs/en/workflows`)
- **2026-06-11: Critic gate re-expressed on `TaskCompleted`, not `TeammateIdle` or `PreToolUse`.** `TaskCompleted` exit 2 ("prevent completion and send feedback") is the exact semantic of the gate ("this work is not done until a critic passed it"). `TeammateIdle` is reserved for the *verification* gate (hold a teammate with a broken typecheck); `PreToolUse` is the legacy workaround, retired in team mode. (`code.claude.com/docs/en/hooks`)
- **2026-06-11: fakoli-state is the tiebreaker on any state conflict.** The native task list owns live status during a run; fakoli-state owns definition and history and wins on reconciliation — because after cleanup it is the only layer that still exists. The ephemerality of `~/.claude/teams` and `~/.claude/tasks` is not a bug to work around but the precise gap fakoli-state fills.
- **2026-06-11: Conflict-groups kept as `dependsOn`-shaping metadata, pending empirical test.** Native file-locking prevents claim races but is not known to enforce fakoli's cross-wave semantic conflicts. Conflict-groups stay (forcing dependencies between tasks that share one) until a test proves native locking covers the case. Deleting them is gated on Q1.
- **2026-06-11: Team mode is opt-in and mutually exclusive per run.** Honors the platform's "experimental, disabled by default" status and the fakoli/superpowers anti-pattern of silent strategy-switching (#992). Legacy wave engine stays the default until Agent Teams is GA.

## Open questions

1. **Does native file-locking obviate fakoli conflict-groups?** Locking is documented to prevent *claim-time* races on a task. fakoli conflict-groups encode a stronger, *semantic* rule: two tasks must not edit the same file even in different waves. Does claiming a task lock the *files* (blocking any other task that touches them) or only the *task record*? If files, conflict-groups may fully reduce to `dependsOn`; if only the record, fakoli must keep enforcing semantic conflicts. **Needs an empirical test before Phase C deletes anything.**
2. **Does native plan-approval duplicate brainstorm/plan?** Native plan-approval gates a *teammate's per-task implementation approach*; fakoli brainstorm/plan produces the *whole-project spec and task graph*. They appear to compose (project-level fakoli planning, then optional per-task native approval) — but is per-task plan-approval redundant once the critic gate enforces quality post-hoc, or is pre-approval worth the extra gate for high-risk tasks? Default-off vs. default-on is a policy call.
3. **What is the contract fakoli pins to, and what breaks if the Agent Teams API changes?** The feature is experimental; hook names, task-state vocabulary, and state paths (`~/.claude/teams`, `~/.claude/tasks`) could move. Which subset is stable enough to build Phase A on, and is the adapter-module isolation sufficient that a breaking change degrades cleanly to legacy rather than corrupting fakoli-state via a half-completed mirror?

---

## Sources

- Agent Teams — primitives, hooks, state paths, ephemerality, limitations: https://code.claude.com/docs/en/agent-teams
- Hooks — `TaskCreated` / `TaskCompleted` / `TeammateIdle` and exit-code-2 blocking semantics: https://code.claude.com/docs/en/hooks
- Dynamic Workflows — JS-script orchestration, "who holds the plan" comparison vs. agent teams: https://code.claude.com/docs/en/workflows
- fakoli-state git-backed events (durable-state direction, actor-identity Phase C): `plugins/fakoli-state/docs/specs/2026-06-10-git-backed-events.md`
- fakoli-flow execute skill (wave engine, gate arming, dispatch): `plugins/fakoli-flow/skills/execute/SKILL.md`
- Critic-gate hooks (hook-enforced gate, proven pattern): `plugins/fakoli-flow/hooks/gate-check.sh`, `plugins/fakoli-flow/hooks/gate-track.sh`
- superpowers user-feedback research (#895 intent-plans, #992 silent strategy-switch): `plugins/fakoli-flow/docs/research/superpowers-feedback.md`
