# fakoli-style Plugin — Execution Plan

**Goal:** Build a `fakoli-style` meta-plugin that catalogs the Fakoli Style operating-model principles as a governed JSON ledger with a generated markdown projection and a validator that enforces a proven/asserted/aspirational lifecycle.
**Spec:** Approved design in session (3 sections: artifact+status model, plugin architecture, seed principles+scope). No separate spec file by user choice.
**Language:** Python (plugin scripts via `uv run --script`, PEP 723 inline metadata). Repo root is language-agnostic.
**Crew:** fakoli-crew v2.0.0 (8 agents)

**Scout findings:** `docs/plans/agent-scout-status.md` (COMPLETE). PEP 723 inline scripts confirmed; `data/`/`schema/`/`scripts/` invisible to validators; proof pointer + SL-ids verified; category `utilities`; marketplace uses `source`.

**Pre-execution:** Create a feature branch off `main` (e.g. `feat/fakoli-style-plugin`) before any file writes.

---

### Task 1: Scaffold the fakoli-style plugin structure and manifest

**Intent:** Establish the plugin skeleton and a schema-valid manifest, consulting the `plugin-dev:create-plugin` workflow for structure.
**Acceptance criteria:**
- `plugins/fakoli-style/.claude-plugin/plugin.json` exists, declares `name` `fakoli-style` and `version` `1.0.0`, and passes `./scripts/validate.sh plugins/fakoli-style` with no ERRORs (README/CHANGELOG warnings acceptable at this stage).
- The manifest declares NO auto-discovered component paths (no `skills`/`commands`/`agents`/`hooks` fields) and contains no `$schema` key.
- Empty component directory `plugins/fakoli-style/skills/style-ops/` exists for later authoring.
- A `LICENSE` file (MIT, matching repo convention) exists at the plugin root.
**Scope:** plugins/fakoli-style/.claude-plugin/plugin.json, plugins/fakoli-style/LICENSE
**Agent:** smith
**Verify:** `./scripts/validate.sh plugins/fakoli-style` (exit 0, no ERROR lines)
**Depends on:** (none)

---

### Task 2: Define the principles ledger data model and JSON Schema

**Intent:** Create the canonical principles ledger and the schema that governs its shape, seeded with the nine operating-model principles at their honest current statuses.
**Acceptance criteria:**
- `schema/principles.schema.json` is a valid JSON Schema requiring per-entry fields `id`, `name`, `principle`, `why`, `status`, `credibility_risk`; constrains `status` to `{proven, asserted, aspirational}` and `credibility_risk` to `{high, med, low}`; and conditionally requires `proof` when status is `proven` or `asserted`, `open_work` when status is `aspirational`, and a non-empty `embodied_in` array when status is `proven` or `asserted`.
- `data/principles.json` validates against that schema and contains exactly the nine seed entries in the Prescriptive Detail below, with the stated statuses, proof pointers, and `open_work` values.
- Every `proof` file path (the substring before `::`, if any) and every `embodied_in[].ref` in the seed data resolves to an existing file in the repo.
- The data file is sortable by `credibility_risk` then status without ambiguity (every entry has both fields).
**Scope:** plugins/fakoli-style/data/principles.json, plugins/fakoli-style/schema/principles.schema.json
**Agent:** guido
**Verify:** `uv run --with jsonschema python -c "import json,jsonschema; jsonschema.validate(json.load(open('plugins/fakoli-style/data/principles.json')), json.load(open('plugins/fakoli-style/schema/principles.schema.json')))"`
**Depends on:** (none)

**Prescriptive detail (seed ledger — exact statuses/pointers are facts, not to be invented):**

| id | name | status | proof / open_work | credibility_risk |
|----|------|--------|-------------------|------------------|
| P1 | Advisory and enforcing share one code path | proven | proof: `plugins/fakoli-state/tests/test_transitions.py::TestEvidenceGateDelegation::test_transition_gate_agrees_with_review_gate`; embodied_in: fakoli-state `transitions._evidence_complete` delegates to `review.gates.evidence_complete`; open_work: extend the agreement-test pattern to fakoli-flow's preview/enforce paths | med |
| P2 | Verifiable proof beats pattern-matching | aspirational | open_work: SL-3 (typed `ProofArtifact` evidence replacing the substring gate) | high |
| P3 | Measure your own gates (false-pass rate) | aspirational | open_work: SL-2 (fault-injection harness + committed baseline) | high |
| P4 | Prove invariants in CI, don't assert them | aspirational | open_work: SL-1 (replay equivalence check in CI) | high |
| P5 | Sequence by credibility risk, not demonstrability | asserted | proof (code/doc location): `plugins/fakoli-state/docs/roadmap.md` (integrity-first track); open_work: encode the ordering as an automated check | med |
| P6 | Close the loop on failure, not just success | aspirational | open_work: make a failed wave a first-class learnable event (substrate: events.jsonl) | med |
| P7 | Coordinate through canonical state, not status files | aspirational | open_work: SL-4 (promote status-file coordination to canonical Events) | high |
| P8 | Conflicts live at the contract level, not the file level | aspirational | open_work: SL-5 (`OutputContract` + post-apply drift check) | med |
| P9 | Score spec assumptions, not just tasks | aspirational | open_work: SL-6 (score assumptions by blast_radius × uncertainty) | high |

For each entry also include a one-sentence `principle` statement and a one-sentence `why` (the failure it prevents), drawn from the approved design. `embodied_in` is required only for P1 and P5; omit or leave empty for aspirational entries.

---

### Task 3: Build the generate and validate scripts, test-first

**Intent:** Implement the projection generator and the governing validator as PEP 723 inline-metadata Python scripts, with tests written before the implementation.
**Acceptance criteria:**
- `scripts/generate.py` reads `data/principles.json` and writes `docs/fakoli-style.md` containing a preamble, an at-a-glance ledger table (`ID | Principle | Status | Embodied in`), and one detailed block per principle, ordered by `credibility_risk` then status (most load-bearing yet least-proven first); the generated file carries a "generated — do not hand-edit" banner.
- `scripts/validate.py` exits non-zero with a clear message when any of these are violated: schema invalidity; a `proven`/`asserted` entry whose `proof` file path does not exist; an `embodied_in[].ref` that does not exist; a `proven` or `asserted` entry missing `embodied_in`; or staleness (regenerating the doc in-memory and diffing against the committed `docs/fakoli-style.md` shows a difference).
- `validate.py` exits 0 against the committed seed data and generated doc.
- A `tests/` directory holds tests covering: a passing ledger, each individual validator failure mode (bad status, missing proof, nonexistent proof path, missing embodied_in, staleness), and generator ordering; tests pass under `uv run`.
**Scope:** plugins/fakoli-style/scripts/generate.py, plugins/fakoli-style/scripts/validate.py, plugins/fakoli-style/tests/, plugins/fakoli-style/docs/fakoli-style.md
**Agent:** guido
**Verify:** `cd plugins/fakoli-style && uv run --with pytest --with jsonschema pytest tests/ && uv run --script scripts/generate.py && uv run --script scripts/validate.py`
**Depends on:** Task 2

---

### Task 4: Author the style-ops skill, plugin README, and CHANGELOG

**Intent:** Document the plugin and its management verbs so an operator can add a lesson, set a status, validate, and report without reading the scripts.
**Acceptance criteria:**
- `skills/style-ops/SKILL.md` has valid frontmatter (`name`, `description`) and documents four verbs — add, set-status, validate, report — each mapping to the concrete `uv run --script` invocation, and states the lifecycle rule (no principle reaches `proven` without an executable proof pointer).
- `README.md` is the authoritative reference: what the Fakoli Style is, the canonical-data→generated-doc model, the verbs, and a quick-start; it links to `docs/fakoli-style.md` rather than duplicating the ledger.
- `CHANGELOG.md` records the `1.0.0` initial release.
- `./scripts/validate.sh plugins/fakoli-style` reports no ERRORs and no missing-README/CHANGELOG warnings.
**Scope:** plugins/fakoli-style/skills/style-ops/SKILL.md, plugins/fakoli-style/README.md, plugins/fakoli-style/CHANGELOG.md
**Agent:** herald
**Verify:** `./scripts/validate.sh plugins/fakoli-style` (exit 0, no ERROR/WARN for README or CHANGELOG)
**Depends on:** Task 1, Task 3

---

### Task 5: Integrate the plugin into the marketplace, README table, and registry

**Intent:** Register the plugin across the three sync sources and regenerate the registry so it is discoverable.
**Acceptance criteria:**
- `.claude-plugin/marketplace.json` has a `fakoli-style` entry with `name`, `version` `1.0.0`, `description`, `source` beginning with `./`, and `category` `utilities`.
- The repo-root `README.md` "Available Plugins" table includes a `fakoli-style` row consistent with the other entries.
- Running `./scripts/generate-index.sh` regenerates `registry/index.json`, `registry/categories.json`, and `registry/tags.json`, and `fakoli-style` appears in `registry/index.json`.
- README table, `registry/index.json`, and `marketplace.json` all agree on the active plugin set (the three-source sync rule).
**Scope:** .claude-plugin/marketplace.json, README.md, registry/index.json, registry/categories.json, registry/tags.json
**Agent:** keeper
**Verify:** `./scripts/generate-index.sh && jq -e '.plugins[]|select(.name=="fakoli-style")' registry/index.json`
**Depends on:** Task 1, Task 2, Task 3, Task 4

---

### Task 6: Full validation scorecard

**Intent:** Produce an evidence-based pass/fail scorecard proving the plugin and repo integration are correct and shippable.
**Acceptance criteria:**
- `./scripts/validate.sh plugins/fakoli-style` and `./scripts/test-path-resolution.sh plugins/fakoli-style` both pass with no ERRORs.
- The plugin's own gates pass: `uv run --with pytest --with jsonschema pytest` (in the plugin) and `uv run --script scripts/validate.py` both exit 0.
- The generated `docs/fakoli-style.md` is confirmed not stale (validator staleness check passes).
- `fakoli-style` is present and consistent across README table, `marketplace.json`, and `registry/index.json`.
- Scorecard reports each check as PASS/FAIL with the exact command output; no fixes are made by this task (findings routed back to the owning agent).
**Scope:** (read-only across the plugin and registry)
**Agent:** sentinel
**Verify:** `./scripts/validate.sh plugins/fakoli-style && ./scripts/test-path-resolution.sh plugins/fakoli-style`
**Depends on:** Task 5
