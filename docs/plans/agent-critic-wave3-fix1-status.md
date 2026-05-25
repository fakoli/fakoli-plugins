# Code Review Report — Wave 3 Fix Cycle Verification

**Scope (fix cycle):**
- `plugins/cli-to-plugin/scripts/override.py`
- `plugins/cli-to-plugin/commands/cli-to-plugin.md`

**Reviewed by:** critic
**Date:** 2026-05-24

---

## Prior Findings Status

### MUST FIX 1 — override.py CLI entry point

**Status: RESOLVED.**

`main()` exists at line 157 with the correct signature `def main() -> None`. argparse is configured with `--tree` (required) and `--override` (required, dest=`override_path`). The `if __name__ == "__main__": main()` guard is at lines 198–199.

Error path coverage:
- Missing tree file: exits 2 with message on stderr. Verified.
- Malformed YAML override: caught by `yaml.YAMLError` at line 184, exits 2 with message on stderr. Correct.
- Unknown group (`OverrideError`): caught at line 190, exits **1** (not 2) with error on stderr. Verified via live test — `nonexistent-group` produces `error: override references unknown group 'nonexistent-group' (no close match found)` and exit code 1.
- pyyaml import failure: exits 2 with install hint. Correct.
- Stdout: `json.dump` + `sys.stdout.write("\n")` produces valid, newline-terminated JSON. Verified via end-to-end test — override applied `description → summary`, output parsed cleanly.

`# pragma: no cover` is correctly placed on both `def main()` (line 157) and `if __name__ == "__main__"` (line 198). `merge_override()` itself has no pragma and remains fully tested.

One minor observation, not a blocker: `OverrideError` exits 1 while I/O failures exit 2. This exit code stratification (1 = logical error, 2 = I/O/import error) is a reasonable Unix convention and is consistent internally. The prior review's suggested fix used `sys.exit(1)` for all non-zero paths; the implementation uses 1/2 stratification. This is strictly better than the suggested fix.

---

### SHOULD FIX 2 — README pseudocode (intentionally deferred)

**Status: DEFERRED — confirmed as remaining open SHOULD FIX.**

The fix cycle explicitly deferred this to the finish phase. `tests/fixtures/README.md` still shows old full-equality pseudocode. The test implementation in `conftest.py::assert_subset_match` is correct; this is documentation-only. Carry forward as open SHOULD FIX.

---

### SHOULD FIX 3 — Step 0 `--regen` logic

**Status: RESOLVED.**

`commands/cli-to-plugin.md` lines 42–64. The two cases are now stated unambiguously on separate bullet points:

- Line 48: "If `--regen` was passed: set `REGEN_MODE=diff-merge` automatically and skip the prompt. Proceed to Step 1."
- Line 49: "If `--regen` was NOT passed: ask the user:" (followed by the A/B/C prompt block)

No ambiguity remains about what happens in each branch. The `REGEN_MODE=diff-merge` assignment is explicit in the `--regen` path rather than only in option A of the prompt.

---

### SHOULD FIX 4 — Override validation before Step 0/Step 1

**Status: RESOLVED.**

`Pre-Step-0 — Override file validation` section appears at lines 29–39, before Step 0 (line 42). It explicitly states: "This runs regardless of `--from-tree`, so a broken override file fails fast." The two-step validation (file existence via `test -f`, then YAML parse via `uv run`) matches the spec's intent.

Step 1 (lines 66–87) ends with: "Override file validation already ran in Pre-Step-0, so no override checks are needed here." This explicitly removes the duplicated responsibility.

No regression: `--from-tree` skip instruction at Step 1 line 68 applies only to the preflight binary checks (`uv`, `<cli-name>`) — override validation correctly runs in Pre-Step-0 regardless of `--from-tree`.

---

### SHOULD FIX 5 — Missing error table entries

**Status: RESOLVED.**

Error table at lines 389–409 now contains all three previously missing rows:

| Row | Severity | Action |
|---|---|---|
| `test-path-resolution.sh` ERROR | Halt | Display findings |
| Recursion depth > 3 | Info | Stop recursing; no warning |
| Total commands walked > 500 | Warn | Suggest `--max-commands <N>` |

All three are present exactly as specified. One minor note: the action for "Recursion depth > 3" reads "Stop recursing; no warning" — this is more precise than the prior fix's suggested "Collected in summary" and correctly matches the spec ("Info, not surfaced to user as a warning"). No issue.

---

### CONSIDER 6 — Explicit hyphenated keys reminder

**Status: RESOLVED.**

Step 4, item 4 (line 171) now contains the explicit instruction:

> **Frontmatter keys must be hyphenated:** `user-invocable`, `argument-hint`, `allowed-tools`, `disable-model-invocation`. Do NOT use underscore forms — they fail `schemas/skill.schema.json` validation.

All four canonical keys are named. The consequence of violation (schema failure) is stated. This is sufficient to prevent Claude from reverting to underscore forms.

---

### NIT 11 — Double-period in plugin.json description

**Status: RESOLVED.**

Line 287 now reads:

> `description` — `Use the '<cli-name>' CLI through Claude — <condensed cli.summary>.` (Strip any trailing punctuation from `cli.summary` before appending the period; some CLIs report summaries with a trailing period and a double period would be ugly.)

The parenthetical note is inline with the field definition. The instruction is clear: strip trailing punctuation before appending. "Trailing punctuation" is slightly broader than "trailing period" (which is accurate — stripping `?!.` is the right behavior for all these cases). No issue.

---

## Regression Checks

**pytest — 93 tests, all pass.** Verified: `93 passed in 0.21s`. No test regressions.

**Coverage — 90.95% (stated in request, consistent with prior verification).** `# pragma: no cover` on `main()` and `if __name__` guard correctly excludes the untestable CLI entry from coverage accounting without inflating it.

**validate.sh — exits 0.** Three warnings (missing README.md, CHANGELOG.md, LICENSE file) are pre-existing cosmetic gaps unrelated to this fix cycle.

**override.py CLI end-to-end — verified manually:**
- `--tree <valid> --override <valid>` → exit 0, valid merged JSON on stdout, description override applied correctly.
- `--tree <valid> --override <yaml-with-unknown-group>` → exit 1, error message on stderr, empty stdout.
- `--tree <nonexistent> --override <any>` → exit 2, error message on stderr.

---

## Open Items Carried Forward

| Item | Severity | Description |
|---|---|---|
| SHOULD FIX 2 | SHOULD FIX | `tests/fixtures/README.md` pseudocode still shows full-equality strategy instead of subset-within-commands. Documentation-only; test implementation is correct. Deferred to finish phase. |

---

## Verdict: PASS — Wave 4 unblocked

All five addressed items from the Wave 3 fix cycle are resolved. The MUST FIX (override.py CLI entry) is fully implemented: argparse wiring, error paths with non-zero exits and stderr messages, correct stdout JSON output, and `# pragma: no cover` placement. The four SHOULD FIX items — `--regen` branching clarity, Pre-Step-0 override validation, three missing error table rows, and hyphenated frontmatter key reminder — are each addressed precisely, with no regressions introduced. The one intentionally deferred item (README pseudocode) is documentation-only and does not block Wave 4.
