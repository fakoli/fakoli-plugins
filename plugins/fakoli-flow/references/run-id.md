# Canonical Run-ID Derivation

**Single source of truth** for how every fakoli-flow phase derives its run ID and scratch
root. `plan`, `execute`, and `verify` all reference this file — do not re-define the format
inline in a skill.

## Why this exists

A run ID names the scratch directory `.fakoli/runs/<run-id>/` that holds every agent's
status file for one phase. If two phases (or two projects, or a retry) resolve to the **same**
run ID, they share one directory and their `agent-<role>-status.md` files **silently
overwrite each other** — losing decisions, file lists, and verification evidence with no error.

A minute-granularity timestamp (`YYYYMMDDHHmm`) is not enough entropy: a `plan` and a
`verify` started in the same minute, or two quick retries, collide.

## Format

```
<run-id> = <prefix><basename>-<YYYYMMDDHHmmss>-<nonce>
```

- `<prefix>` — phase prefix: empty for `execute`, `plan-` for plan, `verify-` for verify
  (`verify-quick-` when verifying a quick session with no plan file).
- `<basename>` — the plan (or spec) filename without extension; omit for quick verify.
- `<YYYYMMDDHHmmss>` — UTC timestamp to **seconds** (not minutes).
- `<nonce>` — a 4-hex-character collision guard.

## How to derive it (copy-paste)

Run once, at the start of the phase, and reuse the captured value everywhere:

```bash
# seconds-granular UTC stamp + 4-hex nonce
STAMP=$(date -u +%Y%m%d%H%M%S)
NONCE=$(printf '%04x' $((RANDOM % 65536)))
# compose with the phase prefix + basename, e.g. for execute:
RUN_ID="${BASENAME}-${STAMP}-${NONCE}"
```

Examples:
- execute, plan `docs/plans/2026-06-01-retry-mechanism.md` at 14:30:07 UTC →
  `2026-06-01-retry-mechanism-20260601143007-3f1a`
- plan, spec `2026-06-01-retry.md` → `plan-2026-06-01-retry-20260601154512-a90c`
- verify (with plan) → `verify-2026-06-01-retry-mechanism-20260601154530-7b22`
- verify (quick, no plan) → `verify-quick-20260601154530-7b22`

## Invariant

The run ID is the **single source of truth** for all status-file paths in a phase. Log the
resolved absolute scratch root once, then derive every agent status path from it. Never
re-derive a second timestamp later in the same phase.
