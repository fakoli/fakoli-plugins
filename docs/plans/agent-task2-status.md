# Task 2 Status — Define the help-tree JSON Schema

**Status: COMPLETE**
**Agent:** guido
**Date:** 2026-05-24

---

## Files Created

- `plugins/cli-to-plugin/schemas/help-tree.schema.json` — canonical help-tree schema (Draft 2020-12)

---

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| File exists at `plugins/cli-to-plugin/schemas/help-tree.schema.json` | PASS |
| Schema declares `$schema: https://json-schema.org/draft/2020-12/schema` | PASS |
| Requires top-level `cli`, `groups`, `discovery`; `global_flags` optional | PASS |
| Each command has a `path` array with `minItems: 2` | PASS |
| `Draft202012Validator.check_schema` self-check passes | PASS |
| Hand-written fixture validates against the schema | PASS |

---

## Verify Command Output

```
$ uv run --with jsonschema python -c "import json, jsonschema; s=json.load(open('plugins/cli-to-plugin/schemas/help-tree.schema.json')); jsonschema.Draft202012Validator.check_schema(s); print('OK')"
OK
```

---

## Schema Design Decisions

### Structural choices

**`additionalProperties: false` on `cli` and at top level; open on `groups`, `commands`, `flags`.**
The top level and `cli` object are fully enumerated and stable — locking them catches typos and schema drift early. `groups`, `commands`, and flags are allowed to grow (e.g., a future `subgroups` field on a group) without breaking existing consumers.

**`flag` defined as a `$defs` reference with `anyOf: [required short, required long]`.**
A flag with neither form is meaningless at the call site. Using `anyOf` rather than `if/then/else` keeps the constraint readable and produces a clear validation error message.

**`group.path: minItems 1`, `command.path: minItems 2`.**
Groups sit one level below the CLI root (path length 1); commands are always nested inside a group (path length ≥ 2). These constraints let `discover.py` assert invariants and let tests catch parser regressions without running the CLI.

**`raw_help` on both `groups` and `commands`.**
The spec's error-handling section specifies that unparseable help text falls back to raw capture. Placing `raw_help` on both objects means any level of the tree can carry a fallback without requiring a parallel schema branch.

**`cli.name` pattern `^[a-z0-9][a-z0-9-]*$`.**
Matches the spec note ("lowercase, hyphen-numeric") while requiring the name to start with an alphanumeric character, preventing names like `-foo`.

**`discovery` is `additionalProperties: false` with all four fields required.**
`discover.py` always emits all four fields. Making them required and the object closed means any schema drift in the emitter is caught at the validation boundary, not silently dropped.

---

## Hand-Written Fixture Validation

Fixture used for verification (not committed — inline only):

```json
{
  "cli": {
    "name": "gh",
    "binary": "/usr/local/bin/gh",
    "version": "2.40.0",
    "summary": "Work seamlessly with GitHub from the command line.",
    "homepage": "https://cli.github.com"
  },
  "global_flags": [
    {"short": "-R", "long": "--repo", "argument": "OWNER/REPO", "description": "Select another repository"}
  ],
  "groups": [
    {
      "name": "pr",
      "path": ["pr"],
      "summary": "Manage pull requests",
      "commands": [
        {
          "name": "list",
          "path": ["pr", "list"],
          "summary": "List pull requests",
          "usage": "gh pr list [flags]",
          "flags": [
            {"short": "-s", "long": "--state", "argument": "string", "description": "open|closed|merged|all"}
          ]
        },
        {
          "name": "view",
          "path": ["pr", "view"],
          "summary": "View a pull request",
          "usage": "gh pr view [<number>] [flags]",
          "flags": [
            {"long": "--json", "argument": "fields", "description": "Output JSON with the specified fields"}
          ]
        }
      ]
    },
    {
      "name": "repo",
      "path": ["repo"],
      "summary": "Work with GitHub repositories",
      "commands": [
        {
          "name": "clone",
          "path": ["repo", "clone"],
          "summary": "Clone a repository locally",
          "usage": "gh repo clone <repository> [<directory>]",
          "flags": []
        }
      ]
    }
  ],
  "discovery": {
    "depth_reached": 2,
    "commands_walked": 47,
    "elapsed_ms": 1820,
    "warnings": []
  }
}
```

Result: `Fixture validates OK`

### Rejection cases verified (9/9 correctly rejected)

| Case | Expected error |
|------|---------------|
| Missing `cli` | `'cli' is a required property` |
| Missing `discovery` | `'discovery' is a required property` |
| Unknown top-level field | `Additional properties are not allowed` |
| `cli.name` uppercase | Does not match pattern `^[a-z0-9][a-z0-9-]*$` |
| Flag with neither `short` nor `long` | Not valid under any of the given schemas |
| Group `path` is empty array | `[] should be non-empty` |
| Command `path` has only one element | `['list'] is too short` |
| `discovery.depth_reached` negative | `-1 is less than the minimum of 0` |
| Unknown field on `cli` object | `Additional properties are not allowed ('extra_data' was unexpected)` |
