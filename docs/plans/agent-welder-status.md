# agent-welder-status

**Date:** 2026-05-31
**Task:** Harden fakoli-style validator for Wave 2 critic-gate correctness findings.
**Status:** COMPLETE

## Files Modified

- `plugins/fakoli-style/scripts/validate.py`
- `plugins/fakoli-style/scripts/generate.py`
- `plugins/fakoli-style/tests/test_validate.py`
- `plugins/fakoli-style/tests/conftest.py`
- `plugins/fakoli-style/.claude-plugin/plugin.json` (version bump 1.0.0 -> 1.1.0)
- `registry/index.json` (regenerated)

## Decisions

**Total tests: 31** (was 21, added 10).

New failure modes covered by the 10 new tests:

1. `test_staleness_crlf_does_not_false_positive` — CRLF-only difference must PASS (Fix 1 regression guard)
2. `test_staleness_trailing_whitespace_does_not_false_positive` — trailing spaces and extra blank lines must PASS (Fix 1 regression guard)
3. `test_staleness_real_content_change_still_fails` — genuine content change must still FAIL after normalization is applied (Fix 1 correctness guard)
4. `test_proof_symbol_missing_class_fails` — proof pointer with nonexistent class must FAIL with "symbol|MissingClass" in message (Fix 2)
5. `test_proof_symbol_missing_method_fails` — proof pointer with real class but renamed method must FAIL (Fix 2)
6. `test_proof_symbol_both_present_passes` — proof pointer with both class and method present must PASS (Fix 2 green path)
7. `test_committed_p1_proof_symbols_pass` — confirms the real committed P1 proof (TestEvidenceGateDelegation::test_transition_gate_agrees_with_review_gate) passes symbol check on disk (Fix 2 integration test)
8. `test_embodiment_guard_raises_without_schema` — calls _check_proof_and_embodiment directly, bypassing schema, asserts it raises with "embodied_in" in the message (Fix 3)
9. `test_numeric_id_p10_sorts_after_p2` — confirms P10 sorts after P2 with equal risk/status (Fix 4)
10. `test_numeric_id_pppp10_not_misread` — confirms id[1:] raises on a multi-P prefix; lstrip("P") would have silently succeeded (Fix 4 regression guard)

**Fix 1 (staleness normalization):** `generate.normalize_for_comparison` added as a public helper — converts CRLF/CR to LF, rstrips each line, collapses trailing blank lines to a single trailing newline. Applied symmetrically in `_check_staleness` (validate.py) and in `--check` mode (generate.py). The committed doc is unaffected: `git diff --stat plugins/fakoli-style/docs/fakoli-style.md` shows no diff.

**Fix 2 (symbol verification):** `_proof_symbols` and `_check_proof_symbols` added to validate.py. After confirming the proof file exists, each `::symbol` segment is checked for `def <sym>` or `class <sym>` in the file text. The committed P1 proof (TestEvidenceGateDelegation::test_transition_gate_agrees_with_review_gate) passes because both symbols exist in the real test file.

**Fix 3 (embodied_in guard test):** Guard kept as defense-in-depth. New test calls `_check_proof_and_embodiment` directly (bypassing schema) and asserts it raises with "embodied_in" in the message.

**Fix 4 (lstrip nit):** `int(entry["id"].lstrip("P"))` replaced with `int(entry["id"][1:])`. Behavior identical for schema-valid ids; malformed ids now raise ValueError instead of silently returning a wrong value.

**conftest.py change:** `repo_root` fixture updated to write real class+method content to `test_proven.py` (was `# test\n`). Required so the new symbol check passes on the baseline fixture.

## Blockers

None.
