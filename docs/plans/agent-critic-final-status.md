## Code Review Report

**Scope:** Final review of assembled `cli-to-plugin` plugin (v1.1.0 Wave 5 + holistic)

**Files reviewed:**
- `.github/workflows/cli-to-plugin-tests.yml`
- `README.md` (root, Available Plugins table)
- `.claude-plugin/marketplace.json`
- `registry/index.json`
- `scripts/generate-index.sh` (Task 12 category-preservation patch)
- `plugins/cli-to-plugin/.claude-plugin/plugin.json`
- `plugins/cli-to-plugin/README.md`
- `plugins/cli-to-plugin/commands/cli-to-plugin.md`
- `plugins/cli-to-plugin/schemas/help-tree.schema.json`
- `plugins/cli-to-plugin/scripts/discover.py`
- `plugins/cli-to-plugin/scripts/override.py`
- `plugins/cli-to-plugin/scripts/validate-output.sh`
- `plugins/cli-to-plugin/templates/group-skill.md`
- `plugins/cli-to-plugin/templates/meta-skill.md`
- `plugins/cli-to-plugin/templates/plugin.json.example`
- `plugins/cli-to-plugin/tests/conftest.py`
- `plugins/cli-to-plugin/tests/test_discover.py`
- `plugins/cli-to-plugin/tests/test_override_merge.py`
- `plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh`
- `plugins/cli-to-plugin/tests/fixtures/README.md`
- `docs/specs/2026-05-24-cli-to-plugin.md`
- `docs/plans/2026-05-24-cli-to-plugin.md`

**Reviewed by:** critic
**Date:** 2026-05-25

---

### MUST FIX

**`scripts/generate-index.sh:269-278` — New plugins silently dropped from marketplace.json when not pre-registered**

The category-preservation fix in Task 12 introduced a silent data-loss regression. The jq expression uses:

```jq
($existing[] | select(.name == $p.name)) as $ex |
```

When `$p.name` does not exist in `$existing[]`, jq's generator produces zero outputs for the entire path, causing the entire plugin entry to be silently omitted from `marketplace_plugins`. A newly added plugin that is in `plugins/` but not yet in `.claude-plugin/marketplace.json` will be dropped from the marketplace output on the next `generate-index.sh` run — with no error and no warning.

This is confirmed by direct testing:

```bash
echo '[{"name":"cli-to-plugin","path":"plugins/cli-to-plugin"}, {"name":"brand-new","path":"plugins/brand-new"}]' \
  | jq --argjson existing '[{"name":"cli-to-plugin","category":"utilities"}]' \
  '[.[] | . as $p | ($existing[] | select(.name == $p.name)) as $ex | {name: $p.name}]'
# Output: [{"name":"cli-to-plugin"}]   ← "brand-new" silently gone
```

`cli-to-plugin` itself is not affected right now because it was manually added to `marketplace.json` before `generate-index.sh` ran. But the next plugin added to the repo without first editing `marketplace.json` will be silently erased from marketplace sync.

Fix using `first(... // empty)` with a null-safe fallback:

```bash
marketplace_plugins=$(echo "$plugins" | jq --argjson existing "$existing_marketplace" '[.[] | . as $p |
    (($existing[] | select(.name == $p.name)) // null) as $ex |
    {
        name: $p.name,
        version: $p.version,
        description: $p.description
    }
    | if ($ex != null and ($ex | has("category"))) then . + {category: $ex.category} else . end
    | . + {source: ("./\($p.path)")}
]')
```

The `// null` coerces an empty generator to `null`, allowing the path to produce one output per plugin and the `if $ex != null` guard to handle the "not in existing" case without appending a category.

---

**`plugins/cli-to-plugin/scripts/validate-output.sh:185-208` — Shell-interpolated Python string enables code injection from SKILL.md content**

The frontmatter is extracted from the SKILL.md file and interpolated directly into a Python `-c` string using `'''$frontmatter'''`:

```bash
frontmatter=$(awk '/^---$/{c++; if(c==2) exit; next} c==1 {print}' "$skill_file")
skill_validate_output=$(uv run ... python -c "
...
frontmatter = '''$frontmatter'''
...")
```

If the SKILL.md frontmatter contains `'''` (triple single-quote), the Python string is broken and the remainder of `$frontmatter` is interpreted as Python code. A malicious CLI whose `--help` output causes `discover.py` to emit a skill with `'''` in the frontmatter would execute arbitrary Python in the context of the validating user.

This is not a theoretical concern: `discover.py` takes user-supplied CLI help output and passes it through to the SKILL.md synthesis step (via Claude), and the validate script runs on the generated output. Anyone who can influence `<cli> --help` can craft a frontmatter injection.

Fix by writing the frontmatter to a temp file and reading it in Python, eliminating the shell interpolation entirely:

```bash
tmp_frontmatter=$(mktemp)
printf '%s' "$frontmatter" > "$tmp_frontmatter"

skill_validate_output=$(uv run --with jsonschema --with pyyaml python -c "
import sys, json, yaml, jsonschema

with open('$tmp_frontmatter') as f:
    raw = f.read()

try:
    data = yaml.safe_load(raw)
except yaml.YAMLError as e:
    print(f'YAML parse error: {e}', file=sys.stderr)
    sys.exit(1)

if data is None:
    data = {}

with open('$SKILL_SCHEMA') as f:
    schema = json.load(f)

try:
    jsonschema.validate(instance=data, schema=schema)
    print('OK')
except jsonschema.ValidationError as e:
    print(f'Schema violation: {e.message}', file=sys.stderr)
    sys.exit(1)
" 2>&1)
skill_validate_exit=$?
rm -f "$tmp_frontmatter"
```

---

**`.github/workflows/cli-to-plugin-tests.yml:41-46` — `jq` installed after smoke test; smoke test calls validators that require `jq`**

The workflow step order is:

```yaml
- name: Run smoke test          # step 2
  run: bash plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh

- name: Install jq              # step 3 — too late
  run: sudo apt-get install -y -qq jq
```

The smoke test calls `./scripts/validate.sh` and `./scripts/test-path-resolution.sh`, both of which `require jq`. The smoke test is currently saved from failure only because it SKIPs when `claude` is not on PATH — and `claude` is never on PATH in CI. This dependency on a behavioral coincidence (`claude` absent → skip before jq needed) makes the workflow silently fragile: the moment `claude` becomes available in CI (e.g., if the team adds a `claude` binary to CI), the smoke test will fail with a cryptic `jq: command not found`.

Fix by moving `Install jq` and `Make scripts executable` before `Run smoke test`:

```yaml
- name: Install jq
  run: |
    sudo apt-get update -qq
    sudo apt-get install -y -qq jq

- name: Make scripts executable
  run: chmod +x scripts/*.sh

- name: Run smoke test
  run: bash plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh

- name: Validate cli-to-plugin manifest
  run: ./scripts/validate.sh plugins/cli-to-plugin
```

---

### SHOULD FIX

**`plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh:82` — Variable `mkdir_result` is a misnomer; carries `mktemp` exit code**

This was flagged in the Wave 4 critic review and remains unfixed:

```bash
TMP="$(mktemp -d /tmp/cli-to-plugin-smoke-XXXX)"
mkdir_result=$?
if [ $mkdir_result -ne 0 ] || [ ! -d "$TMP" ]; then
```

`mktemp -d` creates the directory — it is not `mkdir`. The variable name `mkdir_result` is misleading to readers and debuggers. Rename to `mktemp_result`:

```bash
TMP="$(mktemp -d /tmp/cli-to-plugin-smoke-XXXX)"
mktemp_result=$?
if [ $mktemp_result -ne 0 ] || [ ! -d "$TMP" ]; then
```

---

**`plugins/cli-to-plugin/commands/cli-to-plugin.md:70-88` — Step 1 comment "no live CLI needed" obscures that `uv` is required when `--override` is set with `--from-tree`**

The playbook states: "Skip this step entirely when `--from-tree` is set (no live CLI needed)."

Pre-Step-0 runs `uv run --with pyyaml -c ...` for override file validation, which happens before Step 1 regardless of `--from-tree`. So `uv` IS required when `--from-tree` and `--override` are combined — but the user never sees the clean "HALT: uv is not installed. Install it: ..." message from Step 1. Instead they see a raw `uv: command not found` shell error.

Fix the Step 1 comment to reflect this:

```markdown
## Step 1 — Preflight

Skip CLI-existence check when `--from-tree` is set (no live CLI needed).
Note: `uv` is always required because it is called in Pre-Step-0 (override
validation) and Step 9 (output validation). Always check for `uv`:

```bash
command -v uv
```

- If `uv` is not found: **halt** with the install message.
- Only check for `<cli-name>` when `--from-tree` is NOT set.
```

---

**`plugins/cli-to-plugin/tests/fixtures/README.md:30-38` — Pseudocode uses `==` (full equality) instead of subset semantics actually implemented**

This was flagged in the Wave 3 fix critic review and remains unfixed. The README shows:

```python
assert actual[name] == exp_group   # ← full equality
```

But `conftest.py:assert_subset_match` checks name, path, and summary only, and explicitly allows extra fields and extra commands. The pseudocode contradicts the actual behavior and would mislead future test authors into thinking the expected fixtures must match the full discovered output.

Fix by updating the pseudocode to reflect subset semantics:

```python
# deep-compare only the curated fields (name, path, summary)
assert actual[name]["name"] == exp_group["name"]
assert actual[name]["path"] == exp_group["path"]
if "summary" in exp_group:
    assert actual[name].get("summary") == exp_group["summary"]
# extra groups and commands in actual output are allowed
```

---

**`plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh:34` — `EXPECTED_GROUPS` hardcoded; diverges silently from fixture**

```bash
EXPECTED_GROUPS=(pr issue repo workflow release gist)
```

These 6 groups are copied from `gh-help-tree.expected.json` but are not read from it. If the fixture is updated (e.g., a group added or renamed), the smoke test continues checking the old hardcoded list and never catches the divergence. Reading from the fixture at runtime would keep them in sync:

```bash
EXPECTED_GROUPS=()
while IFS= read -r group; do
    EXPECTED_GROUPS+=("$group")
done < <(jq -r '.groups[].name' "$FIXTURE" | sed 's/^gh-//')
```

Or, simpler, check that every group in the fixture has a corresponding skill without hardcoding:

```bash
while IFS= read -r group_name; do
    skill_md="$OUT/skills/gh-$group_name/SKILL.md"
    ...
done < <(jq -r '.groups[].name' "$FIXTURE")
```

---

**`plugins/cli-to-plugin/.claude-plugin/plugin.json` — Missing `LICENSE` file produces a validator WARN on every `validate.sh` run**

`validate.sh` emits `WARN: license field set to 'MIT' but no LICENSE file found`. The plugin manifest declares `"license": "MIT"` but no `LICENSE` file exists in `plugins/cli-to-plugin/`. Per CLAUDE.md: "ALWAYS bump the version whenever ANY file changes." The missing LICENSE is a known warning but it clutters the validate output on every run and should be resolved before v1 release.

Fix: add `plugins/cli-to-plugin/LICENSE` with MIT text, or remove the `license` field from `plugin.json` if a LICENSE file is genuinely not intended.

---

### CONSIDER

**`plugins/cli-to-plugin/commands/cli-to-plugin.md:37` — Inline `uv run -c` in Pre-Step-0 uses YAML path variable without quoting**

```bash
uv run --with pyyaml -c "import yaml, sys; yaml.safe_load(open('$OVERRIDE_PATH'))"
```

If `$OVERRIDE_PATH` contains spaces or single quotes, this call will fail or behave unexpectedly. This is a playbook (Claude follows it), not a shell script Claude evaluates directly, so the risk is lower — but Claude should be instructed to quote the path correctly when emitting the Bash invocation.

---

**`plugins/cli-to-plugin/scripts/validate-output.sh` — Does not check `uv` version; `jsonschema` behavior varies across `python -m jsonschema` versions**

The script invokes `uv run --with jsonschema python -m jsonschema --instance`. The `--instance` flag was added in `jsonschema` 4.x. If `uv` resolves an older cached version, the schema check silently skips or fails with a confusing error. Adding `--with jsonschema>=4.0` pins the minimum:

```bash
uv run --with "jsonschema>=4.0" python -m jsonschema --instance "$plugin_json" "$PLUGIN_SCHEMA"
```

---

**`plugins/cli-to-plugin/commands/cli-to-plugin.md` — Step 8b description field format instruction could produce double-period**

The playbook says:

```
- `description` — `Use the '<cli-name>' CLI through Claude — <condensed cli.summary>.`
  (Strip any trailing punctuation from `cli.summary` before appending the period...)
```

This instruction is correct and sufficient. However, the spec example shows the `gh` description as:
`"Use the \`gh\` CLI through Claude — pull requests, issues, repos, workflows, and releases."`

The `cli.summary` from the fixture is "Work seamlessly with GitHub from the command line." — if Claude condenses this and does not strip the trailing period before appending, you get a double period. The instruction is there but could be made more explicit with a concrete before/after example.

---

### NIT

**`plugins/cli-to-plugin/commands/cli-to-plugin.md` — `--regen` description says "hint that regeneration is expected" but it's a behavioral flag, not a hint**

```
- `--regen` — hint that regeneration is expected (triggers the regeneration flow automatically without prompting twice)
```

"Hint" undersells it. `--regen` is a functional flag that bypasses the prompt. "Skip the regeneration-mode prompt and go straight to diff-and-merge" is more accurate.

---

**`plugins/cli-to-plugin/scripts/override.py:main()` — `main()` is marked `# pragma: no cover` but is exercised by the playbook**

The `main()` function and `__name__ == "__main__"` block both have `# pragma: no cover`. This is correct for the test environment (tests import `merge_override` directly) but means the CLI argument-parsing paths are never tested. This is a known gap, not a regression.

---

**`plugins/cli-to-plugin/scripts/discover.py` — `_is_flag_section` contains `"GLOBAL OPTIONS"` twice**

```python
def _is_flag_section(heading: str) -> bool:
    upper = heading.upper().rstrip(":").strip()
    return upper in {
        "FLAGS", "OPTIONS", "GLOBAL FLAGS", "GLOBAL OPTIONS",
        "INHERITED FLAGS", "INHERITED OPTIONS",
        "OPTIONAL FLAGS", "REQUIRED FLAGS",
        "GLOBAL OPTIONS",   # ← duplicate
    }
```

Python sets deduplicate silently, so no bug — but the duplicate entry is a copy-paste artifact worth removing.

---

## Acceptance Criteria Scorecard

Evaluating the 10 spec acceptance criteria from code alone (no runtime execution):

| # | Criterion | Status | Evidence |
|---|-----------|--------|---------|
| 1 | `discover.py` parses `gh`/`kubectl`/`docker` fixtures vs expected JSON | PASS | `test_discover.py` fixture tests with `assert_subset_match` cover all three; fixtures are real captures from live CLIs |
| 2 | `/cli-to-plugin gh` produces plugin passing `validate.sh` + `test-path-resolution.sh` | LIKELY PASS | `validate-output.sh` calls both validators from Step 9; playbook generates required `plugin.json`, `README.md`, and `skills/` structure; validate.sh runs cleanly on the generator itself |
| 3 | Every generated SKILL.md validates against `schemas/skill.schema.json`; every `plugin.json` against `schemas/plugin.schema.json` | LIKELY PASS | validate-output.sh Check 4 validates SKILL.md frontmatter; Check 3 validates plugin.json; playbook instructs hyphenated frontmatter keys matching the skill schema |
| 4 | Override file honors `skip`, `description`, `extra_guidance`, `meta_skills` | PASS | All four behaviors are implemented in `override.py` and covered by `test_override_merge.py` |
| 5 | Regeneration asks user (overwrite / diff-and-merge / cancel) | PASS | Step 0 of playbook implements all three paths; `--regen` auto-selects diff-merge |
| 6 | `--from-tree <path>` skips discovery | PASS | Step 1 skips CLI check; Step 2 branches to `cp` instead of discover; correctly documented |
| 7 | `uv` preflight halts cleanly with install hint | PASS | Step 1 emits the exact install command specified in spec; also implicitly caught by Pre-Step-0 if `--from-tree` is used with `--override` (though without the clean message — see SHOULD FIX) |
| 8 | Generated `gh` plugin works in a fresh session | DEFERRED | Sentinel assessment needed; smoke test SKIPs in CI without `claude` on PATH |
| 9 | `discover.py` coverage ≥ 90% | PASS | Previously verified at 90.95%; test suite is comprehensive |
| 10 | Manual smoke matrix (gh, kubectl, docker) | DEFERRED | Release gate, not a code review item |

---

## End-to-End Flow Trace

**Does override.py get called correctly?** Yes. The playbook in Step 2 shows:

```bash
uv run --with pyyaml --script ${CLAUDE_PLUGIN_ROOT}/scripts/override.py \
  --tree /tmp/cli-to-plugin-tree.json \
  --override <override-path> \
  > /tmp/cli-to-plugin-tree-merged.json
```

`override.py`'s `main()` function exists and accepts `--tree` and `--override` flags via argparse. The `--with pyyaml` flag is redundant (pyyaml is declared in PEP 723 dependencies) but harmless.

**Does discover.py output feed cleanly into skill synthesis?** Yes. The tree's `groups[].name`, `groups[].path`, `groups[].summary`, `groups[].commands`, and `groups[].flags` are all available to Claude in Step 4. The `groups[].extra_guidance` field written by `override.py` is picked up by Step 4's instruction to append it as `## Notes`.

**Does Step 8 generate a schema-valid `plugin.json`?** Yes. The playbook synthesizes all required and recommended fields:
- `name` (required) — from `cli.name`
- `version` — `"1.0.0"`
- `description` — synthesized from `cli.summary`, 10–500 chars
- `author` — object form with `name` from git config
- `keywords` — array of strings
- `license` — `"MIT"`

All fields match the schema. The `plugin.json.example` template passes `jsonschema.validate` against `schemas/plugin.schema.json` (verified).

---

## Wave 5 Specific Assessment

**CI workflow** — Correct trigger paths, pinned to `ubuntu-latest`, uses `astral-sh/setup-uv@v3`, runs the three expected checks. The `@v3` tag is a floating mutable tag (not a SHA pin), which is standard for this action and acceptable for an internal tools repo, though SHA pinning is the stricter best practice. The step ordering bug (`jq` after smoke test) is a MUST FIX.

**README "Available Plugins" table** — `cli-to-plugin` appears in the "Development & Workflow" section. Alphabetically within that section, the order is: cli-to-plugin, fakoli-crew, fakoli-flow, fakoli-state, marketplace-manager. This is correct. The one-line description is accurate.

**marketplace.json** — Entry is present with `category: "utilities"`. CLAUDE.md lists `utilities` as a valid category. The description matches `plugin.json` verbatim. The `source` field uses `"./plugins/cli-to-plugin"` (correct format). Consistent across all three sync sources.

**generate-index.sh category-preservation fix** — The goal is correct: preserve the `category` field from `marketplace.json` when regenerating, because `category` is not present in `plugin.json`. The implementation works correctly for existing plugins. The regression (MUST FIX) is that new plugins not yet in `marketplace.json` are silently dropped from the marketplace output when `generate-index.sh` runs. The fix is a one-line `// null` change in the jq expression.

---

### VERDICT

**Verdict: MUST FIX**

Three MUST FIX items block release:

1. `generate-index.sh:269` — Silent data-loss regression: new plugins not pre-registered in `marketplace.json` are dropped from marketplace sync output. All existing plugins are unaffected, but the next plugin onboarded without a manual `marketplace.json` edit first will silently disappear.

2. `validate-output.sh:185-208` — Shell injection in SKILL.md frontmatter validation: triple-single-quote in any generated skill's frontmatter breaks the Python string and causes arbitrary code execution. The fix is to write frontmatter to a temp file before passing it to Python.

3. `.github/workflows/cli-to-plugin-tests.yml:41` — `jq` installed after the step that calls validators requiring `jq`. Currently masked by `claude` being absent from CI PATH. The ordering is a latent failure that will fire when a `claude` binary is available in CI.

The plugin's core code is solid. `discover.py` is well-structured with proper error handling, bounds enforcement, and ANSI stripping. `override.py` is clean, correctly implements all four override behaviors, and handles edge cases (suggestions for typos, warn-not-halt for unknown commands). The test suite is thorough, the templates use the correct hyphenated frontmatter keys, and the playbook is logically structured with correct atomic-write discipline throughout. Once the three MUST FIX items are addressed, this plugin is ready for release.
