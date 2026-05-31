# Critic false-pass baseline (SL-2)

**Roadmap item:** SL-1/SL-2 Wave 1, [`roadmap.md`](roadmap.md). _"You cannot improve
the critic until you can score it."_

This document records the **critic false-pass rate** — the fraction of known-bad
changes the critic incorrectly lets through. It is the number later critic work
is measured against. The harness and corpus are committed so the measurement is
reproducible.

## What "false pass" means

Every case in the corpus ([`../tests/fixtures/critic-faults/`](../tests/fixtures/critic-faults/))
is an obvious `MUST FIX` to a competent reviewer. A **false pass** is any case
the critic records as `PASS` or `SHOULD FIX` (or fails to review) — i.e. work it
would have let through to acceptance. A missing verdict counts as a false pass.

## Corpus (6 cases)

| Case | Fault category |
|------|----------------|
| `01-off-by-one` | Off-by-one slice — wrong window returned |
| `02-dropped-null-check` | Removed `None` guard — crashes on documented path |
| `03-assertion-free-test` | Test with no assertion — "passes" but verifies nothing |
| `04-deleted-assertion` | Key assertion deleted under "cleanup" |
| `05-missing-requirement` | 2 of 3 acceptance criteria implemented |
| `06-broken-contract` | Public return shape changed — breaks callers |

## Committed baseline

| | |
|---|---|
| **False-pass rate** | **0.0% (0 / 6)** |
| Date | 2026-05-31 |
| Critic under test | `agents/critic.md` rubric (fakoli-state fallback critic) |
| Dispatch method | one Opus-class agent per case, given `task.md` + `change.diff` only (never `EXPECTED.md`), prompted with the critic verdict rules; cases reviewed independently to avoid anchoring |
| Runs | single run (N=1 per case) |
| Result | all 6 cases → `MUST FIX` (caught) |

Per-case verdicts and the scorer output are reproduced by the procedure below.

### Caveats (read before citing this number)

- **It scores the rubric, not a fixed function.** The critic is an LLM agent;
  verdicts are non-deterministic. 0.0% on a single run means the rubric caught
  every obvious fault once — it is a floor-check, not a guarantee. Re-run
  periodically and watch for drift; widen the corpus before trusting a low rate.
- **The fallback rubric was measured here**, not `fakoli-crew:critic`. When
  fakoli-crew is installed, re-measure against it (it carries language-specific
  depth) and record a second row.
- **Six cases is a smoke-test corpus**, not a statistically robust sample. The
  faults are deliberately unambiguous; subtler faults (race conditions, partial
  spec drift, plausible-but-wrong logic) belong in a future expanded corpus and
  will produce a higher, more informative rate.

## How to reproduce

The harness cannot dispatch the critic itself — bash cannot spawn a Claude Code
subagent (the same constraint as `fakoli-crew/tests/test_critics.sh`). Run it
in an active Claude Code session:

1. **Enumerate the cases:**
   ```bash
   bash tests/critic_faultset/run.sh --list
   ```
2. **For each case**, dispatch the critic (`fakoli-state:critic`, or
   `fakoli-crew:critic` when installed) over `task.md` + `change.diff` for that
   case. Do **not** show it `EXPECTED.md` — that would bias the verdict.
3. **Record verdicts** in a TSV (`--template` prints a blank one):
   ```bash
   bash tests/critic_faultset/run.sh --template > results.tsv
   # fill in PASS / SHOULD FIX / MUST FIX per case
   ```
4. **Score:**
   ```bash
   bash tests/critic_faultset/run.sh --score results.tsv
   ```
   Exit 0 = every case scored; the printed `FALSE-PASS RATE` is the number to
   commit into the table above with a new date row.

## CI

A nightly / `workflow_dispatch` job can run this in-session via the Agent tool
and append a dated row, mirroring the secret-gated, green-on-missing-secret
pattern of `.github/workflows/fakoli-state-live-github.yml`. Until that lands,
the measurement is run manually and committed here on each critic change.
