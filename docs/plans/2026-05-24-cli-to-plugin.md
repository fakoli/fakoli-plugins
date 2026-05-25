# cli-to-plugin — Execution Plan

**Goal:** Build a Claude Code plugin that converts any CLI (e.g., `gh`) into a self-contained Claude Code plugin by walking the CLI's `--help` tree, writing one skill per command group, and letting the user pick LLM-proposed workflow meta-skills.
**Spec:** docs/specs/2026-05-24-cli-to-plugin.md
**Language:** Python (script-dominant new plugin; marketplace itself is bash + markdown)
**Crew:** fakoli-crew v2.0.0 (8 agents)
**Scout findings:** docs/plans/agent-scout-status.md

---

## Wave 1 — Foundation (parallel)

### Task 1: Scaffold the plugin skeleton

**Intent:** Create the plugin directory at `plugins/cli-to-plugin/` with a valid manifest, license placeholder, and empty subdirectories ready for component files.

**Acceptance criteria:**
- `plugins/cli-to-plugin/.claude-plugin/plugin.json` exists and validates against `schemas/plugin.schema.json`
- Manifest uses object form for `author` (string form is rejected by `validate.sh`)
- Manifest `description` is 10–500 characters
- Manifest `name` is `cli-to-plugin`, version is `1.0.0`, keywords include `cli-to-plugin` and `generator`
- Subdirectories exist (empty is fine): `commands/`, `scripts/`, `schemas/`, `templates/`, `tests/`, `tests/fixtures/`, `tests/smoke/`

**Scope:** plugins/cli-to-plugin/.claude-plugin/plugin.json
**Agent:** smith
**Verify:** `./scripts/validate.sh plugins/cli-to-plugin`
**Depends on:** (none)

---

### Task 2: Define the help-tree JSON Schema

**Intent:** Author the canonical schema for the output of `discover.py` so downstream synthesis and tests have a stable contract.

**Acceptance criteria:**
- `plugins/cli-to-plugin/schemas/help-tree.schema.json` exists
- Schema validates `$schema: https://json-schema.org/draft/2020-12/schema`
- Schema requires top-level `cli`, `groups`, `discovery` objects; `global_flags` is optional
- Each command has a `path` array (e.g., `["pr", "list"]`)
- Schema passes `python -m jsonschema` self-check via `Draft202012Validator.check_schema`
- A reasonable hand-written fixture matching the spec example validates against the schema

**Scope:** plugins/cli-to-plugin/schemas/help-tree.schema.json
**Agent:** guido
**Verify:** `uv run --with jsonschema python -c "import json, jsonschema; s=json.load(open('plugins/cli-to-plugin/schemas/help-tree.schema.json')); jsonschema.Draft202012Validator.check_schema(s); print('OK')"`
**Depends on:** (none)

---

### Task 3: Write the SKILL.md and manifest templates

**Intent:** Provide structural reference templates that Claude reads (not text-substituted into) when synthesizing per-group skills, meta-skills, and the generated plugin's manifest.

**Acceptance criteria:**
- `templates/group-skill.md` shows the per-group skill structure (frontmatter + "When to use" + "Commands" + "Common patterns" + "Reference")
- `templates/meta-skill.md` shows the workflow meta-skill structure (frontmatter + "When to use" + numbered "Workflow" + "Variants" + "Related" with `[[name]]` links)
- Frontmatter examples use **hyphenated** keys (`user-invocable`, `disable-model-invocation`, `argument-hint`, `allowed-tools`) — the underscore form in `templates/basic/` is a bug to NOT replicate
- Description lines start with **"Use when..."** per the convention locked in during brainstorm
- `templates/plugin.json.example` shows the generated plugin manifest, with `author` in object form and `keywords` containing `cli-to-plugin`
- All three template files validate as well-formed markdown (no broken frontmatter)

**Scope:** plugins/cli-to-plugin/templates/group-skill.md, plugins/cli-to-plugin/templates/meta-skill.md, plugins/cli-to-plugin/templates/plugin.json.example
**Agent:** herald
**Verify:** `uv run --with jsonschema python -c "import json, jsonschema; s=json.load(open('schemas/plugin.schema.json')); d=json.load(open('plugins/cli-to-plugin/templates/plugin.json.example')); jsonschema.validate(d, s); print('OK')"` AND `grep -l 'Use when' plugins/cli-to-plugin/templates/*.md | wc -l | grep -q 2`
**Depends on:** (none)

---

### Task 4: Capture test fixtures from real CLIs

**Intent:** Record raw `--help` output and hand-curated expected JSON trees for `gh`, `kubectl`, and `docker`, plus pathological-case fixtures (ANSI codes, non-zero exit, deep recursion, empty stdout). These become the source of truth for `discover.py` tests.

**Acceptance criteria:**
- `tests/fixtures/gh-help-raw/` contains captured `gh --help` and `gh <group> --help` outputs for at least 5 groups
- `tests/fixtures/gh-help-tree.expected.json` is a hand-curated expected output that validates against `schemas/help-tree.schema.json`
- Equivalent capture + expected JSON exist for `kubectl` and `docker` (smaller subset acceptable — at least 3 groups each)
- `tests/fixtures/pathological/` contains: `ansi-codes.txt`, `exits-nonzero.txt`, `empty-stdout.txt`, `deep-recursion.txt` (5-level synthetic), `timeout.sh` (a script that sleeps 6s)
- Each fixture has a short `README.md` in `tests/fixtures/` explaining what it tests
- No fixture exceeds 100KB

**Scope:** plugins/cli-to-plugin/tests/fixtures/**
**Agent:** scout
**Verify:** `uv run --with jsonschema python -c "import json,jsonschema; schema=json.load(open('plugins/cli-to-plugin/schemas/help-tree.schema.json')); [jsonschema.validate(json.load(open(f)), schema) for f in ['plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json','plugins/cli-to-plugin/tests/fixtures/kubectl-help-tree.expected.json','plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json']]; print('OK')"`
**Depends on:** Task 2

---

## Wave 2 — Core engine (parallel)

### Task 5: Implement `discover.py`

**Intent:** Walk `<cli> --help` recursively and emit a canonical JSON tree to stdout, conforming to the help-tree schema and respecting the safety bounds defined in the spec (depth ≤ 3, ≤ 500 commands, 5s per-call timeout, 30s total).

**Acceptance criteria:**
- File uses PEP 723 inline metadata with `requires-python = ">=3.11"` and no third-party deps
- Invocation: `uv run --script plugins/cli-to-plugin/scripts/discover.py <cli-name>` writes JSON to stdout, exits 0 on success
- Accepts `--max-depth`, `--max-commands`, `--per-call-timeout`, `--total-timeout` flags with documented defaults
- Strips ANSI escape sequences before parsing
- Forces `LANG=C.UTF-8` for child processes; decodes stdout as UTF-8 with `errors="replace"`
- On non-zero exit from the CLI with non-empty stdout: parses anyway, adds entry to `discovery.warnings`
- On non-zero exit with empty stdout: exits non-zero with a clear error message
- Output JSON validates against `plugins/cli-to-plugin/schemas/help-tree.schema.json`
- Running against real `gh` on this machine produces a tree with at least 10 groups and exits within 30 seconds

**Scope:** plugins/cli-to-plugin/scripts/discover.py
**Agent:** guido
**Verify:** `uv run --script plugins/cli-to-plugin/scripts/discover.py gh > /tmp/gh-tree.json && uv run --with jsonschema python -c "import json,jsonschema; jsonschema.validate(json.load(open('/tmp/gh-tree.json')), json.load(open('plugins/cli-to-plugin/schemas/help-tree.schema.json'))); print('OK')"`
**Depends on:** Task 2

---

### Task 6: Implement `validate-output.sh`

**Intent:** Wrap the marketplace's existing validators so the playbook (and tests) can validate a generated plugin sitting anywhere on disk, including temp directories.

**Acceptance criteria:**
- `scripts/validate-output.sh <absolute-path-to-plugin>` runs `./scripts/validate.sh` and `./scripts/test-path-resolution.sh` against the target
- Also validates each `skills/*/SKILL.md` frontmatter against `schemas/skill.schema.json` using `uv run --with jsonschema python -m jsonschema` (NOT `ajv` — Node is not available on dev machines per scout findings)
- Also validates the generated `plugin.json` against `schemas/plugin.schema.json`
- Exits 0 on full success, non-zero on any failure
- Emits a clear final summary block with counts of errors and warnings
- Does NOT use `set -e` (per marketplace hook safety rules) — uses explicit exit-code checking
- Resolves marketplace script paths relative to the script's own location so it works from any CWD

**Scope:** plugins/cli-to-plugin/scripts/validate-output.sh
**Agent:** smith
**Verify:** `bash -n plugins/cli-to-plugin/scripts/validate-output.sh && plugins/cli-to-plugin/scripts/validate-output.sh "$PWD/plugins/cli-to-plugin"`
**Depends on:** Task 1

---

## Wave 3 — Tests and playbook (parallel)

### Task 7: Write `discover.py` unit + fixture tests

**Intent:** Cover `discover.py` parsing, recursion bounds, ANSI handling, and timeout behavior against the captured fixtures, including pathological cases.

**Acceptance criteria:**
- `tests/test_discover.py` exists and runs via `uv run --with pytest pytest`
- Tests cover: real `gh` fixture matches expected JSON; ANSI-stripping; non-zero exit with stdout (warn-and-continue); non-zero exit with empty stdout (halt); recursion depth cap; command count cap; per-call timeout; UTF-8 decode with replacement
- `tests/test_override_merge.py` covers override-file merging (skip group, rename description, append `extra_guidance`, pre-specify `meta_skills`, halt on unknown group with suggestion, warn on unknown command)
- `pytest --cov=plugins/cli-to-plugin/scripts/discover --cov-report=term-missing` reports ≥ 90% line coverage on `discover.py`
- No test hits the network or expects `gh` to be installed (uses captured fixtures + monkeypatched subprocess)

**Scope:** plugins/cli-to-plugin/tests/test_discover.py, plugins/cli-to-plugin/tests/test_override_merge.py, plugins/cli-to-plugin/tests/conftest.py
**Agent:** welder
**Verify:** `uv run --with pytest --with pytest-cov pytest plugins/cli-to-plugin/tests/ --cov=plugins/cli-to-plugin/scripts --cov-fail-under=90`
**Depends on:** Task 4, Task 5

---

### Task 8: Author the playbook (`commands/cli-to-plugin.md`)

**Intent:** Write the slash command file that guides Claude through the full conversion flow: preflight, discover, confirm scope, generate per-group skills, propose meta-skills, multi-select, generate meta-skills, manifest + README, validate, summary.

**Acceptance criteria:**
- `commands/cli-to-plugin.md` exists with valid frontmatter (`description`, `argument-hint`)
- Supports invocation: `/cli-to-plugin <cli-name> [--out <path>] [--override <path>] [--from-tree <path>] [--no-meta-skills] [--regen]`
- Playbook is structured as numbered steps matching the 10-step flow in the spec
- Uses `AskUserQuestion` for the scope-confirmation multi-select and the meta-skill picker
- Atomic-write protocol documented: `Write` to `<path>.tmp`, then Bash `mv` into place
- Regeneration flow: detects existing `--out` dir, asks user (overwrite / diff-and-merge / cancel), defaults to diff-and-merge in the question's option ordering
- `--from-tree <path>` skips Step 2 entirely; reads tree from disk
- `--no-meta-skills` skips Steps 5–7 (used by CI smoke test)
- Final step (summary block) follows the exact format in the spec, including warnings and next-steps lines
- Modeled after `plugins/nano-banana-pro/commands/configure.md` for multi-step interactive structure (scout's recommended reference)

**Scope:** plugins/cli-to-plugin/commands/cli-to-plugin.md
**Agent:** welder
**Verify:** `test -f plugins/cli-to-plugin/commands/cli-to-plugin.md && grep -q '^---' plugins/cli-to-plugin/commands/cli-to-plugin.md && grep -qE '(Step|##) (1|2|3|4|5|6|7|8|9|10)' plugins/cli-to-plugin/commands/cli-to-plugin.md && ./scripts/validate.sh plugins/cli-to-plugin`
**Depends on:** Task 3, Task 5, Task 6

---

## Wave 4 — Documentation and smoke (parallel)

### Task 9: Write the smoke test script

**Intent:** End-to-end test using `--from-tree` against the captured `gh` fixture: assert all expected files appear, every group has a skill, and marketplace validators pass on the output.

**Acceptance criteria:**
- `tests/smoke/test-gh-generation.sh` runs without arguments, exits 0 on success
- Uses `claude --no-interactive` with `/cli-to-plugin gh --from-tree tests/fixtures/gh-help-tree.expected.json --out $TMP/gh --no-meta-skills`
- Asserts: `$TMP/gh/.claude-plugin/plugin.json` exists; every group from the fixture has a matching `$TMP/gh/skills/gh-<group>/SKILL.md`
- Runs `./scripts/validate.sh "$TMP/gh"` and asserts exit 0
- Runs `./scripts/test-path-resolution.sh "$TMP/gh"` and asserts exit 0
- Cleans up `$TMP` on success and on failure (trap EXIT)
- Does NOT use `set -e` (uses explicit exit-code checking per hook safety rules)
- Skips with a clear message (exit 0, warning printed) if `claude` is not on PATH so CI without the CLI doesn't false-fail

**Scope:** plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh
**Agent:** welder
**Verify:** `bash -n plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh && bash plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh`
**Depends on:** Task 4, Task 6, Task 8

---

### Task 10: Write the plugin README

**Intent:** Document `cli-to-plugin` for first-time visitors: what it does, install requirements, basic usage, override file shape, and limitations.

**Acceptance criteria:**
- `plugins/cli-to-plugin/README.md` exists
- Opens with a concrete value proposition (not "a tool for X" — specifies what problem this solves and what the user gets)
- Includes a copy-paste Quick Start showing `/cli-to-plugin gh` and the expected output skeleton
- Documents prerequisites: `uv` (with install command), target CLI installed, `jq` (already a marketplace requirement)
- Documents flags: `--out`, `--override`, `--from-tree`, `--no-meta-skills`, `--regen`, `--max-depth`, `--max-commands`
- Includes the override file YAML shape with one full example
- Lists known limitations (per spec's "Out of scope" section): only skills, no command-mirror, no auto-update, requires `--help` support, interactive meta-skill picker
- Links to the spec file (`docs/specs/2026-05-24-cli-to-plugin.md`) under a "Design notes" or "See also" section

**Scope:** plugins/cli-to-plugin/README.md
**Agent:** herald
**Verify:** `test -f plugins/cli-to-plugin/README.md && grep -q '^# ' plugins/cli-to-plugin/README.md && wc -l plugins/cli-to-plugin/README.md | awk '{exit ($1 < 80)}'`
**Depends on:** Task 6, Task 8

---

## Wave 5 — CI and marketplace integration (parallel)

### Task 11: Add CI workflow

**Intent:** Wire pytest + smoke test + marketplace validators into GitHub Actions on PRs touching the plugin.

**Acceptance criteria:**
- `.github/workflows/cli-to-plugin-tests.yml` exists
- Triggers on `pull_request` with `paths: ['plugins/cli-to-plugin/**']`
- Steps install `uv` (via `astral-sh/setup-uv@v3` or equivalent), run `pytest` against the plugin's tests with coverage gate, run the smoke script (gracefully skipping if `claude` is unavailable in CI), run `./scripts/validate.sh plugins/cli-to-plugin`
- Uses `runs-on: ubuntu-latest`
- Job fails on any non-zero exit
- Does not duplicate the marketplace-wide validation (already runs on `plugins/**`)

**Scope:** .github/workflows/cli-to-plugin-tests.yml
**Agent:** keeper
**Verify:** `python -c "import yaml; yaml.safe_load(open('.github/workflows/cli-to-plugin-tests.yml'))" && grep -q 'cli-to-plugin' .github/workflows/cli-to-plugin-tests.yml`
**Depends on:** Task 7, Task 9

---

### Task 12: Marketplace sync

**Intent:** Register `cli-to-plugin` in the three sync sources required by CLAUDE.md: root README "Available Plugins" table, `.claude-plugin/marketplace.json`, and the regenerated `registry/index.json`.

**Acceptance criteria:**
- Root `README.md` "Available Plugins" table includes a row for `cli-to-plugin` with a one-line description
- `.claude-plugin/marketplace.json` has an entry for `cli-to-plugin` with category `utilities`
- `./scripts/generate-index.sh` runs cleanly and `registry/index.json` now contains an entry for `cli-to-plugin`
- The three sources agree on the plugin's name, version (`1.0.0`), and one-line description
- `./scripts/validate.sh` exits 0 across the whole marketplace

**Scope:** README.md, .claude-plugin/marketplace.json, registry/index.json
**Agent:** keeper
**Verify:** `./scripts/generate-index.sh && jq -e '.plugins[] | select(.name == "cli-to-plugin")' registry/index.json > /dev/null && jq -e '.plugins[] | select(.name == "cli-to-plugin")' .claude-plugin/marketplace.json > /dev/null && grep -q 'cli-to-plugin' README.md && ./scripts/validate.sh`
**Depends on:** Task 1, Task 10

---

## Wave 6 — Final review

### Task 13: Critic review of the assembled plugin

**Intent:** Independent end-to-end review of code quality, frontmatter correctness, naming, manifest, hook safety patterns (none expected but worth confirming), and Python/bash idioms.

**Acceptance criteria:**
- Critic produces a written report at `docs/plans/agent-critic-status.md` covering: `discover.py` (correctness, error handling, edge cases), `validate-output.sh` (safety, portability), playbook (structure, AskUserQuestion usage, atomic-write fidelity to the spec), templates (frontmatter hyphen convention), tests (coverage of error paths)
- Each finding has severity: ERROR / WARN / INFO
- No ERROR-severity findings remain unaddressed (any ERROR triggers a follow-up task before verify)
- Report explicitly confirms or refutes: "the generated plugin produced by this generator would pass marketplace validators" (based on reading the playbook, not running it)

**Scope:** (review-only — does not modify files)
**Agent:** critic
**Verify:** `test -f docs/plans/agent-critic-status.md && grep -qE '(PASS|READY|No ERROR-severity)' docs/plans/agent-critic-status.md`
**Depends on:** Task 7, Task 8, Task 9, Task 10, Task 11, Task 12

---

## Self-review

- **Spec coverage** — Walked the spec's "Acceptance criteria" section: items 1, 2, 3, 4, 5, 6, 7, 9 map to Tasks 5/7, 8/12, 6, 8, 8, 8, 8, 7. Item 8 (generated `gh` plugin works in a fresh session) and item 10 (manual smoke matrix) are deferred to `/flow:verify` and release-gate testing, not implementation tasks. Out-of-scope items (no command-mirror, no agents, no auto-update) are absent from the plan as required. ✓
- **Criteria clarity** — Every criterion is a command output check or file-existence/content check. No "error handling is correct"–style vagueness. ✓
- **Dependency graph** — No cycles. Wave 1 has no deps; Wave 2 depends on Wave 1; Wave 3 on Wave 2; Wave 4 on Wave 2/3; Wave 5 on Wave 3/4; Wave 6 on all prior. Within each wave, tasks touch disjoint files. ✓
- **Agent assignment** — smith for plugin scaffolding & shell wrappers; guido for new modules (schema, engine); herald for templates and README; scout for fixture capture (research-adjacent: real CLI inputs); welder for tests + playbook (integration of upstream pieces); keeper for CI + marketplace sync; critic only at the final review wave. ✓
- **Code-free check** — Tasks describe outcomes, not bodies. No function bodies, no line numbers, no step-by-step instructions in acceptance criteria. The one place with prescriptive detail (Task 6's mention of `uv run --with jsonschema python -m jsonschema` vs. `ajv`) is justified — it's a configuration/tooling choice the agent cannot independently discover. ✓
