# Critic Gate — Wave 2 Review

**Scope:**
- `/plugins/cli-to-plugin/scripts/discover.py`
- `/plugins/cli-to-plugin/scripts/validate-output.sh`
- `/plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json`
- `/plugins/cli-to-plugin/tests/fixtures/kubectl-help-tree.expected.json`
- `/plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json`
- `/plugins/cli-to-plugin/tests/fixtures/README.md`
- `/plugins/cli-to-plugin/tests/fixtures/gh-help-raw/` (7 files)
- `/plugins/cli-to-plugin/tests/fixtures/kubectl-help-raw/` (5 files)
- `/plugins/cli-to-plugin/tests/fixtures/docker-help-raw/` (5 files)
- `/plugins/cli-to-plugin/tests/fixtures/pathological/` (5 files)
- `/plugins/cli-to-plugin/schemas/help-tree.schema.json`
- `/docs/plans/agent-task4-status.md`, `agent-task5-status.md`, `agent-task6-status.md`

**Reviewed by:** critic
**Date:** 2026-05-24

---

## MUST FIX

---

### 1. discover.py does not implement the flatten convention for deep groups

**File:** `scripts/discover.py:438–453` (walk, recursion branch)

**Issue:** The schema's `groups` description mandates that deep command paths be flattened to top-level sibling entries: "A deep group like 'kubectl create deployment' appears here as `{name: 'create-deployment', path: ['create', 'deployment']}` — a sibling of `{name: 'pr', path: ['pr']}, not a child of any 'create' entry`."

`discover.py` does the opposite: when recursing into a sub-group at depth+1, it takes the returned group dict and promotes it as a **command entry on the parent**, not as a sibling group at the top level. The returned sub_group is stored as `{name: sub_name, path: cmd_path}` inside the parent `group["commands"]`, then discarded as a group-level sibling. Nothing ever adds the sub-group back to the top-level `groups[]` array in `discover()`.

This is confirmed by `task5-status.md`: "Sub-groups from deeper recursion are stored as command entries inside their parent group, not as top-level siblings — this is correct per the schema's description." This claim is wrong. The status author misread the schema: path length is used to express nesting _within the flat array_, not to opt out of flatness. The schema example is explicit — `create-deployment` is a sibling, not a child.

**Consequence:** Wave 3 `test_kubectl_fixture_validates_against_schema` will compare discover.py output to `kubectl-help-tree.expected.json`, which correctly has `create-deployment` as a top-level group with `path: ["create", "deployment"]`. discover.py would never produce this entry. Test divergence is guaranteed.

**Fix:** After collecting sub_group in the recursion branch, push the sub_group into the top-level groups list in addition to creating the leaf command entry. This requires passing a mutable `groups_accumulator` list through the walk. Alternatively, flatten in `discover()` by post-processing: after all groups are collected, walk each group's `commands[]` and for any command that itself has sub-commands (per its own help walk), promote it to a sibling group with the joined path.

```python
# In discover(), after the walk() call:
def _flatten_to_groups(cli: str, walked_group: dict, groups: list[dict]) -> None:
    """Recursively promote nested groups to the flat top-level groups list."""
    groups.append(walked_group)
    for cmd in walked_group.get("commands", []):
        if cmd.get("commands"):  # has subcommands -> is itself a group
            flat_name = "-".join(cmd["path"])  # "create-deployment"
            sub_group = {
                "name": flat_name,
                "path": cmd["path"],
            }
            if cmd.get("summary"):
                sub_group["summary"] = cmd["summary"]
            if cmd.get("commands"):
                sub_group["commands"] = cmd["commands"]
            groups.append(sub_group)
```

This is a design-level fix that requires coordinating with the group walk structure.

---

### 2. Section detection is blind to kubectl and docker help formats — discover.py produces empty groups for both CLIs

**File:** `scripts/discover.py:171` (`_SECTION_RE`), `scripts/discover.py:180–187` (`_is_command_section`)

**Issue:** `_SECTION_RE = re.compile(r"^([A-Z][A-Z0-9 _/-]+)\s*$")` requires section headings to be entirely uppercase (plus digits, spaces, underscores, slashes, and hyphens). This matches `gh`'s headings (`CORE COMMANDS`, `FLAGS`) but completely misses `kubectl` and `docker`, which use Mixed-Case-With-Colon headings:

- `kubectl.txt`: `Basic Commands (Beginner):`, `Deploy Commands:`, `Available Commands:` — NONE match `_SECTION_RE`.
- `docker.txt`: `Common Commands:`, `Management Commands:`, `Global Options:` — NONE match.
- `docker-container.txt`: `Commands:`, `Global Options:` — NONE match.
- `kubectl-create.txt`: `Available Commands:`, `Options:` — NONE match.

When `parse_help_text` finds no sections, `sub_names` is empty, and `walk()` returns a group with no `commands[]`. In `discover()`, none of the top-level command names from `kubectl.txt` are parsed either (same reason), so `top_commands` is empty and `groups: []` is emitted.

**Confirmed by live test:**
```python
import re
_SECTION_RE = re.compile(r'^([A-Z][A-Z0-9 _/-]+)\s*$')
for heading in ['Basic Commands (Beginner):', 'Available Commands:', 'Commands:', 'Global Options:']:
    print(bool(_SECTION_RE.match(heading)))
# False, False, False, False
```

**Consequence:** If discover.py is run against real `kubectl` or `docker`, it emits `groups: []`. The kubectl and docker expected fixtures are hand-curated with sections populated — they could never be produced by running discover.py against the real binaries with the current section detection.

**Fix:** Extend `_SECTION_RE` and `_is_command_section` to handle:
1. Mixed-case headings ending with `:` (strip the colon before matching)
2. Patterns like `Foo Bar Commands:` → treat "Commands" suffix as a command section
3. `Available Commands:` → command section

```python
_SECTION_RE = re.compile(
    r"^([A-Z][A-Za-z0-9 _/()-]+?)\s*:?\s*$"
)

def _is_command_section(heading: str) -> bool:
    upper = heading.upper().rstrip(":").strip()
    if upper.endswith("COMMANDS") or upper.endswith("SUBCOMMANDS"):
        return True
    return upper in _COMMAND_SECTION_KEYWORDS
```

---

### 3. discover.py never emits `usage` or `flags` on command entries — fixture divergence on every leaf command

**File:** `scripts/discover.py:438–453` (recursion branch), `scripts/discover.py:213–214` (parse_help_text)

**Issue:** `parse_help_text()` extracts `parsed["usage"]` and `parsed["sections"]` (which includes flags). `walk()` uses the flags for collecting but explicitly discards them (`pass` at line 411–414). When building a command entry from a sub_group result, only `summary` and `raw_help` are transferred:

```python
cmd: dict = {
    "name": sub_name,
    "path": cmd_path,
}
if sub_group.get("summary"):
    cmd["summary"] = sub_group["summary"]
if sub_group.get("raw_help"):
    cmd["raw_help"] = sub_group["raw_help"]
```

There is no `cmd["usage"] = ...` or `cmd["flags"] = ...`. The `group` dict itself never gets a `usage` key set. Parsed usage sits in a local variable and is never written to `group` or returned.

Every leaf command in all three expected fixtures (`gh-help-tree.expected.json`, `kubectl-help-tree.expected.json`, `docker-help-tree.expected.json`) has `"usage"` and `"flags"` fields. discover.py would produce none of them.

**Consequence:** Any test comparing discover.py output to these fixtures field-for-field will fail on every single command entry.

**Fix:** Store `usage` and `flags` on the group dict in `walk()`, then transfer them when building command entries:

```python
# In walk(), after parsing:
if parsed["usage"]:
    group["usage"] = parsed["usage"]
if flags:
    group["flags"] = flags

# When building cmd from sub_group:
if sub_group.get("usage"):
    cmd["usage"] = sub_group["usage"]
if sub_group.get("flags"):
    cmd["flags"] = sub_group["flags"]
```

Note: the schema's `command` definition allows `usage` (string) and `flags` (array of flag). The `group` definition does not have a `flags` field, but using it as an intermediate storage field that gets lifted to the command entry is fine since `group` has `additionalProperties` not set to false.

---

### 4. gh-help-tree.expected.json fixture claims 7 global_flags but discover.py would produce 2

**File:** `tests/fixtures/gh-help-tree.expected.json:9–46`

**Issue:** The fixture's `global_flags` array lists 7 flags: `--help`, `--version`, `--repo`, `--jq`, `--json`, `--template`, `--web`.

The raw fixture `gh-help-raw/gh.txt` contains only a `FLAGS` section with 2 entries: `--help` and `--version`. The other 5 flags (`--repo`, `--jq`, `--json`, `--template`, `--web`) appear in group-level help files (e.g., `gh-pr.txt`) under `INHERITED FLAGS`, not in the root help.

`discover.py` extracts global_flags from `root_parsed["sections"]` (the root `--help` only). It would produce `global_flags: [{"long": "--help", ...}, {"long": "--version", ...}]` — 2 entries, not 7.

**Consequence:** The `test_real_gh_fixture_matches_expected` test will fail on `global_flags` regardless of any other fixes.

**Fix:** Either:
- (A) Trim the fixture to match what discover.py actually produces (2 global flags), OR
- (B) Extend discover.py to parse INHERITED FLAGS from sub-group help and deduplicate into `global_flags`.

Option A is the correct immediate fix — the fixture should be the source of truth for what discover.py produces, not an aspirational ideal.

---

### 5. gh expected fixture has only 6 groups but discover.py walks 33 — no test strategy defined

**File:** `tests/fixtures/gh-help-tree.expected.json`, `tests/fixtures/gh-help-raw/` (7 files only)

**Issue:** The raw fixture directory covers 7 invocations: `gh --help` + 6 group help files. But `gh.txt` lists 31 top-level commands across CORE COMMANDS (11), GITHUB ACTIONS COMMANDS (3), ALIAS COMMANDS (1), and ADDITIONAL COMMANDS (16). `discover.py` would attempt to walk all 31.

The `README.md` says the test `test_real_gh_fixture_matches_expected` "drives discover.py with monkeypatched subprocess returning these files, then compares to `gh-help-tree.expected.json`." But for the 25 command groups not in the raw fixtures (`auth`, `browse`, `co`, `alias`, `api`, etc.), the monkeypatch has no file to return.

This is an unresolved test design gap that will block Wave 3:
- If monkeypatch returns empty stdout for unknown commands: discover.py warns and adds bare groups to output. Output will have 31 groups, not 6. Equality test fails.
- If monkeypatch raises for unknown commands: discover.py treats it as a timeout/error. Still produces bare groups for all 31.
- The fixture is not structured as a subset-check — it is a full equality target.

There are two valid resolutions:

**Option A (subset test):** Change the test strategy from full equality to subset assertion:
```python
actual = {g["name"]: g for g in discovered["groups"]}
expected = {g["name"]: g for g in expected_tree["groups"]}
for name, exp_group in expected.items():
    assert name in actual, f"expected group {name!r} not in output"
    # deep-compare the curated group only
    assert actual[name] == exp_group
```

**Option B (full fixture):** Add raw fixtures for all 31 groups (or a representative superset), and expand the expected JSON to match real discover.py output (after fixing issues 1–4). This is the higher-fidelity approach.

The README claims the test does a full comparison (`compares to gh-help-tree.expected.json`). If Wave 3 implements this literally, it will fail. This must be clarified before Wave 3 begins.

---

### 6. Flag regex misparses `[HOST/]OWNER/REPO` — wrong argument captured for `--repo`

**File:** `scripts/discover.py:81–91` (`_FLAG_RE`)

**Issue:** The ALL-CAPS arg pattern `\[?([A-Z][A-Z0-9_/:-]{1,})\]?` captures only `HOST/` (stops at `]`) from the argument text `[HOST/]OWNER/REPO`. The result:

- `argument` = `"HOST/"` (not `"[HOST/]OWNER/REPO"`)
- `description` starts with `"OWNER/REPO   Select another repository..."` (the unmatched tail leaks into the description)

The fixture expects `"argument": "[HOST/]OWNER/REPO"`.

The root cause: the regex only allows one bracketed token, so `[HOST/]` consumes the match and `OWNER/REPO` falls through to the description field.

**Fix:** Extend the argument capture to handle compound forms like `[HOST/]OWNER/REPO` by capturing everything up to the first multi-space separator:

```python
_FLAG_RE = re.compile(
    r"^\s+"
    r"(?:(-[a-zA-Z])(?:,\s*))?"
    r"(--[a-zA-Z][a-zA-Z0-9-]*)?"
    r"(?:\s+([^\s].*?))?"    # greedy-lazy capture stops at description separator
    r"(?:\s{2,}(.*?))?\s*$"  # 2+ spaces separates arg from description
)
```

Or more precisely, capture the argument as "anything that isn't a double-space separator". This is a structural change to the flag regex that should be validated against the full test corpus of gh, kubectl, and docker flag lines.

---

## SHOULD FIX

---

### 7. Shell variable injection in validate-output.sh YAML frontmatter extraction

**File:** `scripts/validate-output.sh:185–208`

**Issue:** The script passes SKILL.md frontmatter content through shell variable expansion into a Python `-c` string:

```bash
frontmatter=$(awk ... "$skill_file")
skill_validate_output=$(uv run ... python -c "
...
frontmatter = '''$frontmatter'''
...")
```

If `$frontmatter` contains `$(command)` or backtick expressions, bash expands them before Python runs. A SKILL.md with:
```yaml
description: $(cat /etc/passwd)
```
would execute `cat /etc/passwd` at validation time.

This is currently only a concern if the tool is used to validate third-party plugins (not just self-authored ones), but the tool is positioned as a generator + validator, and generated plugins from unknown CLIs could have unexpected content. The pattern also sets a bad precedent.

**Fix:** Write the frontmatter to a temp file and pass the path to Python, avoiding shell expansion entirely:

```bash
tmpfile=$(mktemp)
awk '/^---$/{c++; if(c==2) exit; next} c==1 {print}' "$skill_file" > "$tmpfile"
skill_validate_output=$(uv run --with jsonschema --with pyyaml python -c "
import sys, json, yaml, jsonschema
with open('$tmpfile') as f:
    data = yaml.safe_load(f) or {}
with open('$SKILL_SCHEMA') as f:
    schema = json.load(f)
try:
    jsonschema.validate(instance=data, schema=schema)
    print('OK')
except jsonschema.ValidationError as e:
    print(f'Schema violation: {e.message}', file=sys.stderr)
    sys.exit(1)
" 2>&1)
rm -f "$tmpfile"
```

---

### 8. discover.py does not distinguish leaf commands from command groups — all top-level entries become groups

**File:** `scripts/discover.py:582–605` (the top-level walk loop in `discover()`)

**Issue:** Every entry in a top-level commands section is walked unconditionally. If `gh browse --help` returns help text with no COMMANDS section (it's a leaf command that opens a browser), discover.py still emits it as a group:
```json
{"name": "browse", "path": ["browse"], "summary": "Open repositories..."}
```

Similarly, `co` (an alias for `pr checkout`) becomes a group. These are leaf commands, not groups. The schema's `groups` description says "Command groups discovered by walking the help tree" — a leaf command with no subcommands is not a group.

**Consequence:** For `gh`, 33 groups are emitted (31 commands + the root walk + some extra), many of which are leafs. The conceptual pollution of groups[] with leaf entries will confuse Wave 3 synthesis: the playbook generates one SKILL.md per group; emitting a skill for `co` (alias) or `browse` (leaf) produces noise.

**Fix:** After walking a top-level entry, only promote it to `groups[]` if it has `commands[]` (i.e., had subcommands). Bare groups with no commands are leaf commands and should not appear in the groups array — or should appear in a separate `top_level_commands` array for synthesis to use differently:

```python
if group is not None and group.get("commands"):
    groups.append(group)
elif group is not None:
    # Leaf command — emit with a note for synthesis
    leaf_cmd = {"name": group["name"], "path": group["path"]}
    if group.get("summary"):
        leaf_cmd["summary"] = group["summary"]
    leaf_commands.append(leaf_cmd)
```

This is a SHOULD FIX because the schema does not enforce that groups must have commands (it's optional), and discover.py's current behavior is technically schema-valid. But it breaks the downstream synthesis contract.

---

### 9. discover.py does not extract `homepage` from help text — fixture has homepage, engine never sets it

**File:** `scripts/discover.py:556–566` (cli_info construction)

**Issue:** `gh-help-tree.expected.json` has `"homepage": "https://cli.github.com/manual"` and `docker-help-tree.expected.json` has `"homepage": "https://docs.docker.com/go/guides/"`. These URLs appear in the raw help text:
- `gh.txt`: `Read the manual at https://cli.github.com/manual`
- `docker.txt`: `For more help on how to use Docker, head to https://docs.docker.com/go/guides/`

`discover.py` builds `cli_info` with only `name`, `binary`, `summary`, and `version`. It never parses homepage URLs from the help text. The schema allows `homepage` as a URI-format field.

**Fix:** Add a URL extraction pass in `parse_help_text` or in `discover()`:

```python
import re
_URL_RE = re.compile(r'https?://[^\s<>"\']+')
for line in clean_root.splitlines():
    m = _URL_RE.search(line)
    if m:
        cli_info.setdefault("homepage", m.group(0))
        break  # take the first URL found
```

This is imprecise (might capture the wrong URL) but better than nothing. Alternatively, the test fixtures should remove `homepage` if discover.py will not produce it.

---

### 10. `deep-recursion.txt` fixture is a documentation+data hybrid — tests cannot use it as a single monkeypatch source

**File:** `tests/fixtures/pathological/deep-recursion.txt`

**Issue:** The file mixes comment lines (`# ---- foo --help (depth 0) ----`) with actual help text segments for 5 different invocations: `foo --help`, `foo bar --help`, `foo bar baz --help`, `foo bar baz qux --help`, `foo bar baz qux quux --help`. All segments are concatenated in one file.

A test that monkeypatches `subprocess.run` to return the contents of this file for ALL invocations would give the same text to every call, defeating the purpose. The test must return DIFFERENT slices depending on which command is being invoked. There is no mechanism in the fixture file itself for this (no delimiters that tests can parse to extract segments).

**Fix:** Either:
- (A) Split into separate files: `deep-foo.txt`, `deep-foo-bar.txt`, `deep-foo-bar-baz.txt`, etc., OR
- (B) Add machine-parseable section markers (e.g., `# === INVOCATION: foo --help ===`) that test helpers can parse to extract the right segment per invocation.

Option A is cleaner and consistent with the other raw fixture directories.

---

### 11. `jsonschema` CLI is deprecated — validate-output.sh will start emitting deprecation warnings

**File:** `scripts/validate-output.sh:133–135`

**Issue:** `uv run --with jsonschema python -m jsonschema ...` emits:
```
DeprecationWarning: The jsonschema CLI is deprecated and will be removed in a future version. Please use check-jsonschema instead...
```

This warning goes to stderr, which the script captures via `2>&1`. The warning string does not contain `ERROR:` or `WARN:` so it does not affect the pass/fail counters, but it pollutes the output and will eventually break when jsonschema removes the CLI.

**Fix:** Suppress the deprecation warning at the invocation site:

```bash
plugin_schema_output=$(uv run --with jsonschema python -W ignore::DeprecationWarning \
    -m jsonschema --instance "$plugin_json" "$PLUGIN_SCHEMA" 2>&1)
```

Or migrate to `check-jsonschema` (a separate installable) which is the recommended replacement.

---

## CONSIDER

---

### 12. `_SECTION_RE` false positive on `USAGE COMMANDS`

**File:** `scripts/discover.py:171–187`

**Issue:** A section heading `USAGE COMMANDS` would match `_SECTION_RE` and `_is_command_section` (ends with COMMANDS). No known CLI uses this heading, but if one did, it would cause USAGE examples to be parsed as commands. Low risk but worth documenting.

**Recommendation:** Add `USAGE` and `LEARN MORE` and `EXAMPLES` to an explicit exclusion list before the `endswith("COMMANDS")` check:

```python
_NON_COMMAND_SECTIONS = {"USAGE", "EXAMPLES", "LEARN MORE", "HELP TOPICS", "ARGUMENTS"}

def _is_command_section(heading: str) -> bool:
    upper = heading.upper().strip()
    if upper in _NON_COMMAND_SECTIONS:
        return False
    if upper.endswith("COMMANDS") or upper.endswith("SUBCOMMANDS"):
        return True
    return upper in _COMMAND_SECTION_KEYWORDS
```

---

### 13. `raw_help` fallback condition is too narrow

**File:** `scripts/discover.py:484–486`

**Issue:** `raw_help` is attached only if `not sub_names and not parsed["summary"]`. If a group has a summary but no parseable subcommands (e.g., `gh auth` which has a summary "Authenticate gh and git with GitHub" but uses section headings like `GENERAL COMMANDS`), neither condition triggers — so `raw_help` is not attached, and the group has no `commands[]` and no `raw_help`. The group is structurally empty beyond `name` and `path`.

**Recommendation:** Attach `raw_help` whenever `not sub_names`, regardless of whether a summary was found:

```python
if not sub_names:
    group["raw_help"] = clean
```

---

### 14. Pathological fixture gap — no fixture for invalid UTF-8 bytes

**File:** `tests/fixtures/pathological/` (directory)

**Issue:** The spec's error-handling section mentions `UTF-8 decode with errors="replace"`. There is no fixture that contains raw non-UTF-8 bytes (e.g., Latin-1 sequences that are invalid in UTF-8). The `ansi-codes.txt` fixture covers ANSI, but the replacement-character path in `run_help()` line 57 (`errors="replace"`) is never exercised.

**Recommendation:** Add `tests/fixtures/pathological/invalid-utf8.bin` — a binary file with known invalid UTF-8 bytes embedded in otherwise valid help text. This is a simple `echo -e '\x80\x81 bad bytes' > file` artifact.

---

## NIT

---

### 15. `discover.py:484` — `raw_help` attached when both `sub_names` and `summary` are absent, but the condition should say "opaque help" more clearly

**File:** `scripts/discover.py:484`

The comment `# If we could not parse any structure` is accurate but the condition `not sub_names and not parsed["summary"]` is confusing — a group with a summary but no commands (like `gh browse`) would neither attach `raw_help` nor have `commands[]`. Add a comment explaining this is intentional: browse-type leaves are expected to have only `summary`.

---

### 16. `validate-output.sh` reports `0 errors, 4 warnings` for validate.sh on the generator itself

**File:** `scripts/validate-output.sh`, status note in `agent-task6-status.md`

The 4 warnings from validate.sh are: missing README.md, CHANGELOG.md, LICENSE file, and no components. The `README.md` and `LICENSE` warnings are expected to be resolved in Wave 4/5 tasks. The "no components" warning is misleading — the plugin DOES have components (commands/, scripts/), but validate.sh may not recognize scripts/ as a component directory. This will produce noise in any CI run. No action required before Wave 3, but document that these warnings are expected and tracked.

---

## Verdict: MUST FIX

Six MUST FIX items block Wave 3 from succeeding:

1. **No flatten convention** — discover.py never promotes deep sub-groups to top-level siblings. The kubectl expected fixture requires this. Test will fail.
2. **Section detection incompatible with kubectl/docker** — Mixed-case section headings are not parsed. discover.py produces `groups: []` for kubectl and docker.
3. **Missing `usage` and `flags` on command entries** — Both are parsed but never written to the output dict. Every leaf command in every fixture has these fields.
4. **Incorrect global_flags count** — Fixture claims 7 global flags; discover.py would produce 2. Fixture must be corrected to match actual discover.py output after other fixes.
5. **Fixture vs. engine divergence on group count** — 6-group expected fixture vs. 33-group real output with no defined test strategy. Wave 3 cannot write `test_real_gh_fixture_matches_expected` without resolving whether to use equality or subset comparison.
6. **Flag regex misparsing compound argument forms** — `[HOST/]OWNER/REPO` becomes `HOST/` with `OWNER/REPO` leaking into the description.

Items 1–3 are code bugs in discover.py that require implementation work. Items 4–5 are fixture correctness issues that require either correcting the fixture or changing the test strategy. Item 6 is a regex precision bug.

The validate-output.sh script is structurally sound: no `set -e`, correct path resolution via `SCRIPT_DIR`, correct tool choices (uv+jsonschema over ajv), correct exit code propagation, and the YAML frontmatter extraction logic is correct for well-formed SKILL.md files. The shell injection issue (SHOULD FIX #7) is real but low-risk for the current use case.

The pathological fixtures are well-chosen and mostly correct. The `ansi-codes.txt` has real ESC bytes (confirmed by hexdump). The `empty-stdout.txt` is truly 0 bytes. The `timeout.sh` is executable and sleeps 6 seconds. The only structural problem is `deep-recursion.txt` (SHOULD FIX #10), which requires splitting into per-invocation files before Wave 3 test authors can use it.
