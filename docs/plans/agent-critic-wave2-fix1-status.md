# Critic Gate — Wave 2 Fix Cycle Review

**Scope:**
- `plugins/cli-to-plugin/scripts/discover.py` (heavily modified)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json`
- `plugins/cli-to-plugin/tests/fixtures/kubectl-help-tree.expected.json`
- `plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json`
- `plugins/cli-to-plugin/tests/fixtures/README.md`
- `plugins/cli-to-plugin/tests/fixtures/pathological/deep-foo*.txt` (4 new files)

**Reviewed by:** critic
**Date:** 2026-05-24

---

## Prior MUST FIX Resolution Status

### MUST FIX 1 — Flatten convention: RESOLVED

Implementation: `WalkState.groups_accumulator` field (`discover.py:401`), populated at `discover.py:558–573`. After each top-level group walk in `discover()`, the accumulator is appended to `top_level_groups` at `discover.py:728`. The accumulator is reset before each top-level walk (`discover.py:719`).

Verified by simulation: running discover against `deep-foo.txt` fixtures produces `groups: [bar, bar-baz, top]` — `bar-baz` appears as a sibling of `bar`, not nested. Deep flat name uses `"-".join(sub_path).lower()`. No double-counting: the flat_group in accumulator and the cmd entry in parent's `commands[]` reference the same path but serve different roles (the former is the expanded view, the latter is the reference entry in parent's listing). This is the schema's intended pattern.

One observation: the flat_group pushed to accumulator copies `commands` from `sub_group` (`discover.py:572`), but does NOT re-attach `raw_help`. This is correct — if a group has `commands`, it was successfully parsed and `raw_help` is not needed.

---

### MUST FIX 2 — Section detection for kubectl/docker: RESOLVED WITH CAVEAT

New `_SECTION_RE` at `discover.py:229` accepts mixed-case headings with optional trailing colons. Confirmed:
- `Basic Commands (Beginner):` → matches → `_is_command_section()` strips `(Beginner)`, checks suffix → True
- `Available Commands:` → matches → suffix COMMANDS → True
- `Management Commands:` → matches → True
- `Global Options:` → matches → `_is_flag_section()` recognizes `GLOBAL OPTIONS` → True
- `CORE COMMANDS` → still matches → True
- `FLAGS` → still matches → True

Verified live: kubectl parse produces 8 command sections (42 commands), docker produces 4 command sections. Section detection for both CLIs is now functional.

**CAVEAT (SHOULD FIX — new finding):** The new regex produces false positives on multi-word prose lines that happen to start with a capital letter and end with no terminal punctuation. Two confirmed instances in the current fixture set:

1. `discover.py:229` — `'Edit the API resource before creating'` in `kubectl-create.txt` line 42 (a tab-indented flag description continuation) matches `_SECTION_RE` and is classified as `kind=other`. Confirmed by running `parse_help_text()` against `kubectl-create.txt`: the output includes `[other] 'Edit the API resource before creating' — 0 entries`.

2. `'A pull request can be supplied as argument in any of the following formats'` in `gh-pr.txt` similarly matches and becomes `kind=other`.

Both false positives land in `kind=other` (neither `_is_command_section()` nor `_is_flag_section()` matches them), so they do not corrupt command or flag parsing. However, they create spurious `other`-kind sections in the parse output and can cause a subsequent command-line entry to be stranded (if it appears after the false section, it will be associated with the `other` section and ignored). This is a known limitation of the regex approach.

---

### MUST FIX 3 — usage and flags on output: RESOLVED IN CODE, NOT FIXTURE-COMPLETE

Code fix confirmed:
- `discover.py:487`: `group["usage"] = parsed["usage"]` (when non-empty)
- `discover.py:504–505`: `group["flags"] = flags` (when non-empty)
- `discover.py:547–550`: `cmd["usage"]` and `cmd["flags"]` transferred from `sub_group`

The code correctly stores usage and flags on group dicts and transfers them to cmd entries. The harness report of 173 commands with usage and 173 with flags (against live `gh`) is consistent with this.

**NEW MUST FIX:** There is a summary fallback bug that directly undermines the fixture strategy. When `walk()` returns a `sub_group` that has no summary (because the mock returned empty stdout), the cmd entry gets no summary — even though the parent's command listing has a summary for that command. Code at `discover.py:544`:

```python
if sub_group.get("summary"):
    cmd["summary"] = sub_group["summary"]
# sub_summary is in scope but NEVER used as fallback here
```

The bare-leaf path at `discover.py:583` does use `sub_summary` as fallback. The max-depth leaf path at `discover.py:525` also uses `sub_summary`. Only the successful-sub-walk path at `discover.py:544` is missing the fallback.

Fix required:
```python
if sub_group.get("summary"):
    cmd["summary"] = sub_group["summary"]
elif sub_summary:
    cmd["summary"] = sub_summary
```

Without this fix, any command whose `--help` invocation returns empty stdout (the monkeypatch fallback for unknown fixtures) will produce a cmd entry with no `summary`, no `usage`, and no `flags` — even though the parent's listing had all of that information.

---

### MUST FIX 4 — global_flags count in gh fixture: RESOLVED FOR GH

`gh-help-tree.expected.json` now has exactly 2 flags (`--help`, `--version`) at the root. Verified by reading the fixture (lines 8–17) and confirming `gh.txt` root `FLAGS` section produces the same 2 entries via `parse_help_text()`.

The filter in `discover()` at `discover.py:693–695` correctly restricts global_flags to root-level headings in `{"FLAGS", "OPTIONS", "GLOBAL FLAGS", "GLOBAL OPTIONS"}`, excluding `INHERITED FLAGS`.

**NEW MUST FIX:** The `docker-help-tree.expected.json` `global_flags` array has two errors in the `--config` entry:

1. Missing `"argument": "string"` — actual `parse_help_text()` on `docker.txt` produces `{'long': '--config', 'argument': 'string', 'description': '...'}` because docker formats it as `--config string   description`. The expected fixture omits the `argument` field.

2. Truncated description — expected has `"description": "Location of client config files (default"`. Actual has `"description": "Location of client config files (default \"/Users/sdoumbouya/.docker\")"`. The expected description cuts off mid-sentence.

Additionally, the docker fixture only lists 3 global flags but `docker.txt`'s `Global Options` section has 11 flags. The README does not state that `global_flags` comparison uses subset semantics (only groups comparison is described as subset). If Wave 3 tests `assertEqual(actual['global_flags'], expected['global_flags'])` for docker, it will fail on count (11 vs 3) and on the `--config` field mismatch.

Fix: either (a) correct the `--config` entry and document that global_flags tests also use subset semantics, or (b) expand the docker fixture to include all 11 flags with accurate field values.

---

### MUST FIX 5 — Test strategy definition: PARTIALLY RESOLVED — ONE ITEM REMAINS MUST FIX

The README now documents subset matching on groups. The kubectl and docker expected fixtures were regenerated with bare leaf commands (no usage/flags) consistent with their fixture set.

**NEW MUST FIX:** The `gh-help-tree.expected.json` fixture is structurally incompatible with the test strategy described in the README. The fixture has rich command entries with `usage` and `flags` (e.g., `pr.commands[0]` has `usage: "gh pr list [flags]"` and `flags: [8 entries]`). But the raw fixture directory has NO depth-3 files — there is no `gh-pr-list.txt`, `gh-pr-create.txt`, etc. The only depth-2 files are `gh-pr.txt`, `gh-issue.txt`, etc. (group level). All depth-3 invocations (`gh pr list --help`, etc.) will return empty stdout from the monkeypatch fallback.

When mock returns empty stdout for `gh pr list --help`:
- `walk()` produces `sub_group = {name: 'list', path: ['pr', 'list'], raw_help: ''}`
- No summary, no usage, no flags
- The cmd entry in `pr.commands[]` becomes `{name: 'list', path: ['pr', 'list'], raw_help: ''}` (plus the summary fallback bug makes it even worse — no summary either)

The expected fixture has:
```json
{"name": "list", "path": ["pr", "list"], "summary": "...", "usage": "gh pr list [flags]", "flags": [8 entries]}
```

The actual output (with monkeypatched empty stdout) will have:
```json
{"name": "list", "path": ["pr", "list"], "raw_help": ""}
```

No subset matching semantics can bridge this gap: expected has `usage` and `flags` keys that actual doesn't have.

The `discovery.commands_walked: 28` in the expected fixture is also unreachable with the current fixture set. Root + 31 top-level groups + all subcommands of 6 fixture groups far exceeds 28.

Two valid resolutions (neither was completed):
- **Option A:** Add depth-3 fixture files (`gh-pr-list.txt`, `gh-pr-create.txt`, `gh-issue-list.txt`, etc.) for every command listed in the gh expected fixture
- **Option B:** Strip `usage` and `flags` from command entries in `gh-help-tree.expected.json`, making them bare leaf entries like the kubectl and docker fixtures

---

### MUST FIX 6 — Flag regex for compound arguments: RESOLVED

The new 2-step approach (`_FLAG_RE` at `discover.py:93–98`, `parse_flag_line()` at `discover.py:121–183`) correctly handles all required cases. Verified by running against actual flag line strings:

- `'-R, --repo [HOST/]OWNER/REPO   Select another repository...'` → `{short: '-R', long: '--repo', argument: '[HOST/]OWNER/REPO', description: 'Select another repository...'}`
- `'--state string   Filter by state...'` → `{long: '--state', argument: 'string', description: '...'}`
- `'-d, --draft   Filter by draft state'` → `{short: '-d', long: '--draft', description: 'Filter by draft state'}`
- `'--all-namespaces    If present...'` → `{long: '--all-namespaces', description: 'If present...'}`
- `'--json fields   Output JSON...'` → `{long: '--json', argument: 'fields', description: '...'}`

`[HOST/]OWNER/REPO` compound form matches `_ARG_PLACEHOLDER_RE` via the `\[[A-Z][A-Z0-9_/:\[\]-]*\][A-Z][A-Z0-9_/:\[\]-]+` branch at `discover.py:113`.

---

### SHOULD FIX 10 — Split deep-recursion.txt: RESOLVED

4 new files confirmed in `tests/fixtures/pathological/`: `deep-foo.txt`, `deep-foo-bar.txt`, `deep-foo-bar-baz.txt`, `deep-foo-bar-baz-qux.txt`. All 4 are clean per-invocation files with no comment lines. Content is correct: each level lists the next level's subcommands as expected.

`deep-recursion.txt` is still present. The README correctly notes it is kept for historical reference and should not be used as a monkeypatch source. This is a NIT.

---

## New Findings

---

### MUST FIX A — gh-help-tree.expected.json incompatible with test strategy (carries over from MUST FIX 5)

Covered in detail under MUST FIX 5 above. The gh fixture has rich commands that cannot be produced by the monkeypatch strategy the README documents. This is a blocker for Wave 3.

**File:** `tests/fixtures/gh-help-tree.expected.json` (entire file) and `tests/fixtures/gh-help-raw/` (missing depth-3 files)

**Fix Option A:** Add fixture files for every command in the expected fixture:
```
tests/fixtures/gh-help-raw/gh-pr-list.txt
tests/fixtures/gh-help-raw/gh-pr-create.txt
tests/fixtures/gh-help-raw/gh-pr-view.txt
tests/fixtures/gh-help-raw/gh-pr-checkout.txt
tests/fixtures/gh-help-raw/gh-pr-merge.txt
tests/fixtures/gh-help-raw/gh-issue-list.txt
... (20+ files)
```

**Fix Option B (faster):** Reduce gh expected fixture to bare leaf commands, matching the kubectl/docker approach:
```json
{"name": "list", "path": ["pr", "list"], "summary": "List pull requests in a repository"}
```
This requires re-curating the gh fixture to only include what monkeypatching actually produces.

---

### MUST FIX B — summary fallback missing at discover.py:544

Covered in detail under MUST FIX 3 above.

**File:** `scripts/discover.py:544`

**Fix:**
```python
if sub_group.get("summary"):
    cmd["summary"] = sub_group["summary"]
elif sub_summary:
    cmd["summary"] = sub_summary
```

---

### MUST FIX C — docker-help-tree.expected.json --config flag entry is wrong

Covered under MUST FIX 4 above.

**File:** `tests/fixtures/docker-help-tree.expected.json:10–12`

Current (wrong):
```json
{
  "long": "--config",
  "description": "Location of client config files (default"
}
```

Correct (from actual parse):
```json
{
  "long": "--config",
  "argument": "string",
  "description": "Location of client config files (default \"/Users/sdoumbouya/.docker\")"
}
```

Note: the full description includes the machine-specific default path. If that path varies across environments, the test should use partial matching for descriptions, or strip default paths from the fixture.

---

### SHOULD FIX D — docker cli.summary is empty in actual output (fixture disagrees)

**File:** `scripts/discover.py:338`, `tests/fixtures/docker-help-tree.expected.json:5`

Docker's help format puts the usage text inline on the `Usage:` line and the description on the next paragraph:
```
Usage:  docker [OPTIONS] COMMAND

A self-sufficient runtime for containers
```

`parse_help_text()` Pass 1 encounters `Usage:  docker [OPTIONS] COMMAND` and breaks (it starts with `USAGE`). No summary is captured. In Pass 2, the USAGE handler fires on that line, then takes the NEXT non-empty line as usage text: `"A self-sufficient runtime for containers"` becomes `result["usage"]` instead of the summary.

Result: `root_parsed["summary"] = ""` and `root_parsed["usage"] = "A self-sufficient runtime for containers"`. The cli_info dict does not get a `summary` key.

The expected fixture has `"summary": "A self-sufficient runtime for containers"` in `cli`.

Fix: When the USAGE line contains text beyond `Usage:` (i.e., the usage string is inline), extract it directly from the line rather than reading the next line. Then treat the following paragraph as summary:

```python
if stripped.upper().startswith("USAGE"):
    # Check for inline usage text: "Usage:  docker [OPTIONS] COMMAND"
    inline = re.sub(r'^usage:?\s*', '', stripped, flags=re.IGNORECASE).strip()
    if inline:
        result["usage"] = inline
        # Next non-empty paragraph becomes summary if not yet found
    else:
        # Usage text is on next line
        while i < n and not lines[i].strip(): i += 1
        if i < n: result["usage"] = lines[i].strip(); i += 1
    continue
```

This bug affects the docker expected fixture's `cli.summary` and `cli.usage` fields. The impact on tests depends on whether Wave 3 validates `cli` metadata equality. Schema validation passes regardless (both fields are optional).

---

### SHOULD FIX E — docker global_flags subset semantics not documented

**File:** `tests/fixtures/README.md:25–36`

The README's test strategy code shows subset matching only for `groups`. Docker's expected `global_flags` has 3 entries but actual output has 11. If Wave 3 tests compare `global_flags` with full equality, the docker test fails. The README must specify whether `global_flags` comparison also uses subset semantics.

---

### CONSIDER F — _SECTION_RE false positives on prose lines (degrade parser robustness)

**File:** `scripts/discover.py:229`

Two confirmed false positives in current fixtures: `'Edit the API resource before creating'` (from kubectl-create.txt) and `'A pull request can be supplied as argument in any of the following formats'` (from gh-pr.txt). Both get classified as `kind=other` and produce no harm to command/flag parsing in these specific cases.

However, if such a line appears inside a flag section, the current section is terminated and subsequent flag lines are silently ignored (they fall under the false `other` section). This is a correctness risk for CLIs with verbose flag descriptions.

A minimum heuristic to reduce false positives: require the heading to be at most N words (e.g., 6) before accepting it as a section heading. Most real section headings are 1–4 words.

---

### NIT G — deep-recursion.txt still present alongside split files

**File:** `tests/fixtures/pathological/deep-recursion.txt`

The README says it is kept "for historical reference." This is documented and intentional. However, its presence may confuse Wave 3 test authors who might try to use it. Consider renaming to `deep-recursion.txt.bak` or adding a one-line comment at the top: `# DEPRECATED — use deep-foo*.txt files for monkeypatching`. Since the file format doesn't support comments, deletion is cleaner.

---

## Verdict: MUST FIX

Three MUST FIX items from the prior wave are resolved (1, 2, 6). Three are partially or not fully resolved, and three new MUST FIX items surfaced:

**Prior MUST FIX items still blocking:**

- **MUST FIX 3 partial** — code emits usage/flags correctly, but summary fallback bug (`discover.py:544`) causes commands whose sub-walk returns empty stdout to lose the summary from the parent listing. This interacts with the fixture strategy.
- **MUST FIX 4 partial** — gh global_flags resolved, but docker expected fixture has wrong `--config` entry (missing `argument`, truncated description).
- **MUST FIX 5 partial** — subset test strategy is documented, but gh expected fixture commands have usage/flags that cannot be produced with the current fixture file set (no depth-3 files). The fixture is structurally incompatible with the test strategy.

**New MUST FIX items:**

- **MUST FIX A** — same as MUST FIX 5 partial above (gh fixture vs test strategy incompatibility)
- **MUST FIX B** — `discover.py:544` missing summary fallback to `sub_summary`
- **MUST FIX C** — docker expected `--config` global flag entry missing `argument` field and has truncated description

Wave 3 cannot write a passing `test_real_gh_fixture_matches_expected` test against this fixture set. The summary fallback bug means that even if depth-3 fixtures are added, summaries from parent listings are dropped whenever the sub-walk returns empty stdout. The docker `--config` fixture error is a direct incorrect value that will cause assertEqual failures.

The code itself (discover.py) is substantially improved. Flatten convention, section detection, flag parsing, and the usage/flags writeback are all correctly implemented. The gap is between what the code produces with the monkeypatch strategy and what the expected fixtures describe — and a single missing `elif sub_summary` line at `discover.py:544`.
