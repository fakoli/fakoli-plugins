# Wave 2 Fix Cycle — Status

**Agent:** welder
**Date:** 2026-05-24
**Scope:** discover.py fix cycle addressing 6 MUST FIX items from critic's Wave 2 review

---

## Verdict: DONE

All 6 MUST FIX items have been addressed. Both SHOULD FIX 10 extras have been resolved.

---

## MUST FIX Items

### MUST FIX 1 — Flatten convention in discover.py: DONE

**How:** Added a `groups_accumulator` list to `WalkState`. During the `walk()` recursion, when a sub-group is returned and it has `commands[]` (meaning it is itself a group, not a leaf), it is pushed into `state.groups_accumulator` with a hyphenated flat name derived from the path (e.g., `["repo", "autolink"]` → name `"repo-autolink"`). In `discover()`, after each top-level group walk completes, the accumulator contents are appended to `top_level_groups`. The accumulator is reset before each top-level group walk to avoid cross-contamination.

**Verification:** Running against live `gh` produces 5 deep groups as top-level siblings: `codespace-ports`, `repo-autolink`, `repo-deploy-key`, `repo-gitignore`, `repo-license`, each with `path` length > 1.

---

### MUST FIX 2 — Section detection for kubectl/docker: DONE

**How:** Replaced the strictly all-uppercase `_SECTION_RE = re.compile(r"^([A-Z][A-Z0-9 _/-]+)\s*$")` with a mixed-case pattern that accepts optional trailing colons:

```python
_SECTION_RE = re.compile(r"^([A-Z][A-Za-z0-9 _/()\-]+?)\s*:?\s*$")
```

Updated `_is_command_section()` to:
1. Strip trailing `:` before uppercasing
2. Strip parenthetical qualifiers (e.g., `(Beginner)`, `(Intermediate)`) before checking COMMANDS suffix
3. Added `_NON_COMMAND_SECTIONS` exclusion set for USAGE, EXAMPLES, LEARN MORE, etc.

Also updated `_is_flag_section()` to strip trailing `:` before comparison.

**Verification:** Running `parse_help_text()` against raw fixtures:
- gh: 4 command sections, 33 commands
- kubectl: 8 command sections, 42 commands  
- docker: 4 command sections, 57 commands
All three CLIs produce >= 3 command sections (previously kubectl/docker produced 0).

---

### MUST FIX 3 — Write `usage` and `flags` to output: DONE

**How:** In `walk()`:
1. After parsing, `group["usage"] = parsed["usage"]` is set when non-empty.
2. `group["flags"] = flags` is set when the flags list is non-empty.
3. When building a `cmd` dict from a `sub_group`, both `usage` and `flags` are transferred from `sub_group` to `cmd`.

**Verification:** Running against live `gh` with default `--max-depth 3` produces 173 commands with usage and 173 commands with flags. Schema validation passes (schema's `command` definition allows both fields).

---

### MUST FIX 4 — Correct global_flags count in gh-help-tree.expected.json: DONE

**How:**
1. In `discover()`, the `global_flags` extraction was narrowed to only pull from sections whose heading is in `{"FLAGS", "OPTIONS", "GLOBAL FLAGS", "GLOBAL OPTIONS"}` at the root level — excluding `INHERITED FLAGS` sections that appear in sub-help outputs.
2. The `gh-help-tree.expected.json` fixture was trimmed from 7 flags to 2 (`--help`, `--version`) — the only flags in `gh --help`'s `FLAGS` section.
3. The fixture's `homepage` field was also removed since `discover.py` does not extract homepage URLs.
4. The `README.md` documents this behavior: "global_flags reflects only what appears in root --help's FLAGS section. INHERITED FLAGS shown in sub-help outputs are not extracted into global_flags."

---

### MUST FIX 5 — Define test strategy for fixture/engine alignment: DONE

**How:** Updated `tests/fixtures/README.md` with a "Test Strategy" section that documents:
- Raw fixtures are partial captures, not full CLI mirrors
- Monkeypatched tests return fixture content for known invocations and empty stdout for unknown ones
- `discover.py` treats empty stdout as a valid "no subcommands" response
- Tests use **subset matching on groups**: every group in expected JSON must exist in actual output, extra groups are allowed
- Regenerated `kubectl-help-tree.expected.json` and `docker-help-tree.expected.json` to match what monkeypatched discovery actually produces (bare leaf commands for depth-2 kubectl/docker commands that have no fixture files)
- `create-deployment` flat group removed from kubectl expected fixture since no `kubectl create deployment --help` fixture exists

**Decisions made during regeneration:**
- kubectl expected fixture: contains `create` (17 bare leaf subcommands) and `apply` (3 bare leaf subcommands). Groups `get` and `describe` omitted since they have no subcommands in fixture set.
- docker expected fixture: contains `container`, `image`, `volume`, `network` with representative bare leaf subcommands (no flags since no depth-3 fixtures exist).

**Test driver approach (for Wave 3 test author):** The monkeypatch function should map `["kubectl"] + subcmd_path + ["--help"]` to the fixture file at `tests/fixtures/kubectl-help-raw/kubectl-{'-'.join(subcmd_path)}.txt`, returning `("", 0, False)` if the file doesn't exist. Same pattern for gh and docker.

---

### MUST FIX 6 — Fix flag regex for compound argument forms: DONE

**How:** Completely rewrote the flag parsing to use a clean 2-step approach:

1. `_FLAG_RE` now captures just `(short, long, remainder)` — the entire text after the flag names, stripped.
2. `parse_flag_line()` splits `remainder` on the first `\s{2,}` (2+ consecutive spaces) to separate argument from description:
   - If a 2-space separator is found: left part = candidate argument token, right part = description
   - If no separator: single-word remainder → check if it's an argument; multi-word → treat as description
3. `_ARG_PLACEHOLDER_RE` validates argument tokens: angle-brackets, ALL-CAPS (>= 2 chars), `[OPTIONAL]REQUIRED` compound form (for `[HOST/]OWNER/REPO`), and known lowercase type names.

**Verification test cases all pass:**
- `[HOST/]OWNER/REPO` → argument (MUST FIX 6 target case)
- `string` / `int` / `expression` → argument (known type names)
- `--draft Filter by draft state` → no argument (description = "Filter by draft state")
- `--all-namespaces    If present, list...` → no argument (description starts with "If")

---

## SHOULD FIX 10 — Split deep-recursion.txt into separate files: DONE

**How:** Created 4 separate fixture files in `tests/fixtures/pathological/`:
- `deep-foo.txt` — depth 0 (foo root)
- `deep-foo-bar.txt` — depth 1 (foo bar)
- `deep-foo-bar-baz.txt` — depth 2 (foo bar baz)
- `deep-foo-bar-baz-qux.txt` — depth 3, at depth limit

Each file contains clean help text for exactly one invocation level (no comment lines). The original `deep-recursion.txt` is preserved for historical reference. Wave 3 test authors should use the new per-depth files for monkeypatching.

Monkeypatch mapping: `["foo"] + path + ["--help"]` → `deep-foo{"-" + "-".join(path) if path else ""}.txt`.

---

## Items Out of Scope (per task brief)

- SHOULD FIX 7 (shell injection in validate-output.sh) — not in scope
- SHOULD FIX 8 (leaf command vs group distinction) — not in scope
- SHOULD FIX 9 (homepage extraction) — not in scope
- SHOULD FIX 11 (jsonschema CLI deprecation) — not in scope
- All CONSIDER/NIT items — not in scope

---

## Verification Results

All three mandatory verification commands from the task brief pass:

```
# 1. discover.py against live gh: commands with usage: 173, with flags: 173 → OK
# 2. All 3 expected fixtures validate against schema → OK
# 3. deep-*.txt file count: 5 (>= 4) → OK
```

Schema validation of `discover.py` output against `help-tree.schema.json`: PASS.

---

## Files Modified

- `/plugins/cli-to-plugin/scripts/discover.py` — flag regex rewrite, section detection fix, flatten convention, usage/flags on output
- `/plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json` — trim global_flags to 2, remove homepage
- `/plugins/cli-to-plugin/tests/fixtures/kubectl-help-tree.expected.json` — regenerate to match monkeypatched output (subset)
- `/plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json` — regenerate to match monkeypatched output, remove homepage
- `/plugins/cli-to-plugin/tests/fixtures/README.md` — test strategy documentation
- `/plugins/cli-to-plugin/tests/fixtures/pathological/deep-foo.txt` — new
- `/plugins/cli-to-plugin/tests/fixtures/pathological/deep-foo-bar.txt` — new
- `/plugins/cli-to-plugin/tests/fixtures/pathological/deep-foo-bar-baz.txt` — new
- `/plugins/cli-to-plugin/tests/fixtures/pathological/deep-foo-bar-baz-qux.txt` — new
