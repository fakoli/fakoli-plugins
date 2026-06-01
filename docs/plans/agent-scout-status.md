---
agent: scout
status: COMPLETE
task: pre-planning research for plugins/fakoli-style/
date: 2026-05-31
---

# Scout Findings: fakoli-style Plugin Pre-Planning Research

Status: COMPLETE with findings

---

## Finding 1: create-plugin workflow (plugin-dev:create-plugin)

File confirmed at:
`/Users/sdoumbouya/.claude/plugins/cache/claude-plugins-official/plugin-dev/unknown/commands/create-plugin.md`

The `create-plugin` command is an 8-phase workflow (Discovery, Component Planning, Design, Structure, Implementation, Validation, Testing, Documentation). Key conventions it prescribes:

**Scaffold structure (Phase 4):**
```
plugin-name/
  .claude-plugin/
    plugin.json          # initial version: "0.1.0" per template
  skills/<skill-name>/   # one dir per skill
  agents/                # if needed
  hooks/                 # if needed
```
- `commands/` is explicitly called a "legacy format" — new plugins use `skills/<name>/SKILL.md`
- `README.md` and `.gitignore` created at Phase 4
- plugin.json starts at `"version": "0.1.0"` in the command template (the repo CLAUDE.md says `"1.0.0"` — see note in Finding 8; use `1.0.0` for this repo's convention)

The command does NOT mention `data/`, `schema/`, or `scripts/` as special auto-discovered dirs — they are free-form non-standard directories, which is exactly what fakoli-style needs.

**plugin-structure SKILL.md** (the skill loaded at Phase 2) lists `scripts/` as an explicitly valid plugin directory in its "Full-Featured Plugin" example:
```
hooks/
  hooks.json
  scripts/
.mcp.json
scripts/       # Shared utilities — appears at plugin root level
```

**Alignment assessment:** The proposed fakoli-style layout aligns perfectly. `data/`, `schema/`, `scripts/` are non-standard dirs that will not be auto-discovered, have no validation rules against them, and are recognized as valid by plugin-structure conventions.

---

## Finding 2: Repo plugin conventions — Python, data/schema/scripts patterns

**No existing plugin uses `data/` or `schema/` at plugin root.** The only existing `schemas/` dirs are:
- `plugins/cli-to-plugin/schemas/` — contains `help-tree.schema.json`, `plugin.schema.json`, `skill.schema.json`

This is the closest precedent. cli-to-plugin puts JSON schemas in `plugins/cli-to-plugin/schemas/` (plural). The proposed `schema/` (singular) is fine — no naming rule exists.

**Python patterns in this repo:**

1. **`plugins/cli-to-plugin/scripts/`** — contains `discover.py` and `override.py`. These use PEP 723 inline script metadata (the `# /// script` block) invoked via `uv run --script <file> <args>`. No `pyproject.toml` in the scripts dir itself, no separate package. Dependency list is empty for discover.py (stdlib only).

2. **`plugins/notebooklm-enhanced/scripts/`** — contains a `pyproject.toml` and `uv.lock` directly in `scripts/`. The pyproject.toml declares `dependencies = ["notebooklm-py>=0.3.4,<1.0"]`. Scripts are invoked via `uv run --project plugins/notebooklm-enhanced/scripts/ <script>`.

3. **`plugins/fakoli-state/bin/`** — full Python package with `pyproject.toml`, `src/fakoli_state/` layout, `hatchling` build backend, `requires-python = ">=3.11"`. Tests live in `plugins/fakoli-state/tests/` (sibling to `bin/`). `pytest.ini_options.testpaths = ["../tests"]` points from `bin/` up to tests. Dev deps: `pytest>=8`, `pytest-cov>=5`, `ruff>=0.5`, `mypy>=1.10`.

**Recommended pattern for fakoli-style** (scripts that need `jsonschema`): Use PEP 723 inline script metadata in each `.py` file, run via `uv run --script scripts/validate.py`. This is the lightest-weight approach and matches cli-to-plugin's pattern. No `pyproject.toml` needed unless tests are added.

Example header for `scripts/validate.py`:
```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.0"]
# ///
```

Invocation: `uv run --script plugins/fakoli-style/scripts/validate.py`

---

## Finding 3: Proof pointer for PR #66 agreement test

File confirmed at:
`/Users/sdoumbouya/code/claude-env/fakoli-plugins/plugins/fakoli-state/tests/test_transitions.py`

The exact test function name is:

```
test_transition_gate_agrees_with_review_gate
```

It is a parametrized test in the class `TestEvidenceGateDelegation` at line 730. The decorator is:
```python
@pytest.mark.parametrize(
    "required, evidence_kwargs",
    [
        ([], {}),
        ...  # 14 parameter tuples total
    ],
)
def test_transition_gate_agrees_with_review_gate(
    self, required: list[str], evidence_kwargs: dict
) -> None:
```

The docstring states: "Lock: the enforcing transition gate accepts iff evidence_complete passes. This is the regression guard against the two gates ever diverging again (the bug this change fixes: the transition enforced raw substring while `apply` previewed evidence_complete)."

**Proof pointer for the principles ledger:**
```
plugins/fakoli-state/tests/test_transitions.py::TestEvidenceGateDelegation::test_transition_gate_agrees_with_review_gate
```

---

## Finding 4: SL-0 through SL-7 IDs from roadmap.md

File: `plugins/fakoli-state/docs/roadmap.md`

All 8 SL items, extracted verbatim:

| ID | One-line meaning |
|----|-----------------|
| **SL-0** | Unify evidence gate with `apply` preview — `transitions._evidence_complete` delegates to `review.gates.evidence_complete`; parametrized agreement test locks the two gates. **SHIPPED in 1.17.1 (PR #66).** |
| **SL-1** | Prove replay in CI — ship `fakoli-state replay --from-events events.jsonl`; add CI job asserting replayed canonical state equals original. **TARGETED, highest leverage.** |
| **SL-2** | Measure the critic false-pass rate — build fault-injection harness; feed known-bad diffs to critic agent; measure how many are waved through; commit baseline number. **TARGETED.** |
| **SL-3** | Ship `ProofArtifact` (typed evidence) — replace free-text `required_evidence` with typed, verifiable proofs (`CommandProof`, `DiffProof`, `LinkProof`, `AssertionProof`); gate stops asking "does this word appear" and asks "does a passing CommandProof exist." **SPEC-FIRST.** |
| **SL-4** | Promote status-file coordination to canonical state — replace fakoli-flow/fakoli-crew markdown status files with state `Event`s; wave engine reads `fakoli-state` instead of parsing prose. **TARGETED.** |
| **SL-5** | Contract-level conflict with after-the-fact reconciliation — add `OutputContract` to `Task`; key `ConflictGroup` on contract overlap not file overlap; post-`apply` drift check comparing declared contract to actual `DiffProof`. **SPEC-FIRST.** |
| **SL-6** | Score spec assumptions, not just tasks — extend six-dimension `Score` to PRD requirements; surface highest-blast-radius, lowest-confidence assumptions before planning; `fakoli-state plan` reports top assumptions ranked by `blast_radius * uncertainty`. **TARGETED.** |
| **SL-7** | Workflow adapter spike — build `fakoli-state workflow-step` governed-step wrapper; one worked example wiring a dynamic-workflow script to persist script-variable intermediates as `Evidence`/`Decision` rows. **SPEC-FIRST, spike not product.** |

Note: SL-0 is already shipped. SL-1, SL-2, SL-6 are TARGETED (committed). SL-3, SL-5, SL-7 are SPEC-FIRST (need design doc). SL-4 is TARGETED (Wave 3).

---

## Finding 5: marketplace.json structure and valid categories

File: `/Users/sdoumbouya/code/claude-env/fakoli-plugins/.claude-plugin/marketplace.json`

This is the **repo-level** marketplace.json (not per-plugin). It is auto-updated by `scripts/generate-index.sh`.

**Per-plugin entry structure** (exact fields as they appear):
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "...",
  "category": "productivity",   // optional but expected
  "source": "./plugins/plugin-name"
}
```

**Required fields per entry:** `name`, `source` (must start with `./`). The field `path` is explicitly rejected by validation (use `source` instead).

**Valid category values** (defined in the `categories` array of marketplace.json):
- `productivity`
- `integrations`
- `utilities`

No other category values exist or are validated as valid.

**How a new plugin is added:** `generate-index.sh` calls `update_marketplace()` which syncs the plugins array from `plugins/` scan results. It preserves any existing `category` field from the marketplace.json entry. If no entry exists yet, the new plugin gets `name`, `version`, `description`, `source` but no `category` — the category must be added manually or it will remain absent. This triggers the CLAUDE.md checklist item "Assign a category."

**No per-plugin marketplace.json** exists — only the single repo-level `.claude-plugin/marketplace.json`. The per-plugin `.claude-plugin/` directory contains only `plugin.json`.

---

## Finding 6: Registry generation — what generate-index.sh scans and outputs

Script: `scripts/generate-index.sh`

**Input:** Scans `plugins/` (depth 1) and `external_plugins/` (depth 1, if it exists) for subdirectories containing `.claude-plugin/plugin.json`. Does NOT scan `archive/`.

**Outputs (three files):**
1. `registry/index.json` — full plugin index with fields: `$schema`, `version`, `generatedAt`, `pluginCount`, `plugins[]`. Each plugin entry includes: `name`, `version`, `description`, `author`, `repository`, `license`, `keywords`, `homepage`, `path`, `indexedAt`. Fields are selected with `with_entries(select(.value != null))` — absent manifest fields are omitted.
2. `registry/categories.json` — plugins grouped by `category` field (`group_by(.category // "uncategorized")`). Since `plugin.json` has no `category` field (it is only in marketplace.json), ALL plugins will land in `uncategorized` bucket in categories.json unless the generation logic is extended.
3. `registry/tags.json` — tag cloud built from `keywords` arrays, sorted by count descending.

**Also updates:** `.claude-plugin/marketplace.json` — syncs the plugins list, preserving existing `category` fields.

**Change-detection:** Files are only written if content (excluding timestamp fields) has changed.

**Requirement:** `jq` must be installed.

---

## Finding 7: Validation gates — what validate.sh and test-path-resolution.sh check

**validate.sh checks:**

1. JSON syntax of `.claude-plugin/plugin.json` — ERROR if invalid
2. Unrecognized fields (derived from `schemas/plugin.schema.json` at runtime) — ERROR
3. `name` required, kebab-case `^[a-z0-9-]+$` — ERROR
4. `version` semver if present — ERROR
5. `author` must be object (not string) — ERROR
6. `repository` must be string (not object) — ERROR
7. `keywords` must be array — ERROR
8. `README.md` present — WARN if absent
9. `CHANGELOG.md` present — WARN if absent
10. LICENSE file or `license` field — WARN if neither
11. At least one of `skills/`, `commands/`, `agents/`, `hooks/` — WARN if none found
12. Declared `commands`/`agents`/`skills` in manifest — WARN (auto-discovered, unnecessary)
13. `../` prefix on path fields — WARN (use `./` instead)
14. `hooks` string path resolves to existing file — ERROR if not found
15. `mcpServers` string path resolves to existing file — ERROR if not found
16. Hook safety: missing `hooks` array wrapper — ERROR
17. Hook safety: empty `hooks` array — ERROR
18. Hook safety: no matcher on PreToolUse/PostToolUse/UserPromptSubmit — WARN
19. Hook safety: prompt-type on UserPromptSubmit — ERROR
20. Hook safety: prompt-type on PreToolUse with no matcher — ERROR
21. Hook safety: command-type hook with no timeout — WARN
22. Hook safety: hook script not found — ERROR
23. Hook safety: `set -e` in hook script — WARN

**What validate.sh does NOT check:** `data/`, `schema/`, `scripts/` directories — they are completely transparent to the validator.

**test-path-resolution.sh checks** (deep scan):
- All component path fields from manifest (commands, agents, skills, hooks, mcpServers, outputStyles, lspServers)
- Resolves each path to disk — ERROR if not found
- WARN on auto-discovered fields being declared
- Scans all hook scripts for `cat | grep` anti-pattern — WARN
- Scans all hook scripts for `set -e` — WARN
- Checks matcher analysis on hooks

**Answer for fakoli-style:** Having `data/`, `schema/`, `scripts/` directories will trigger ZERO errors or warnings from either script. Having only `skills/` auto-discovered (no manifest component path fields) is the correct pattern and will validate cleanly. The validator will check for `README.md` and `CHANGELOG.md` (WARN if absent) and `license` field / LICENSE file.

**Allowed manifest fields** (from `schemas/plugin.schema.json`, enforced at runtime):
`name`, `version`, `description`, `author`, `license`, `repository`, `homepage`, `keywords`, `commands`, `agents`, `skills`, `hooks`, `mcpServers`, `outputStyles`, `lspServers`

No other fields allowed (`$schema` will trigger ERROR "Unrecognized field").

---

## Finding 8: New Plugin Checklist (exact from CLAUDE.md)

Extracted verbatim from CLAUDE.md section "New Plugin Checklist":

> When adding a new plugin, ALWAYS complete ALL of these steps before merging:
> 1. Create the plugin in `plugins/<name>/` with all required files
> 2. **Update `README.md`** — add the plugin to the "Available Plugins" table
> 3. **Set initial version** to `1.0.0` in `.claude-plugin/plugin.json`
> 4. Run `./scripts/generate-index.sh` to regenerate `registry/index.json`
> 5. Run `./scripts/validate.sh plugins/<name>` to validate the plugin
> 6. Run `./scripts/test-path-resolution.sh plugins/<name>` to deep scan paths and hooks
> 7. Verify no auto-discovered directories (`skills/`, `commands/`, `agents/`) are declared in manifest
> 8. Verify `hooks`/`mcpServers` paths use `./` prefix (relative to plugin root) and targets exist
> 9. If plugin has hooks: verify matchers are specific, no `set -e`, timeouts are set
> 10. **Assign a category** in `.claude-plugin/marketplace.json` — must be one of: `productivity`, `integrations`, `utilities`
> 11. Verify the plugin appears in both the README table AND `registry/index.json`

Note: The checklist says initial version is `1.0.0` (not `0.1.0` which is what the `create-plugin` command template uses). Use `1.0.0` per CLAUDE.md.

Also relevant from CLAUDE.md "Keeping Sources in Sync":
> Three sources must always agree on the active plugin set:
> 1. `README.md` — "Available Plugins" table
> 2. `registry/index.json` — auto-generated by `generate-index.sh`
> 3. `.claude-plugin/marketplace.json` — marketplace metadata

---

## Finding 9: Python toolchain — version, uv, invocation, test patterns

**Python availability:** `cpython-3.14` is present (confirmed by `__pycache__/discover.cpython-314.pyc` in cli-to-plugin). `cpython-3.11` is also present (cpython-311.pyc files). The fakoli-state pyproject.toml requires `>=3.11`.

**uv availability:** Confirmed installed and in use across the repo. Evidence:
- `plugins/notebooklm-enhanced/scripts/uv.lock` exists
- `plugins/cli-to-plugin/scripts/discover.py` uses PEP 723 inline metadata (`# /// script` block) which requires `uv run --script`
- CLAUDE.md "Python Scripts with uv" section explicitly documents: `uv run --with <pkg>` for one-off testing, `pyproject.toml` for plugin scripts

**How existing Python scripts are invoked:**

Pattern A (cli-to-plugin, recommended for fakoli-style):
```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.0"]
# ///
```
Invoked as: `uv run --script scripts/generate.py`

Pattern B (notebooklm-enhanced): `pyproject.toml` in `scripts/` dir with `uv.lock`.
Invoked as: `uv run --project scripts/ <script>`

Pattern C (fakoli-state): Full package under `bin/` with `pyproject.toml` and `src/` layout.

**For fakoli-style**, Pattern A (PEP 723 inline metadata) is the lightest and most appropriate. Both `scripts/generate.py` and `scripts/validate.py` can carry their own inline dependency declarations.

**Test patterns:**

- fakoli-state: `pytest` with tests in `plugins/fakoli-state/tests/`, `pyproject.toml` in `plugins/fakoli-state/bin/` with `testpaths = ["../tests"]`. Run from `bin/` directory: `cd plugins/fakoli-state/bin && uv run pytest`.
- cli-to-plugin: no tests found in scripts dir (scripts are standalone)
- CLAUDE.md testing standards: see `docs/TESTING_STANDARDS.md`

**For fakoli-style scripts/validate.py:** Since the validator is a standalone script (not a library), tests could either be:
1. Inline assertions at the bottom of the script (simplest)
2. A `tests/` dir at plugin root with `pytest` + a `pyproject.toml` in a `bin/` or root equivalent

If a `tests/` dir is added, follow fakoli-state's pattern: `pyproject.toml` with `[tool.pytest.ini_options]` and `dev = ["pytest>=8"]` dependency group.

**No tests directory exists yet** for the planned plugin — starting fresh.

---

## Synthesis: Layout decisions confirmed by findings

The proposed layout is valid and well-supported:

```
plugins/fakoli-style/
  .claude-plugin/plugin.json     name="fakoli-style", version="1.0.0"
  README.md                      REQUIRED (WARN if absent)
  CHANGELOG.md                   WARN if absent
  data/principles.json           non-standard dir, invisible to validator
  schema/principles.schema.json  non-standard dir, invisible to validator
  docs/fakoli-style.md           non-standard dir, invisible to validator
  scripts/generate.py            non-standard dir, PEP 723 inline metadata
  scripts/validate.py            non-standard dir, PEP 723 inline metadata
  skills/style-ops/SKILL.md      auto-discovered, do NOT declare in manifest
```

**No hooks planned** → no hook safety checks fire.

**Manifest will declare:** `name`, `version`, `description`, `author`, `license`, `keywords` only. No component path fields needed.

**Category for marketplace.json:** `productivity` (governing/meta-operational tools fit here; `utilities` is also defensible).

**Proof pointer** for the SL-0 principle's `proof` field:
`plugins/fakoli-state/tests/test_transitions.py::TestEvidenceGateDelegation::test_transition_gate_agrees_with_review_gate`

**SL ID mapping for `open_work`** on aspirational principles: Use SL-1 through SL-7 as appropriate (SL-0 is already shipped).
