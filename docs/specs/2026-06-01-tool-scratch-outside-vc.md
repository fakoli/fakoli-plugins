# Tool Scratch Outside Version Control — Design Spec

**Goal:** Establish and enforce one rule across the Fakoli plugins: transient tool scratch (agent status files, run state) lives outside version control, while intent (specs and plans) stays version-controlled. Re-point the fakoli-flow/fakoli-crew wave engine to write status files to a gitignored per-run scratch root, and record the rule as fakoli-style principle P10 (proven).

**Date:** 2026-06-01
**Status:** Approved (brainstorm sections 1-3 approved by user)
**Spec path:** docs/specs/2026-06-01-tool-scratch-outside-vc.md (no CLAUDE.md override)

---

## Context

The fakoli-flow wave engine instructs every dispatched crew agent to write a coordination status file to `docs/plans/agent-<name>-status.md` — inside the repo. The orchestrator reads these between waves (for the critic gate and next-wave context). These files are run-local process mechanics with no lasting value, yet they land in version control and clutter PR diffs and history. The same convention is duplicated as a literal path across ~20 files in fakoli-flow and fakoli-crew, and is referenced by fakoli-state docs.

This spec generalizes the narrow "status files shouldn't be committed" observation into a durable rule, and applies it to its first concrete instance (the wave-engine status files).

## The Rule

Every artifact sorts into exactly one category:

- **Durable (version-controlled):** captures intent and decisions; reviewed in the PR diff; useful to someone reading history months later. Examples: specs (`docs/specs/`), plans (`docs/plans/<date>-<feature>.md`), design docs, ADRs, the fakoli-style ledger.
- **Scratch (never version-controlled):** run-local process mechanics with no value after the run ends. Examples: agent status files, server PID/log/event files, screenshots, evidence buffers, temp notes.

**Sorting test:** *"Would a reviewer want this in the PR diff, and would it help someone reading history in six months?"* Yes → durable. No, it is just how a run coordinated itself → scratch.

## Architecture & Path Contract

- **One scratch root per run:** `.fakoli/runs/<run-id>/` at the repo root. `.fakoli/` is gitignored.
- **Status files** move from `docs/plans/agent-<name>-status.md` to `.fakoli/runs/<run-id>/agent-<name>-status.md`.
- **run-id** is chosen once by the orchestrator at the start of `/flow:execute`, derived from the plan filename plus a short timestamp, and stays stable for the whole run.
- **flow↔crew contract:** crew subagents and the flow orchestrator are separate invocations, so they cannot independently recompute a shared path. The orchestrator computes the run-dir once and **injects the absolute status-file path into each agent's dispatch prompt** ("write your status to `<abs-path>`"). Agents no longer hardcode any path. `status-protocol.md` changes from a fixed location to: "write to the path the orchestrator gives you; the default scratch root is `.fakoli/runs/<run-id>/`."
- **Plans and specs are untouched:** still `docs/plans/<date>-<feature>.md` and `docs/specs/`, still committed. Only the `agent-*-status.md` references move; plan/spec references stay.

## Data / Artifacts Changed

### fakoli-style — record the rule as P10 (proven)

Add principle **P10** to `plugins/fakoli-style/data/principles.json` and regenerate `docs/fakoli-style.md`:

- `id`: `P10`
- `name`: `Tool scratch lives outside version control`
- `principle`: `Run-local process artifacts are gitignored; only intent (specs and plans) is committed.`
- `why`: `Committing scratch clutters history and PR diffs with mechanics that have no value after the run.`
- `status`: `proven`
- `proof`: `tests/test-scratch-not-tracked.sh` (a repo-level executable check; see Enforcement)
- `embodied_in`: `.gitignore` (the guard) and `plugins/fakoli-flow/references/status-protocol.md` (the contract)
- `credibility_risk`: `med`

### fakoli-flow — re-point the wave engine

- `references/status-protocol.md` — canonical: rewrite the "File Location" section to the orchestrator-injected path + `.fakoli/runs/<run-id>/` default.
- `skills/execute/SKILL.md` — compute run-id at start; inject absolute status path into every dispatch prompt; read status from the run-dir; collect modified files from the run-dir.
- `skills/plan/SKILL.md` — scout status path.
- `skills/verify/SKILL.md` — sentinel status path.
- `references/example-dispatch-prompt.md`, `references/wave-engine-ref.md` — update the status-file references.
- `docs/wave-engine.md`, `docs/getting-started.md` — update for accuracy.
- Historical `docs/plans/2026-04-04-*` and `docs/specs/2026-04-04-*` are left as-is (they are a record, not live instruction).

### fakoli-crew — agents write where told

- `skills/crew-ops/SKILL.md`, `skills/crew-ops/references/communication.md`, `references/file-ownership.md` — update the status protocol to "write to the path you are given."
- All 8 agent definitions (`agents/*.md`) — replace "write to `docs/plans/agent-<name>-status.md`" with "write your status to the path the orchestrator provides."
- `README.md`, `CHANGELOG.md`, and `tests/` (`RECIPES.md`, `test_critics.sh`) — update any asserted path.

### repo

- `.gitignore` — add `.fakoli/`.

## Enforcement

- **Mechanical guard:** `.gitignore` `.fakoli/` makes it impossible to commit run scratch.
- **Proven check (`tests/test-scratch-not-tracked.sh`):** an executable test that fails if the rule is violated. It asserts (1) a representative path under `.fakoli/` is git-ignored (`git check-ignore` succeeds) and (2) no file under `.fakoli/` is tracked (`git ls-files .fakoli/` is empty). This proves the guard holds for the new scratch location without depending on the deferred legacy cleanup. This is P10's `proof` pointer, so fakoli-style's validator will require it to resolve to a real test file.

## Acceptance Criteria

1. `.fakoli/` is gitignored; `git check-ignore .fakoli/runs/x/agent-y-status.md` resolves (ignored).
2. `tests/test-scratch-not-tracked.sh` exists, is under `tests/`, and exits 0 on the current repo state.
3. No live instruction to write status files to `docs/plans/agent-*` remains in fakoli-flow skills/references or fakoli-crew skills/agents (verified by grep; historical `docs/plans|specs/2026-04-04-*` excepted).
4. `references/status-protocol.md` describes the orchestrator-injected path and the `.fakoli/runs/<run-id>/` default; `skills/execute/SKILL.md` computes a run-id and injects the absolute status path into dispatch prompts.
5. All 8 fakoli-crew agent definitions instruct writing to the orchestrator-provided path, not a hardcoded `docs/plans/` path.
6. fakoli-style ledger contains P10 (proven) with the proof pointer resolving; `plugins/fakoli-style` `validate.py` exits 0 and the generated doc is in sync.
7. Plan and spec references (`docs/plans/<date>-<feature>.md`, `docs/specs/`) are unchanged and still committed.
8. fakoli-flow, fakoli-crew, and fakoli-style each get a version bump (minor); `generate-index.sh` regenerated; the three sync sources agree; `validate.sh` passes for all three.

## Out of Scope

- **Legacy migration:** untracking the already-committed `agent-*-status.md` files under `plugins/fakoli-crew/docs/plans/` and `plugins/fakoli-state/docs/plans/` is a separate follow-up. The gitignore added earlier (`**/docs/plans/agent-*-status.md`) stops new ones; this spec does not untrack the existing ones.
- Moving the visual-companion `/tmp` session dir to `.fakoli/` (it already lives out of tree; leave it).
- fakoli-state behavior changes (only its doc references to the convention, if any are live instructions, are in scope — historical/backlog docs are left as-is).
