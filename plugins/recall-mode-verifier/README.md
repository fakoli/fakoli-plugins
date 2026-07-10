# recall-mode-verifier

Verify a change from an **independent model of what must not break** — not from
its own spec or tests (which encode the implementer's blind spots). The focused,
spec-independent specialization of ship-loop's review angles, shaped as a
**skill** so both Claude Code and Codex can invoke it, and so `anvil execute`
can run it as its verify-left stage cross-repo.

## The four axes

1. **Fail-closed** — when safety state can't be read, does it refuse or fail open?
2. **Malformed input** — empty/null/wrong-type/boundary/adversarial-metachar/encoding.
3. **Resource exhaustion** — unbounded retries, growth, missing timeouts.
4. **State drift** — TOCTOU, stale bases/claims/sessions, cross-process seams.

Reports CONFIRMED / PLAUSIBLE findings ranked by severity; **does not fix**.

## Use

`/recall-verify` in Claude Code, or invoke the `recall-mode-verifier` skill
(Codex / anvil execute). Composes with `ship-loop` step 5 and `gate-router`.

## License

MIT
