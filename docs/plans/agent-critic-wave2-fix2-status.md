# Critic Gate — Wave 2 Fix Cycle Review (Iteration 2)

**Scope:**
- `plugins/cli-to-plugin/scripts/discover.py` (two targeted edits)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json`
- `plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json`
- `plugins/cli-to-plugin/tests/fixtures/README.md`
- `plugins/cli-to-plugin/.claude-plugin/plugin.json`

**Reviewed by:** critic
**Date:** 2026-05-24

---

## Items Under Review

---

### MUST FIX B — discover.py:572 — Missing `elif sub_summary` fallback: RESOLVED

Confirmed at line 572–573:

```python
if sub_group.get("summary"):
    cmd["summary"] = sub_group["summary"]
elif sub_summary:
    cmd["summary"] = sub_summary
```

The pattern now mirrors the bare-leaf branch at lines 611–612 and the max-depth branch at lines 551–552. All three code paths (max-depth leaf, successful-sub-walk, failed-sub-walk) use `sub_summary` as fallback when `sub_group.get("summary")` is falsy. Verified by grepping for all `sub_summary` references — no asymmetry remains.

---

### MUST FIX C — docker-help-tree.expected.json `--config` entry incorrect: RESOLVED

Confirmed: the `--config` entry now contains `"argument": "string"` and the full untruncated description `"Location of client config files (default \"/Users/sdoumbouya/.docker\")"`. Schema validation passes. Total global_flags count is 11, matching what `parse_help_text()` produces against `docker.txt`. Verified live:

```
--config entry: {
  "long": "--config",
  "argument": "string",
  "description": "Location of client config files (default \"/Users/sdoumbouya/.docker\")"
}
Total global_flags count: 11
```

---

### MUST FIX A/5 — gh-help-tree.expected.json incompatible with test strategy: RESOLVED (Option B)

Confirmed: all 21 command entries across 6 groups contain only `name`, `path`, and `summary`. No `usage` or `flags` fields are present in any command entry in the gh fixture. Verified programmatically against all three fixtures (gh, kubectl, docker) — all pass the "bare entry" check.

---

### SHOULD FIX D — docker inline USAGE misread as usage text: RESOLVED

Confirmed by running `parse_help_text()` directly against `docker.txt`:

```
Docker: summary = 'A self-sufficient runtime for containers', usage = 'docker [OPTIONS] COMMAND'
```

The inline USAGE handler correctly extracts `docker [OPTIONS] COMMAND` from the `Usage:  docker [OPTIONS] COMMAND` line and promotes the following paragraph as `summary`. The docker expected fixture `cli.summary` is `"A self-sufficient runtime for containers"` — this now matches what the parser produces.

Non-regression confirmed:
```
GH:     summary = 'Work seamlessly with GitHub from the command line.', usage = 'gh <command> <subcommand> [flags]'
Kubectl: summary = 'kubectl controls the Kubernetes cluster manager.', usage = 'kubectl [flags] [options]'
```

Both gh and kubectl use the non-inline USAGE form (`USAGE\n  <text>`) — the else-branch is unchanged and these parse correctly.

---

### Schema Validation: PASS

All three expected fixtures validate against `schemas/help-tree.schema.json`. Confirmed by running the schema validator directly:

```
PASS: plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json
PASS: plugins/cli-to-plugin/tests/fixtures/kubectl-help-tree.expected.json
PASS: plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json
```

---

### Live gh Schema Validity: PASS

`discover.py` against live `gh` binary produces schema-valid JSON (38 groups, `global_flags: ['--help', '--version']`). Confirmed.

---

### Iteration-1 Fixes: Still Working

- Flatten convention: sub-groups are pushed to `state.groups_accumulator` at line 601 when `sub_group.get("commands") and len(sub_path) > 1`.
- Mixed-case section detection: docker fixture run produces 4 groups (`container`, `image`, `volume`, `network`) confirming `Management Commands:` and `Common Commands:` headings are parsed.
- Flag regex: `_ARG_PLACEHOLDER_RE` compound form still active at `discover.py:113`.
- Usage/flags writeback: lines 574–578 transfer `usage` and `flags` from `sub_group` to `cmd`.

All iteration-1 fixes are intact.

---

## New Finding: gh Fixture Summaries Diverge From Raw Fixture Content

**This is a pre-existing issue, not introduced by iteration 2.**

Running `discover.py` monkeypatched against the gh raw fixtures produces 4 command-level summary mismatches:

| Group | Command | Fixture says | Raw `gh-pr.txt` / `gh-issue.txt` says |
|-------|---------|--------------|----------------------------------------|
| `pr`    | `create`  | `"Create a pull request on GitHub"` | `"Create a pull request"` |
| `pr`    | `view`    | `"Display the title, body, and other information about a pull request"` | `"View a pull request"` |
| `issue` | `list`    | `"List issues in a GitHub repository"` | `"List issues in a repository"` |
| `issue` | `create`  | `"Create an issue on GitHub"` | `"Create a new issue"` |

The raw fixtures contain the canonical text — the expected fixture was hand-curated in iteration 1 with different (more verbose) summaries that don't match what the parser produces from the actual raw content.

The MUST FIX B summary fallback fix (iteration 2) works correctly: when a depth-3 invocation returns empty stdout, the engine falls back to the summary captured from the parent's command listing (e.g., `gh pr --help` line `create: Create a pull request`). This produces summaries like `"Create a pull request"` — which is what the raw fixture actually says, not what the expected fixture claims.

**Impact on Wave 3 tests:** Any test using `assertEqual(actual_group, expected_group)` against the gh fixture will fail on these 4 command entries. A subset-within-commands strategy (matching by `name` and checking only `path` and `summary`) would still fail because the summaries themselves diverge.

**Severity:** MUST FIX. Wave 3 `test_real_gh_fixture_matches_expected` cannot pass as written. The expected fixture must be corrected to match what `parse_help_text()` actually produces from the raw files.

**Fix:** Update the 4 divergent summaries in `gh-help-tree.expected.json` to match the raw fixture content:

```json
// In groups[0] (pr):
{"name": "create", "path": ["pr", "create"], "summary": "Create a pull request"}
{"name": "view",   "path": ["pr", "view"],   "summary": "View a pull request"}

// In groups[1] (issue):
{"name": "list",   "path": ["issue", "list"],   "summary": "List issues in a repository"}
{"name": "create", "path": ["issue", "create"], "summary": "Create a new issue"}
```

These are the literal strings from lines 7–8 and 22–23 of `gh-pr.txt` and `gh-issue.txt` as parsed by the section parser.

---

## New Finding: Wave 3 Test Strategy Requires Subset-Within-Commands, Not Group Equality

**Severity:** SHOULD FIX. Not introduced by iteration 2, but becomes visible now that command entries are stripped to bare `name/path/summary`.

The README documents subset matching at the group level:

```python
for name, exp_group in expected.items():
    assert name in actual, ...
    assert actual[name] == exp_group  # ← full group equality
```

However, full group equality fails for docker because actual `container` has 25 commands while the expected fixture lists 4, and actual `image` has 12 while the expected lists 4. The specific 4 expected commands match correctly when checked individually, but `actual[name] == exp_group` returns False because the `commands` arrays differ in length.

Wave 3 test authors need to implement subset-within-commands, not group equality. The README should specify:

```python
for name, exp_group in expected.items():
    assert name in actual
    # Check group-level fields
    for field in ("name", "path", "summary"):
        if field in exp_group:
            assert actual[name].get(field) == exp_group[field]
    # Check commands as subset
    act_cmd_map = {c["name"]: c for c in actual[name].get("commands", [])}
    for exp_cmd in exp_group.get("commands", []):
        assert exp_cmd["name"] in act_cmd_map
        assert act_cmd_map[exp_cmd["name"]] == exp_cmd
```

---

## Verdict: MUST FIX

MUST FIX B, MUST FIX C, and MUST FIX A/5 are resolved. SHOULD FIX D is resolved. No regressions introduced in existing fixes.

However, a new MUST FIX is present: the gh expected fixture contains 4 command summaries that diverge from what `parse_help_text()` produces from the raw fixtures. This is a pre-existing data quality issue from iteration 1 that was not corrected in iteration 2. Wave 3 `test_real_gh_fixture_matches_expected` cannot produce a passing test against this fixture.

The fix is a 4-line correction to `gh-help-tree.expected.json` — no code changes required.

This is iteration 2 of 3. If iteration 3 corrects the 4 divergent gh command summaries, Wave 3 is unblocked.
