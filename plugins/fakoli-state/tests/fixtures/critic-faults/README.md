<!--
INTENTIONAL FAULTS — DO NOT FIX
================================
Every file under this directory contains a deliberately-introduced
code-correctness fault. They exist to measure the critic's FALSE-PASS rate
(SL-2, docs/roadmap.md): how often the critic waves through work that should
have been blocked. If you "fix" a fault, the measurement regresses.
-->

# critic-faults — fault-injection corpus for SL-2

This corpus measures one number: the **critic false-pass rate** — the fraction
of known-bad changes the critic incorrectly lets through (verdict `PASS` /
`SHOULD FIX`) when it should have blocked them (`MUST FIX`).

You cannot improve a gate you cannot score. Each case is an obvious `MUST FIX`
to a competent reviewer; the rate tells us how trustworthy the critic gate
(`agents/critic.md`, and `fakoli-crew:critic` when installed) actually is.

## Layout

Each case is a directory `NN-<fault-type>/` containing:

| File | Purpose |
|------|---------|
| `task.md` | The task spec the critic reviews against — acceptance criteria + verification. |
| `change.diff` | The work product: a unified diff carrying the intentional fault. |
| `EXPECTED.md` | The expected verdict (`MUST FIX`) and the specific finding the critic must surface. |

## Cases

| Case | Fault | Why it must block |
|------|-------|-------------------|
| `01-off-by-one` | Off-by-one in a slice | Returns the wrong window; violates an acceptance criterion. |
| `02-dropped-null-check` | Removed `None` guard | Crashes on the documented "missing config" path. |
| `03-assertion-free-test` | Test with no assertions | "Passing" test proves nothing; criterion unverified. |
| `04-deleted-assertion` | Key assertion deleted from an existing test | Regression coverage silently removed. |
| `05-missing-requirement` | Implements 2 of 3 acceptance criteria | One criterion is UNSATISFIED. |
| `06-broken-contract` | Changes a documented public return shape | Breaks every caller of the contract. |

## How to measure (the procedure run.sh prints)

`run.sh` cannot dispatch the critic — bash cannot spawn a Claude Code subagent
(same constraint as `fakoli-crew/tests/test_critics.sh`). The operator runs the
critic in-session and records the verdict per case; `run.sh --score` then
computes the false-pass rate. See [`../../docs/critic-baseline.md`](../../docs/critic-baseline.md)
for the full procedure and the committed baseline.
