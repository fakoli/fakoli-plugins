# Overnight Roadmap Run — Progress Log

**Branch:** `roadmap/p0-hardening` (isolated worktree off `origin/main` @ `b69cd38`)
**Started:** 2026-06-02, autonomous run while user sleeps
**Rule:** commit locally, do NOT push. No destructive actions. Keep only test-green code.

## Baseline
- fakoli-state test suite: **1250 passed** (4 prior failures were the optional `openai` SDK
  not installed; installed it → green). This is the trusted baseline.

## Task ledger
| # | Task | Status |
|---|------|--------|
| A | Write hardening spec/PRD | in progress |
| B1 | flow: run-id collision fix (P0#1) | todo |
| B2 | flow: BLOCKED/NEEDS_REVIEW timeout (P1#6) | todo |
| B3 | flow: verify→finish coupling (P1#5) | todo |
| B4 | flow: plan pre-flight validation (P1#7) | todo |
| C1 | crew: status-file instr in critic.md + welder.md (P2) | todo |
| D1 | state: torn-line bounded window (P0#4) | todo |
| D2 | state: audit-write error surfacing (P1#9) | todo |
| D3 | state: schema migration transaction (P0#2) | todo |
| D4 | state: claim UNIQUE(id,task_id) (P0#3) | todo |
| D5 | state: evidence file-scope validation (P1#8) | todo |
| E | NotebookLM: add roadmap note | todo |
| F | Morning summary | todo |

## Log
- Set up worktree, synced uv env, ran baseline (green). Created deliverables dir.
