# Task 5 Status — Implement `discover.py`

**Agent:** guido
**Date:** 2026-05-24
**Status:** PASS

---

## Verification output

```
OK
33 groups discovered
```

Full verify command (verbatim from spec):

```bash
uv run --script plugins/cli-to-plugin/scripts/discover.py gh > /tmp/gh-tree.json && \
  uv run --with jsonschema python -c "import json, jsonschema; jsonschema.validate(...); print('OK')" && \
  uv run --with jsonschema python -c "import json; t=json.load(...); assert len(t['groups']) >= 10; print(f'{len(t[\"groups\"])} groups discovered')"
```

All three assertions pass. Elapsed time: ~6.5 seconds (well within 30s budget). Schema validation: OK.

---

## Acceptance criteria results

| Criterion | Result |
|---|---|
| PEP 723 inline metadata, `requires-python = ">=3.11"`, no third-party deps | PASS |
| `uv run --script ... gh` writes JSON to stdout, exits 0 | PASS |
| Accepts `--max-depth`, `--max-commands`, `--per-call-timeout`, `--total-timeout`, `--output` flags | PASS |
| Strips ANSI escape sequences before parsing | PASS |
| Forces `LANG=C.UTF-8` / `LC_ALL=C.UTF-8` for child processes | PASS |
| Decodes stdout as UTF-8 with `errors="replace"` | PASS |
| Non-zero exit with non-empty stdout: parses anyway, adds warning | PASS (gh extension exec --help rc=1 logged as warning) |
| Non-zero exit with empty stdout: exits non-zero with clear error | PASS (sys.exit(1) with message to stderr) |
| Output validates against `help-tree.schema.json` | PASS |
| Real `gh` produces ≥ 10 groups and exits within 30s | PASS (33 groups, ~6.5s) |

---

## Decisions and heuristics

### Section detection

A line is treated as a section heading if it matches `^([A-Z][A-Z0-9 _/-]+)\s*$` — all-uppercase words with optional spaces, slashes, and hyphens. This captures `gh`'s unusual headings ("CORE COMMANDS", "GITHUB ACTIONS COMMANDS", "ALIAS COMMANDS", "ADDITIONAL COMMANDS") by checking whether the heading ends with "COMMANDS" or "SUBCOMMANDS" as a command section, and exact matches for `{"FLAGS", "OPTIONS", "GLOBAL FLAGS", "INHERITED FLAGS", ...}` as a flag section. Any other all-caps heading is type "other" and its entries are ignored.

**Why suffix-based:** `gh` uses section names with qualifiers ("GITHUB ACTIONS COMMANDS", "CORE COMMANDS"). A full-word match would miss these. Suffix matching on "COMMANDS" captures all of them without a maintained allowlist.

### Command-line parsing

Command entries are parsed with a regex requiring 1–8 leading spaces, then a name token matching `[a-zA-Z][a-zA-Z0-9_-]*`, an optional colon (`gh` style), then whitespace and a description. The 1–8 space bound excludes continuation lines (which are deeply indented) and section headings (which have no leading spaces). Name underscores are normalized to hyphens per schema requirement.

**Why optional colon:** `gh` uses `pr:  Manage pull requests` (colon), `kubectl` and `docker` use `get  Display one or many resources` (no colon).

### Flag-line parsing

Flags are detected by a pre-filter regex `^\s+(-[a-zA-Z]|--[a-zA-Z])` before the full parse. The full flag regex captures:
- Optional short form: `-[a-zA-Z]` optionally followed by `, `
- Optional long form: `--[a-zA-Z][a-zA-Z0-9-]*`
- Optional argument in one of three forms:
  - Angle-bracket: `<anything>`  (e.g. `<OWNER/REPO>`)
  - ALL-CAPS: `[A-Z][A-Z0-9_/:-]{1,}` — requires at least 2 chars to avoid capturing the first letter of a description word (e.g. `--help   Show help` would incorrectly capture `S` as the argument without this bound)
  - Lowercase: `[a-z][a-zA-Z0-9_/-]*` (e.g. `string`, `fields`, `expression`)
- Description: remainder of the line

**Critical edge case:** `--help   Show help for command` — the word "Show" starts with uppercase `S`. The ALL-CAPS pattern was initially written as `[A-Z][A-Z0-9_/-]*` (1+ chars), which incorrectly captured `S` as the argument and `how help for command` as the description. Fixed by requiring 2+ chars for the ALL-CAPS form.

### Multi-line flag descriptions

When a flag section entry has a continuation line (6+ leading spaces, no flag prefix), it is appended to the previous flag's description. This handles `gh pr list --help` where some flag descriptions wrap.

### Help fetched from stderr fallback

When a CLI writes help to stderr instead of stdout (non-zero exit with empty stdout but non-empty stderr), the script uses stderr content as the help text. This handles CLIs that print usage on stderr when invoked with `--help` and exit non-zero.

### Recursion model

The walk is depth-first. `depth=0` is the root (handled separately before walking). Top-level groups are walked at `depth=1`. Sub-commands appear as entries on the parent group's help page and are walked at `depth=2`. At `depth == max_depth - 1`, sub-commands are recorded as bare leaf command objects without further recursion. At `depth == max_depth`, recursion stops entirely.

The flat `groups` array in the output is populated only from top-level groups (path length 1). Sub-groups from deeper recursion are stored as command entries inside their parent group, not as top-level siblings — this is correct per the schema's description ("Nesting is expressed via path length, not nested objects") and the example (`kubectl create deployment` → `{name: "create-deployment", path: ["create", "deployment"]}`). The schema does not require sub-groups to be promoted to the top-level flat array.

**Note for Task 7 (tests):** The `gh` discovery run produces one warning: `non-zero exit (rc=1), parsing anyway: gh extension exec --help`. The `extension exec` subcommand exits 1 when invoked with `--help` but produces help text, so it is parsed with a warning. This is the correct warn-and-continue behavior from the spec.

### Version detection

Tries `--version`, then `version`, then `-v` in order. Takes the first non-empty line from the first successful invocation. The `gh` version string is `gh version 2.92.0 (2026-04-28)` — stored verbatim, not parsed as semver (the schema says "free-form").

### Total-timeout enforcement

Checked before each `walk()` call (between groups and between sub-commands). A timed-out run still emits valid JSON for the groups already discovered; the timeout adds a warning and halts further recursion.

---

## File

`/Users/sdoumbouya/code/claude-env/fakoli-plugins/plugins/cli-to-plugin/scripts/discover.py`
