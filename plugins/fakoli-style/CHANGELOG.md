# Changelog

All notable changes to fakoli-style are documented here.

## [1.2.0] - 2026-06-02

### Added
- Two principles surfaced by an external-taxonomy review (Google Cloud agentic-architecture guidance used as an independent pattern dictionary, not a design source):
  - **P12** (aspirational, high risk): untrusted external content is data, never instruction — Fakoli ingests web fetches and third-party PRD/spec text with no inspection boundary today; a poisoned input could be read as direction, undermining *Evidence over Claim*.
  - **P13** (asserted, med risk): bounded refinement with explicit escalation — names the iteration caps Fakoli already practices (critic fix cycle ≤ 3, welder/verify ≤ 2, 5-min poll timeout). Documented in the flow skills; `open_work` is to make the cap machine-enforced.
- Research resources under `docs/research/` (hand-authored, **not** part of the governed ledger): `agentic-patterns-glossary.md` (external pattern vocabulary) and `architecture-view.md` (maps each pattern to the Fakoli plugin that embodies it and the governing principle). Headline finding: eight load-bearing taxonomy concepts already had ledger principles (P2, P5, P6, P7, P8, P10, P11 + the P1 critic-gate discipline) — Fakoli converged on the same forces independently.

---

## [1.1.3] - 2026-06-01

### Changed
- Principle **P4** (prove invariants in CI) moves `aspirational → proven`: SL-1 landed a CI-enforced replay-equivalence test (`fakoli-state/tests/test_replay_equivalence.py`) backed by `serialize_state` and the new `fakoli-state.yml` workflow. `open_work` now tracks the latent poison-line replay-robustness follow-up surfaced during SL-1.

---

## [1.1.2] - 2026-06-01

### Added
- Principle **P11** (aspirational): derived indexes live outside the replay boundary. Model-derived or externally-sourced data (embeddings, vector indexes via `sqlite-vec`, semantic-graph caches) is a rebuildable projection kept out of canonical state and the event log, so deterministic replay is preserved. Parked from a design discussion; `open_work` points to the post-Wave-1 fakoli-state roadmap evaluation.

---

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
