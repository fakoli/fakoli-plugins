# Worked example: anvil-serving issue #377

Generated from anvil-serving GitHub issue #377, `[sonnet][feature 12] Run
lint + rollback-check as implicit gates in promote and mode enter`. That
issue was itself written for this packet format, so any drift between it
and the rendering below is a real signal about the template, not noise.

Every anchor below was grep-verified against a real anvil-serving checkout
on 2026-08-08. Three of the issue's own breadcrumbs did not survive
verification — a stale line number, a function name that does not exist,
and a re-verify grep that matches nothing. The corrections are shown
inline in the Wiring section: the issue's claim, the reality, and the grep
or read that establishes it. Verification also surfaced a genuine
contradiction between the issue's design and the code it targets; that is
marked `OPEN-DECISION` rather than resolved, per the skill's rule that the
generator does not choose for the requester.

Line numbers are true as of 2026-08-08 against anvil-serving `main`. A
regenerated packet re-greps rather than trusting this copy — `serves.py`
moves.

---

```markdown
# Dispatch packet: Run lint + rollback-check as implicit gates in promote and mode enter
WORKING DIRECTORY: <anvil-serving worktree path>   BRANCH: <feature branch> (checked out — do NOT switch/commit/push)
Begin editing within ~5 tool calls; the pointers below are sufficient.

## Why
`serves promote` and `serves mode enter` can currently complete a
transaction against a manifest set that would fail lint or rollback-check —
the checks exist standalone but aren't wired as preconditions. Source:
anvil-serving `docs/FEATURE-EXECUTION-PLAYBOOK.md` (recipe A, gates) and
`docs/PRODUCT-DISCOVERY-PERSONAS.md` §3; mirrors the gate-wiring shape of
the two mirror precedent PRs, #364 and #368.

## Decided design
1. `serves promote` and `serves mode enter` run `lint_manifest_set` +
   `rollback_check_manifest_set` BEFORE beginning their transaction.
2. Any error-severity finding aborts with the findings printed and exit
   code 3, before any mutation.
3. `--skip-preflight-checks` (exact flag name) overrides both checks,
   logged loudly when used.
4. Dry-run paths run the checks too — they are read-only, so there's no
   cost to skipping them.
5. The rollback-check's restore-group = the transaction's own
   `--restore-group` when the caller supplied one.
6. `OPEN-DECISION` — issue #377 states "both already load the manifest set
   + promotions — pass them through, do NOT re-load." Verification shows
   this is false for `mode enter`: `mode` loads the full manifest set
   (`serves.py:4739`) but loads no promotions at all — no `load_promotions`
   call anywhere in the mode dispatch block (`serves.py:4805-4842`), and
   `cmd_mode`'s signature (`serves.py:3740-3756`) takes no `promotions`
   parameter. `rollback_check_manifest_set` requires a `promotions`
   argument (`serves.py:2592`). So `mode enter` must do one of: (a) load
   promotions itself before calling `rollback_check_manifest_set` —
   contradicting the issue's "do NOT re-load" — or (b) run only
   `lint_manifest_set` as a precondition and skip the rollback-check gate
   for `mode enter` — contradicting decision 1's "run lint +
   rollback-check ... in ... mode enter". The issue does not say which.
   Do NOT pick one. Stop here and flag this contradiction back to the
   issue author before wiring `mode enter`'s gate; everything else in this
   packet is closed and can proceed.

## Wiring (mirror PRs #364 and #368; anchors grep-verified 2026-08-08)

Promote dispatch:
- CORRECTION — issue claimed `serves.py:4640` for the promote dispatch
  site. Reality: line 4640 is `a.action = action`, a post-parse assignment
  inside `main()` (`main()` starts at `serves.py:4614`). The real promote
  branch is `serves.py:4663`: `    elif a.action == "promote":`. The
  handler call site is `serves.py:4921`: `    if a.action == "promote":`
  (calls `cmd_promote(...)`, 4921-4930).
- `lint_manifest_set` — `serves.py:2454`:
  `def lint_manifest_set(serves, _run=subprocess.run):`
- `rollback_check_manifest_set` — `serves.py:2592`:
  `def rollback_check_manifest_set(serves, promotions, restore_group=None, _run=subprocess.run):`
  (name matches the issue exactly; note the required `promotions`
  argument — this is why decision 6 is open).
- `_promotion_transition` — `serves.py:1125`:
  `def _promotion_transition(serves, plan, manifest_path, *, rollback=False,`
  (a distinct `_promotion_transition_cli` exists at `serves.py:1007` — do
  not confuse the two; tests monkeypatch the former, see Tests).

Mode-enter dispatch:
- CORRECTION — issue named `_load_mode_plan` as the mode-enter
  plan/validation entry point. Reality: NOT FOUND — no such symbol exists
  in `serves.py`. The real mode-plan builder is `operating_mode_plan`,
  called at `serves.py:3773`:
  `plan = operating_mode_plan(serves, target_name, restore_group, state_of)`.
- `cmd_mode` — `serves.py:3740`: `def cmd_mode(`
- CORRECTION — issue's suggested re-verify grep, `mode_action == "enter"`,
  does not appear anywhere in `serves.py`. The real enter checks are
  membership tests on `a.mode_action`: `serves.py:4667`:
  `    elif a.action == "mode" and a.mode_action in {"enter", "leave"}:`
  and `serves.py:4819`:
  `    if a.preserve_on_failure and a.mode_action != "enter":`

Load sites (why decision 6 is open, not closed):
- `use_set` is computed at `serves.py:4730`:
  `use_set = bool(a.groups) or a.action in {"groups", "lint", "rollback-check", "mode", "up-for"}`
  — note `"promote"` is NOT a member.
- `mode` IS in `use_set`: its `serves` is the full manifest set, loaded at
  `serves.py:4739` via `load_manifest_set(manifest_path, reject_duplicates=not lenient)`.
  But mode never loads promotions.
- `promote`'s `serves` comes from plain `load_manifest(manifest_path)`
  (~`serves.py:4738-4741`), not the manifest set; the manifest set loads
  separately as `ledger_serves` at `serves.py:4759`:
  `ledger_serves = serves if use_set else load_manifest_set(manifest_path)`.
  Promotions load at `serves.py:4923`: `promotions = load_promotions(manifest_path)`.
  Promote already has both objects in hand before its checks would run —
  pass them through, do not re-load. This half of the issue's claim holds.

New-flag check:
- `--skip-preflight-checks` (decision 3) — grepped case-insensitively
  across the whole repo: NOT FOUND. The flag does not exist yet; this task
  introduces it from scratch, not extends an existing one.

## Boundaries
- Detection (`lint_manifest_set`, `rollback_check_manifest_set`) stays
  available as standalone commands — this task only adds them as
  preconditions on the two existing entry points. No new checks, no new
  check logic.
- Do not touch unrelated `serves.py` command handlers — they belong to
  other features; editing one ships an unreviewed behavior change under
  this task's PR.
- No `git commit`, `git push`, `git checkout`, or branch creation — the
  orchestrator owns git.

## Tests
- Promote tests live in `tests/test_serves.py`. The injectable-runner seam
  is `_inspect_returning`, `tests/test_serves.py:44` — a fake `_run`
  helper; copy its pattern rather than shelling out. Promote tests
  commonly monkeypatch the transition function directly, e.g.
  `tests/test_serves.py:1873`:
  `monkeypatch.setattr(serves, "_promotion_transition", transition)`.
  First existing promote test: `tests/test_serves.py:1844` — read it for
  the fixture shape before adding a new one.
- Mode tests live in `tests/test_serves_manage.py`. The fake-docker helper
  is `cmd_mode_with_fake_docker`, `tests/test_serves_manage.py:517`.
- Neither test file defines a `class _Result` helper — grep-checked. Use
  the fakes named above; do not invent a new result-object shape.
- Assert a manifest set with a duplicate name, or a manifest missing its
  rollback image, aborts `promote` before `_promotion_transition` is
  reached — inject the finding and assert the transition function's call
  count is zero.
- Same assertion shape for `mode enter`, once decision 6 is resolved by
  the issue author — do not write this case against a guessed resolution.
- CLI-level test asserting exit code 3 on an aborting finding.
- Tests must fail against a build that skips the new precondition call.

## Verify
```
cd <anvil-serving worktree>
python -m pytest tests/ -q
python -m ruff check anvil_serving tests
git add -A
python scripts/audit_cli_references.py --update --scope docs
```
Full suite, not a `-k` filter (`docs/FEATURE-EXECUTION-PLAYBOOK.md:12`):
a filtered run passes while a gate wired into a shared code path breaks
promote/mode tests elsewhere in the file.
`git add -A` runs BEFORE the audit — it is `git ls-files`-based, so an
unstaged new file is invisible and the inventory reads stale. Paste the
pytest and audit tails in the report, not a summary.

## [operator]
Live fleet validation — an actual `serves promote` / `serves mode enter`
run against a real manifest set on the reference GPU host, to confirm the
abort message and exit code in practice. Produce the exact commands; do not
run them from this packet. (Host names, addresses, and credentials are
operator state — never embed them in a packet.)

## Report back
Files changed (path + line count), which of the two entry points needed
the manifest-set pass-through vs a re-load and why (see the load-sites
evidence above), how decision 6 was resolved once the issue author
answers, verify-command tails verbatim, and anything found outside this
diff's scope — reported, not fixed here.
```
