# Changelog

All notable changes to fakoli-style are documented here.

## [1.1.1] - 2026-06-01

### Added
- CI enforcement: `.github/workflows/fakoli-style.yml` runs the ledger validator (`scripts/validate.py`) and the pytest suite on every change to `plugins/fakoli-style/**`. The schema, lifecycle, and doc-staleness invariants are now proven in CI rather than only locally runnable — the plugin obeying its own P1 (advisory and enforcing share one code path) and P4 (prove invariants in CI).

---

## [1.1.0] - 2026-06-01

### Added
- Principle P10 (proven): tool scratch lives outside version control. Proven by `tests/test-scratch-not-tracked.sh`; embodied in the root `.gitignore` and `fakoli-flow/references/status-protocol.md`.

---

## [1.0.0] - 2026-05-31

Initial release.

- `data/principles.json`: versioned ledger of Fakoli operating-model principles with `proven`, `asserted`, and `aspirational` lifecycle statuses.
- `schema/principles.schema.json`: JSON Schema (draft-07) governing the ledger shape and lifecycle rules.
- `scripts/generate.py`: deterministic projection of the ledger into `docs/fakoli-style.md`; supports `--check` mode for staleness detection.
- `scripts/validate.py`: full validation: schema, duplicate IDs, proof-path existence, proven-requires-test enforcement, embodiment-path existence, and staleness diff.
- `skills/style-ops/SKILL.md`: skill definition documenting the four management verbs: add, set-status, validate, report.
- Nine principles recorded across three statuses: one proven (P1), one asserted (P5), seven aspirational (P2, P3, P4, P6, P7, P8, P9).
