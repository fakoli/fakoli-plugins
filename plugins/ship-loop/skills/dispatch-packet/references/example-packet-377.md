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
recorded under `## Open decisions (BLOCKING)` rather than resolved, per
the skill's rule that the generator does not choose for the requester.

Line numbers are true as of 2026-08-08 against anvil-serving `main`. A
regenerated packet re-greps rather than trusting this copy — `serves.py`
moves.

The `<anvil-serving worktree path>` and `<feature branch>` placeholders
below are deliberate: this is a public-repo reference, and a live packet
fills them in literally. Host names, addresses, and paths are operator
state that never ship in a public example.

---

````markdown
# Dispatch packet: Run lint + rollback-check as implicit gates in promote and mode enter
WORKING DIRECTORY: <anvil-serving worktree path>   BRANCH: <feature branch> (checked out — do NOT switch/commit/push)
MODEL TIER: sonnet — anchored mechanics with grep-verified anchors and two mirror PRs; no design tension left open once the blocking item below is answered.
STATUS: BLOCKED — do not dispatch until the item below is answered
Begin editing within ~5 tool calls; the pointers below are sufficient.
If blocked for more than ~5 tool calls on open-ended reading, STOP and report the blocker — do not keep searching.

## Context reads (in order; playbook/spec first, then precedent PRs)
1. `docs/FEATURE-EXECUTION-PLAYBOOK.md` — recipe A and the gate sequence.
2. `docs/PRODUCT-DISCOVERY-PERSONAS.md` §3.
3. Mirror PR #364.
4. Mirror PR #368.

## Why
`serves promote` and `serves mode enter` can currently complete a
transaction against a manifest set that would fail lint or
rollback-check — the checks exist standalone but aren't wired as
preconditions on the two entry points that actually mutate state.

## Open decisions (BLOCKING)
Issue #377 states "both already load the manifest set + promotions — pass
them through, do NOT re-load." That premise is false for `mode enter`:
`load_promotions(` appears in `serves.py` at line 717 (definition), 4776
(rollback-check), 4923 (promote), and 4938 (switch) — never inside the
mode dispatch block, `serves.py:4805-4842` (grep-checked: no
`load_promotions` call in that span). `cmd_mode`'s signature,
`serves.py:3740-3756`, takes no `promotions` parameter, and
`rollback_check_manifest_set` requires one (`serves.py:2592`). So loading
promotions in `mode enter` would be a FIRST load, not a re-load — the
issue's "do NOT re-load" instruction does not apply to it; only the
issue's false premise that mode already loads them does. One confirmation
is needed from the issue author: should `mode enter` load promotions
itself (a first load, consistent with decision 1's intent to gate both
entry points on both checks), or should `mode enter` gate on
`lint_manifest_set` only and skip the rollback-check gate? Do not pick —
this packet does not dispatch until the author answers.

## Decided design
1. `serves promote` and `serves mode enter` run `lint_manifest_set` +
   `rollback_check_manifest_set` BEFORE beginning their transaction.
2. Any error-severity finding aborts with the findings printed and exit
   code 3, before any mutation.
3. `--skip-preflight-checks` (exact flag name) overrides both checks,
   logged loudly when used.
4. Dry-run paths run the checks too — they are read-only, so there's no
   cost to running them.
5. The rollback-check's restore-group = the transaction's own
   `--restore-group` when the caller supplied one.

## Wiring (mirror PRs #364 and #368; anchors grep-verified 2026-08-08)

### Mirror PRs — the edit set to copy
- PR #364 touched: `anvil_serving/serves.py`,
  `anvil_serving/commands/serves.py`, `anvil_serving/deploy.py`,
  `docs/CLI-COMMAND-MANIFEST.json`, `docs/CLI-REFERENCE-AUDIT.json`,
  `CHANGELOG.md`, `anvil_serving/__init__.py`, plus scaffold templates.
- PR #368 touched: `anvil_serving/serves.py`,
  `anvil_serving/commands/serves.py`, `docs/CLI-COMMAND-MANIFEST.json`,
  `docs/CLI-REFERENCE-AUDIT.json`, `docs/CLI.md`, `docs/cli/serves.md`,
  `docs/PRODUCT-DISCOVERY-PERSONAS.md`, `mkdocs.yml`, `CHANGELOG.md`,
  `anvil_serving/__init__.py`, `pyproject.toml`,
  `tests/test_serves_rollback_check.py`.
- Consequence: the new `--skip-preflight-checks` flag (decision 3) must
  be declared in `anvil_serving/commands/serves.py` as well as wired in
  `anvil_serving/serves.py` — the sibling `--restore-group` option is
  declared at `anvil_serving/commands/serves.py:158` and `:181`. Omitting
  the `commands/serves.py` edit makes this packet's own
  `audit_cli_references.py` verify step report manifest drift with no
  anchor pointing at the fix.

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
  argument — this is why the open decision above exists).
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

Load sites (why the open decision above applies only to `mode enter`):
- `use_set` is computed at `serves.py:4730`:
  `use_set = bool(a.groups) or a.action in {"groups", "lint", "rollback-check", "mode", "up-for"}`
  — note `"promote"` is NOT a member.
- `mode` IS in `use_set`: its `serves` is the full manifest set, loaded at
  `serves.py:4739` via `load_manifest_set(manifest_path, reject_duplicates=not lenient)`.
  But mode never loads promotions.
- `promote`'s `serves` comes from `serves.py:4738-4741`, the expression
  `serves = load_manifest_set(...) if use_set else load_manifest(...)`
  (grep-verified) — since `"promote"` is not in `use_set`, this evaluates
  the `load_manifest(...)` branch; the manifest set for promote's own
  checks arrives separately as `ledger_serves` at `serves.py:4759`:
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
- `tests/test_serves.py` and `tests/test_serves_manage.py` do not define
  a `class _Result` helper — grep-checked; use `_inspect_returning` and
  `cmd_mode_with_fake_docker` as named above for those two files. For the
  rollback-check gate itself, this task's canonical `_Result` fake is
  `tests/test_serves_rollback_check.py:84`, `class _Result:` — copy that
  pattern (`docs/FEATURE-EXECUTION-PLAYBOOK.md:105-107`: "Inject
  `_run=subprocess.run` and fake it ... Copy the `_Result` / fake-runner
  helpers from `tests/test_serves_rollback_check.py` or
  `tests/test_fleet_drift.py`."). Do not invent a new result-object shape.
- Assert a manifest set with a duplicate name, or a manifest missing its
  rollback image, aborts `promote` before `_promotion_transition` is
  reached — inject the finding and assert the transition function's call
  count is zero.
- Same assertion shape for `mode enter`, once the open decision above is
  resolved by the issue author — do not write this case against a guessed
  resolution.
- CLI-level test asserting exit code 3 on an aborting finding.
- Tests must fail against a build that skips the new precondition call.

## Verify
```
cd <anvil-serving worktree>
python -m pytest tests/ -q
```
Full suite, not a `-k` filter (`docs/FEATURE-EXECUTION-PLAYBOOK.md:12` —
"`python -m pytest tests/ -q` fully green (see *known local failures*
below)"): a filtered run passes while a gate wired into a shared code
path breaks promote/mode tests elsewhere in the file. Known local
failure: `test_cli.py::test_top_level_version_reports_installed_version`
fails whenever the source version is bumped, because the editable
install's metadata goes stale — that is environment drift, not your
change; the playbook explicitly says never to "fix" it by reinstalling
from a scratch worktree. (This repo runs tests under plain
`pytest`/`python -m pytest`, not `uv run pytest` — `uv run` is wrong for
this repo.)

Mutation check, by hand: comment out the new
`lint_manifest_set`/`rollback_check_manifest_set` precondition call in
`serves.py`, re-run `python -m pytest tests/ -q -k "promote or mode"` and
confirm the new tests fail against the gate's own assertions (not an
unrelated pre-existing failure), then restore the call and confirm the
same tests pass again.

```
python -m ruff check anvil_serving tests
python -m mkdocs build --strict
git add -A
python scripts/audit_cli_references.py --update --scope docs
```
`git add -A` runs BEFORE the audit — it is `git ls-files`-based, so an
unstaged new file is invisible and the inventory reads stale.

CHANGELOG entry plus a version bump in BOTH `pyproject.toml` and
`anvil_serving/__init__.py` — they drift if only one is bumped.

Paste the pytest, mutation-check, ruff, mkdocs, and audit tails in the
report, not a summary.

## [operator]
Live fleet validation — an actual `serves promote` / `serves mode enter`
run against a real manifest set on the reference GPU host, to confirm the
abort message and exit code in practice. Produce the exact commands; do not
run them from this packet. (Host names, addresses, and credentials are
operator state — never embed them in a packet.)

## Report back
Files changed (path + line count), how the open decision above was
resolved once the issue author answers, verify-command tails verbatim,
and anything found outside this diff's scope — reported, not fixed here.
````
