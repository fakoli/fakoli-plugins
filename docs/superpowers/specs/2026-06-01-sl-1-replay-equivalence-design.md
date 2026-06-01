# SL-1 — Prove replay in CI (replay-equivalence)

**Date:** 2026-06-01
**Status:** Approved design → implementation plan pending
**Roadmap item:** SL-1 (fakoli-state `docs/roadmap.md`, Wave 1)
**Ledger payoff:** fakoli-style **P4** (prove invariants in CI) `aspirational → proven`; firms **P1** by running its agreement test in CI.

## Problem

fakoli-state's central claim is that canonical state is a deterministic projection of the append-only event log (`events.jsonl`) — replayable, auditable. That guarantee is currently **asserted, not proven**: nothing re-derives state from events and checks it matches, and fakoli-state's unit suite does not run in CI on PRs at all (the only workflow is the nightly live-GitHub cron). SL-1 converts the most-repeated, least-proven claim into a CI-enforced invariant.

## Goal

A green `replay-equivalence` check on every PR: for a non-trivial fixture project, replaying its `events.jsonl` into a fresh database produces canonical state equal to a committed golden snapshot.

## Non-goals (YAGNI)

- No new replay *engine* — `SqliteBackend.replay_from_empty` already exists and is reused as-is.
- No general-purpose snapshot/export CLI surface beyond what the check needs.
- Not SL-2 (critic false-pass), not SL-3 (`ProofArtifact`). This PR proves replay only.
- No masking framework for non-deterministic fields — replay is deterministic; if a field differs, that is a real bug to surface, not noise to hide.

## Design decisions (resolved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Equivalence definition | **Model-level (semantic)** | Compare the modeled state via the read API, not SQLite bytes. Robust to storage incidentals (rowid, `sqlite_sequence`, pragmas); defines equivalence as "the state the system cares about." |
| The "original" | **Golden snapshot (committed JSON)** | Inspectable, diff-able, no binary `.db` in git; the snapshot doubles as documentation of canonical-state shape. |
| CI scope | **Full fakoli-state pytest on PRs** | New workflow runs `pytest -q` on `plugins/fakoli-state/**`, including the replay test. Closes the gap that no fakoli-state tests run on PRs, and makes P1's existing agreement test CI-enforced. |
| Scratch DB location | **tmpdir (never tracked)** | The replay target is run-local scratch — embodies P10 (tool scratch outside version control). |
| CLI surface | `fakoli-state replay --from-events <jsonl> --into <db>` | Thin wrapper over `replay_from_empty`; also useful standalone for disaster recovery. |

## Components

Each unit is small, single-purpose, independently testable.

### 1. `state/snapshot.py` — `serialize_state(backend) -> dict`
- **Responsibility:** read every domain collection (projects, tasks, claims, reviews, sync_mappings — the full canonical surface) in primary-key order and emit a deterministic, canonical-JSON-able dict (sorted keys, stable ordering).
- **Interface:** pure function of a backend's read API; no writes, no clock, no I/O beyond the backend.
- **Reuse:** consumed by the test now; available later to SL-3 (typed proof) and disaster-recovery verification.

### 2. CLI `replay` command
- **Surface:** `fakoli-state replay --from-events <events.jsonl> --into <scratch.db>`.
- **Behavior:** instantiate a `SqliteBackend` pointed at `--into` (a path that is *not* the live `state.db`), call `replay_from_empty(events_path)`, exit 0 on success. Errors (missing events file, unwritable target) produce a clear non-zero exit.
- **Guardrail:** refuse to target the project's live `state.db` path (replay deletes its target).

### 3. Fixture — `tests/fixtures/replay/sample-project/`
- `events.jsonl`: a non-trivial recorded project exercising many event types — project init, multiple tasks, a claim with lease + heartbeat, a renew, a review accept (`needs_review → accepted`), a stale-claim reap, and a sync mapping. Includes at least one `error.transaction_aborted` / `warn.idempotent_no_op` line to prove they are skipped.
- `expected-state.json`: the golden snapshot — `serialize_state` output for that events log, generated once via a documented helper and committed.

### 4. `tests/test_replay_equivalence.py`
- **Equivalence test:** replay fixture `events.jsonl` into a tmpdir DB → `serialize_state` → assert `== expected-state.json`.
- **Idempotence test:** replay the same events into two separate tmpdir DBs → assert the two snapshots are byte-identical (guards determinism directly).
- **Regeneration helper:** a documented path (env flag or small script) to rewrite `expected-state.json` when fixtures legitimately change — a deliberate human act, mirroring fakoli-style's generated-doc discipline (drift is caught by the test, never silent).

### 5. `.github/workflows/fakoli-state.yml`
- Triggers: `pull_request` and `push` on `paths: plugins/fakoli-state/**`.
- Steps: checkout → `astral-sh/setup-uv` → `uv run --project plugins/fakoli-state/bin --with pytest pytest plugins/fakoli-state/tests/ -q`.
- Concurrency group + `permissions: contents: read`, matching repo convention (floating action tags, consistent with the other 6 workflows).

### 6. Ledger update (the payoff — same PR)
- fakoli-style `data/principles.json`: **P4** `aspirational → proven`; `proof` → `plugins/fakoli-state/tests/test_replay_equivalence.py::test_replay_equivalence` (+ the workflow); add `embodied_in` for the replay engine + `state/snapshot.py`. Regenerate `docs/fakoli-style.md` (staleness check); validator stays green.

## Data flow

```
events.jsonl ──replay_from_empty──▶ scratch.db ──serialize_state──▶ dict
                                                                      │
expected-state.json (golden) ─────────────────────────────────── assert ==
```

## Error handling / edge cases

- Missing `--from-events` file: clear error, non-zero exit (CLI) / test fails loudly.
- `replay` targeting the live `state.db`: refused (would delete real state).
- Corrupted / abort / idempotent-no-op event lines: already skipped by `replay_from_empty`; the fixture includes such lines to prove it.
- A genuinely non-deterministic field surfacing as a diff: this is the test doing its job — it has caught a real replay bug; do not mask, fix the bug.
- Schema/migration drift changing canonical shape: regenerate `expected-state.json` deliberately; the diff in the PR documents the intended change.

## Testing strategy (TDD)

1. Write `test_replay_equivalence` first (red — no `serialize_state`/CLI yet).
2. Implement `serialize_state`, then the `replay` CLI; iterate to green.
3. Add the idempotence test.
4. Generate and commit `expected-state.json`.
5. Add the workflow; verify locally with the exact CI command (`uv run --project … pytest …`) before pushing.

## Acceptance criteria

- [ ] `fakoli-state replay --from-events <f> --into <scratch>` rebuilds canonical state from events.
- [ ] `test_replay_equivalence` passes: replayed snapshot == committed golden snapshot.
- [ ] Idempotence test passes: two independent replays are byte-identical.
- [ ] `.github/workflows/fakoli-state.yml` runs the suite on PRs touching `plugins/fakoli-state/**` and is green on this PR.
- [ ] fakoli-style P4 = `proven` with a resolvable proof pointer; ledger validator green and in sync.

## File manifest

**New:** `plugins/fakoli-state/bin/src/fakoli_state/state/snapshot.py`; the `replay` CLI command (in the existing `cli/` package); `plugins/fakoli-state/tests/fixtures/replay/sample-project/{events.jsonl,expected-state.json}`; `plugins/fakoli-state/tests/test_replay_equivalence.py`; `.github/workflows/fakoli-state.yml`.
**Modified:** fakoli-state CLI app registration; `fakoli-style/data/principles.json` + regenerated `docs/fakoli-style.md`; CHANGELOGs; `registry/*` + `marketplace.json`.

## Bookkeeping & sequencing

- Version bumps: fakoli-state **minor** (new `replay` CLI feature); fakoli-style **patch** (P4 flip). Regenerate registry + marketplace.
- **Sequencing dependency:** PR #72 (parks P11) also bumps fakoli-style to 1.1.2 and edits `principles.json`. Merge #72 **before** this PR's ledger step to avoid a `principles.json` / version conflict; this PR then bases its fakoli-style bump on whatever is on `main` at implementation time.

## Risks

- **Hidden non-determinism** in `serialize_state` (e.g., a dict iteration order, an unsorted collection) could make the golden test flaky. Mitigation: canonical sorting in `serialize_state` + the idempotence test catches order instability immediately.
- **Fixture realism:** too thin a fixture proves little. Mitigation: the fixture must exercise claims, leases, review transitions, stale reaping, and sync — the event types where replay is most likely to diverge.
