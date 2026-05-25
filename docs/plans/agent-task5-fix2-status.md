# Welder — Wave 2 Fix Cycle Iteration 2 Status

**Agent:** welder
**Date:** 2026-05-24
**Scope:** cli-to-plugin — targeted fixes for MUST FIX A, B, C + SHOULD FIX D

---

## MUST FIX B — discover.py:544 — Missing `elif sub_summary` fallback

**STATUS: RESOLVED**

Added the missing fallback at `discover.py:572–573`:

```python
if sub_group.get("summary"):
    cmd["summary"] = sub_group["summary"]
elif sub_summary:
    cmd["summary"] = sub_summary
```

This mirrors the bare-leaf path at line 609 and the max-depth path at line 552. Commands whose sub-walk returns empty stdout now fall back to the summary captured from the parent's command listing, preventing silent summary loss.

---

## MUST FIX C — docker-help-tree.expected.json `--config` entry incorrect

**STATUS: RESOLVED**

The `--config` entry was missing `"argument": "string"` and had a truncated description. Regenerated the entire `global_flags` array from what `parse_help_text()` actually produces against `docker.txt`:

- 3 entries replaced with all 11 correct entries from Docker's `Global Options:` section
- `--config` now correctly includes `"argument": "string"` and full description `"Location of client config files (default \"/Users/sdoumbouya/.docker\")`
- Eliminates the entire class of "fixture-claims-what-parser-doesn't-produce" issues for global_flags

---

## MUST FIX A/5 — gh-help-tree.expected.json commands carry usage/flags without depth-3 raw fixtures

**STATUS: RESOLVED (Option B)**

Stripped `usage` and `flags` from all command entries in `gh-help-tree.expected.json`. All 21 command entries across 6 groups now contain only `name`, `path`, and `summary`. This aligns the fixture with what the monkeypatch strategy (empty stdout for unknown depth-3 invocations) actually produces.

Also verified kubectl and docker expected fixtures — both already had bare command entries; no changes needed there.

Updated `tests/fixtures/README.md`:
- Added explicit note: "Expected JSON command entries do not include `usage` or `flags` — those require depth-3 raw captures which are out of scope."
- Updated `gh-help-tree.expected.json` description to say "bare entries (`name`, `path`, `summary` only)"
- Updated `docker-help-tree.expected.json` description to say "all 11 flags from Docker's root Global Options section"

---

## SHOULD FIX D — docker inline USAGE misread as usage text

**STATUS: RESOLVED**

Root cause: `Usage:  docker [OPTIONS] COMMAND` is an inline-form USAGE line. The old handler always read the NEXT non-empty line as usage — causing `A self-sufficient runtime for containers` to land in `usage` while `summary` remained empty.

Fix in `discover.py` Pass 2 USAGE handler (around line 337):
- Detect inline form: if `re.sub(r'^usage:?\s*', '', stripped, re.IGNORECASE)` yields non-empty text, that is the usage value
- After capturing inline usage, if `summary` is not yet set, read the following non-empty line as summary — provided it does not look like a real section heading (ends with `:`, is ALL-CAPS, starts with `#`, or starts with `USAGE`)

Verified: `parse_help_text()` against `docker.txt` now produces `summary: 'A self-sufficient runtime for containers'` and `usage: 'docker [OPTIONS] COMMAND'`.

The docker expected fixture's `cli.summary` was already correct (`"A self-sufficient runtime for containers"`); this fix makes the parser produce matching output.

---

## No New Defects

- Verified `gh --help`, `gh-pr.txt`, and other raw fixtures still parse correctly after the USAGE inline change (gh uses the non-inline form `USAGE\n  gh <command> <subcommand> [flags]`, so the else-branch runs, unchanged behavior)
- Live `gh` discovery still produces a schema-valid tree
- All three expected fixtures validate against `schemas/help-tree.schema.json`
- Plugin validation: 8 passed, 4 warnings (pre-existing), 0 errors

---

## Verification Results

```
fixtures: validate       ✓ (all 3 fixtures schema-valid)
command entries: clean   ✓ (no usage/flags in command entries)
live gh: validates       ✓ (discover.py against live gh binary)
plugin validate.sh:      8 passed, 4 warnings, 0 errors
```

---

## Files Modified

- `plugins/cli-to-plugin/scripts/discover.py` — two surgical changes:
  1. USAGE inline detection (SHOULD FIX D) — Pass 2 USAGE handler
  2. `elif sub_summary` fallback (MUST FIX B) — line ~572
- `plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json` — stripped usage/flags from all 21 command entries
- `plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json` — replaced 3-entry global_flags with all 11 correct entries
- `plugins/cli-to-plugin/tests/fixtures/README.md` — documented command-level field scope
- `plugins/cli-to-plugin/.claude-plugin/plugin.json` — version bumped 1.0.0 → 1.0.1
- `registry/index.json`, `registry/categories.json`, `registry/tags.json` — regenerated

---

## Out of Scope (Deferred)

- SHOULD FIX E — docker global_flags subset semantics documentation (now moot: fixture has all 11 flags, full equality comparison will work)
- CONSIDER F — `_SECTION_RE` false positives (confirmed harmless for current fixture set; both false positives land in `kind=other`)
- NIT G — `deep-recursion.txt` still present alongside split files
