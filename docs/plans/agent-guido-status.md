# Agent Status — guido (Task 3: generate.py + validate.py, test-first)

## Status

COMPLETE. Built test-first. 21 tests pass under `uv run`; both verbs run clean;
`validate.py` exits 0 against committed seed data + generated doc, and exits
non-zero with a clear message on every defined failure mode.

Verification command (all green):
```
cd plugins/fakoli-style \
  && uv run --with pytest --with jsonschema pytest tests/ \
  && uv run --script scripts/generate.py \
  && uv run --script scripts/validate.py
```
Result: `21 passed`; generate wrote the doc; validate printed
`OK: ledger and generated doc are valid and in sync`.

## Files Modified (all new; scope respected — only the four named paths)

- `plugins/fakoli-style/scripts/generate.py` — PEP 723 script. Projects
  `data/principles.json` → `docs/fakoli-style.md`. Public API used by tests:
  `load_ledger(path)`, `sort_principles(list)`, `render(ledger) -> str`,
  module constants `DATA_PATH` / `DOC_PATH`, `main(argv)`.
- `plugins/fakoli-style/scripts/validate.py` — PEP 723 script. Public API:
  `ValidationError`, `validate(*, data_path, schema_path, doc_path, repo_root)`,
  constants `DATA_PATH` / `SCHEMA_PATH` / `DOC_PATH` / `REPO_ROOT`, `main(argv)`.
- `plugins/fakoli-style/tests/conftest.py` — fixtures: `schema`, `good_ledger`
  (P1 proven / P2 asserted / P10 aspirational), `repo_root` (tmp tree with the
  proof+ref files), `mutate` (deep-copy + mutate helper). Adds `../scripts` to
  `sys.path`.
- `plugins/fakoli-style/tests/test_generate.py` — banner, ledger-table header,
  one-block-per-principle, aspirational graceful render (blank Embodied cell,
  no placeholder), ordering by risk→status, numeric-id tiebreaker (P2<P10),
  determinism, committed-doc-matches-committed-data.
- `plugins/fakoli-style/tests/test_validate.py` — passing baseline + committed
  seed/doc pass; one isolated test per failure mode: bad status (schema),
  bare-array-not-object (schema), nonexistent proof path, proven-proof-not-a-
  test-file, nonexistent embodied_in ref, proven missing embodied_in, duplicate
  ids, staleness; plus a guard that `open_work` prose is never scanned.
- `plugins/fakoli-style/docs/fakoli-style.md` — GENERATED. Do not hand-edit;
  it is locked by the staleness check. Regenerate via the command below.

## Decisions

- **Repo root resolution:** scripts resolve paths from `__file__`, not CWD.
  `REPO_ROOT = scripts/../../../..` (scripts → fakoli-style → plugins → repo
  root). `proof` and `embodied_in[].ref` are repo-relative (e.g.
  `plugins/fakoli-state/...`) and resolve against REPO_ROOT. All three live seed
  paths exist on disk and validate clean.
- **Versioned object, not bare array:** both scripts load `data["principles"]`.
  A bare-array ledger is rejected by the schema check (test covers it).
- **Aspirational rendering:** the at-a-glance "Embodied in" cell is empty and the
  detail block shows **Open work** only — no `N/A`/`TODO` placeholder. Tested.
- **Sort:** `credibility_risk` (high>med>low) → `status`
  (aspirational>asserted>proven) → numeric id (`int(id.lstrip("P"))`) so P2
  sorts before P10. Order is fully deterministic; staleness locks the doc to it.
  Committed order: P2,P3,P4,P7,P9 (high asp), P6,P8 (med asp), P5 (med asserted),
  P1 (med proven).
- **Proof checks:** only the substring before `::` is filesystem-checked.
  `open_work` prose is NEVER scanned for paths (explicit test). For `proven`,
  the proof must also look like a test file — by pytest conventions (a
  `test`/`tests` path segment, or `test_*` / `*_test` stem), NOT a loose "test"
  substring (which would misclassify names like `not_a_test.py`). For `asserted`
  the proof path must merely resolve (may be a doc, e.g. P5's roadmap.md).
- **Unique ids** (principle P4 applied to itself) enforced programmatically.
- **Staleness** re-renders in memory and byte-compares against the committed
  doc; any drift fails with a regenerate hint.
- **Out of scope (left for the finalization wave):** I did NOT bump
  `plugin.json` version or run `generate-index.sh` — scope was restricted to the
  four named paths. Whoever finalizes the plugin must do the standard
  "Existing/New Plugin Checklist" steps (version bump, registry regen, README).

## Notes for Specific Agents

### herald (next wave — SKILL.md authoring)
Document these exact, real invocations. Run from the plugin root
(`plugins/fakoli-style/`); both are PEP 723 standalone scripts (no venv setup):

- **generate verb** — projects the ledger into the doc:
  ```
  uv run --script scripts/generate.py
  ```
  Dry-run / CI staleness check (no write, non-zero on drift):
  ```
  uv run --script scripts/generate.py --check
  ```
- **validate verb** — governs the ledger + doc, non-zero on any violation:
  ```
  uv run --script scripts/validate.py
  ```
- **tests** (for the SKILL's "verify" note):
  ```
  uv run --with pytest --with jsonschema pytest tests/
  ```

The generated doc lives at **`plugins/fakoli-style/docs/fakoli-style.md`** and
carries an HTML-comment banner: `<!-- generated — do not hand-edit ... -->`.
SKILL.md should tell users to edit `data/principles.json` and regenerate, never
to edit the doc directly. Both scripts work regardless of CWD (paths resolve
from the script location), but the documented `scripts/...` relative form
assumes the plugin-root CWD.

### Whoever wires CI
`scripts/generate.py --check` and `scripts/validate.py` both exit non-zero with
a clear stderr message on failure — drop them straight into a CI step. Each
needs `uv` on PATH; dependencies (`jsonschema>=4.0`) are declared inline via
PEP 723, so `uv run --script` installs them automatically.

## Blockers

None.
