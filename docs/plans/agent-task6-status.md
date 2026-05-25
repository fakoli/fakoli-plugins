# Task 6 Status — Implement `validate-output.sh`

**Status:** COMPLETE
**Date:** 2026-05-24
**Agent:** Smith

## File created

- `plugins/cli-to-plugin/scripts/validate-output.sh` — wraps all four validation checks; executable

## Verification

Command run (verbatim from acceptance criteria):

```bash
cd /Users/sdoumbouya/code/claude-env/fakoli-plugins && \
  bash -n plugins/cli-to-plugin/scripts/validate-output.sh && \
  bash plugins/cli-to-plugin/scripts/validate-output.sh "$(pwd)/plugins/cli-to-plugin"
```

Output (final summary block):

```
========================================
  validate-output.sh summary for /Users/sdoumbouya/code/claude-env/fakoli-plugins/plugins/cli-to-plugin
========================================
  Marketplace validate.sh:       PASS (0 errors, 4 warnings)
  test-path-resolution.sh:       PASS
  plugin.json schema check:      PASS
  SKILL.md frontmatter checks:   PASS (0 skills checked, 0 failed)
========================================
  Overall:                       PASS
========================================
```

Exit code: 0. All four acceptance criteria checks pass.

## Acceptance criteria checklist

- [x] `scripts/validate-output.sh <absolute-path>` runs `validate.sh` and `test-path-resolution.sh` against the target
- [x] Validates each `skills/*/SKILL.md` frontmatter against `schemas/skill.schema.json` using `uv run --with jsonschema --with pyyaml python -c`
- [x] Validates `plugin.json` against `schemas/plugin.schema.json` via `uv run --with jsonschema python -m jsonschema`
- [x] Exits 0 on full success, non-zero on any failure
- [x] Emits clear final summary block with error/warning counts
- [x] Does NOT use `set -e` — uses explicit exit-code checking (`validate_exit=$?` pattern)
- [x] Resolves marketplace script paths via `SCRIPT_DIR` + `../../..` relative to script location
- [x] Script is executable (`chmod +x`)
- [x] Zero skills is not a failure — prints "No SKILL.md files found — skipping frontmatter check (not a failure)"
- [x] validate.sh emits 4 WARNs (missing README.md, CHANGELOG.md, LICENSE file, no components) but no ERRORs; overall PASS

## Decisions

### YAML frontmatter extraction

Used `awk '/^---$/{c++; if(c==2) exit; next} c==1 {print}'` to extract the YAML block between the first pair of `---` markers. This is safer than sed for multi-line extraction and handles edge cases where `---` appears in body content (it exits after the second marker). The extracted YAML is passed as a here-string literal into a Python one-liner via `uv run --with jsonschema --with pyyaml python -c '...'` so both deps install in a single uv call (~13ms overhead per the scout finding).

### Schema validation tool choice

Used `uv run --with jsonschema python -m jsonschema` for `plugin.json` (file-based invocation, cleaner for two-file comparison) and `uv run --with jsonschema --with pyyaml python -c '...'` for SKILL.md frontmatter (inline Python needed to do YAML→JSON→schema in one step without temp files). ajv was explicitly excluded per scout finding that Node.js is not available on dev machines.

### Error/warning counting

`validate.sh` emits colored ANSI output. The script captures stdout+stderr together, strips ANSI codes with `sed 's/\x1b\[[0-9;]*m//g'`, then counts `ERROR:` and `WARN:` occurrences with `grep -c`. This is reliable because both scripts use consistent prefixes.

### No `set -e`

The script uses explicit `var=$?` capture after every command that could fail, then branches on `$var -ne 0`. The `((counter++)) || true` pattern is used for arithmetic increments to prevent exit on zero-increment edge cases (same pattern as the marketplace scripts themselves).

### Marketplace root resolution

`MARKETPLACE_ROOT="$SCRIPT_DIR/../../.."` resolves correctly from `plugins/cli-to-plugin/scripts/` to the repository root regardless of the caller's CWD.
