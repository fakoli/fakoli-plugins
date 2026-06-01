# fakoli-style

Governed ledger of the Fakoli operating-model principles. Tracks which rules are proven by machine tests, which are asserted with a pointer, and which are aspirational, then generates a formatted Markdown report from that single source of truth.

## What it does

The plugin maintains `data/principles.json` as the canonical record of operating-model principles. Each entry carries a `status` (`proven`, `asserted`, or `aspirational`) and the evidence required to earn that status. A Python script projects the ledger into `docs/fakoli-style.md`; a second script validates the ledger against its schema, checks that all proof paths exist on disk, and diffs the generated doc against the committed one to catch staleness.

**The hard rule: edit `data/principles.json`, never `docs/fakoli-style.md` directly.** The generated doc carries a "do not hand-edit" banner. Changes made there are overwritten the next time `generate.py` runs.

## Installation

```bash
# From the repo root
claude plugin install ./plugins/fakoli-style
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The scripts pull `jsonschema` automatically via `uv run --script`.

## Canonical-data to generated-doc model

```
data/principles.json          <-- edit here
        |
        v
scripts/generate.py           <-- uv run --script scripts/generate.py
        |
        v
docs/fakoli-style.md          <-- read-only projection (do not hand-edit)
```

`scripts/validate.py` runs the full loop in check mode: schema, lifecycle rules, disk-existence of proof paths, and a staleness diff. Run it before every commit that touches `data/principles.json`.

## Statuses

| Status | Meaning | Required fields |
|---|---|---|
| `proven` | Machine-verified by a test in CI | `proof` pointing to a test file, non-empty `embodied_in` |
| `asserted` | Claimed with a resolvable pointer, not yet machine-verified | `proof` pointing to any existing file, non-empty `embodied_in` |
| `aspirational` | Not yet built | `open_work` describing what would raise the status |

A principle cannot reach `proven` unless `proof` resolves to a real test file (`test_*.py`, `*_test.py`, or a file under `tests/`). The validator enforces this and exits non-zero with a precise message on any violation.

`data/principles.json` is a versioned object `{ "version": "1.0.0", "principles": [ ... ] }`. Each element in the `principles` array is one entry with the fields shown in the Statuses table above (`status`, `proof`, `embodied_in`, or `open_work` as required by status).

## Quick start

```bash
cd plugins/fakoli-style

# Validate the ledger and confirm the generated doc is current
uv run --script scripts/validate.py

# Regenerate docs/fakoli-style.md after editing data/principles.json
uv run --script scripts/generate.py

# Read the at-a-glance status table
cat docs/fakoli-style.md

# Count principles by status
jq '[.principles[].status] | group_by(.) | map({(.[0]): length}) | add' data/principles.json
```

## Verbs (style-ops skill)

| Verb | What it does | Invocation |
|---|---|---|
| add | Append a new `aspirational` entry with `open_work` to `data/principles.json`, then regenerate and validate | Edit `data/principles.json`, then `uv run --script scripts/generate.py` and `uv run --script scripts/validate.py` |
| set-status | Edit an entry's `status` and add its `proof` / `embodied_in`, then regenerate and validate | Edit `data/principles.json`, then run both scripts |
| validate | Run schema, duplicate IDs, lifecycle, disk-existence, and staleness checks | `uv run --script scripts/validate.py` |
| report | Read the "At a glance" table or query with jq | `cat docs/fakoli-style.md` or `jq '[.principles[].status] ...` |

Full skill documentation: [skills/style-ops/SKILL.md](skills/style-ops/SKILL.md)

## Ledger reference

The generated ledger document (read-only): [docs/fakoli-style.md](docs/fakoli-style.md)

The document includes the ordering rule: entries are sorted most load-bearing yet least-proven first (by `credibility_risk` then `status`), so the claims that would most damage the project if false appear at the top.

## Files

| Path | Role |
|---|---|
| `data/principles.json` | Canonical source of truth. Edit this |
| `schema/principles.schema.json` | JSON Schema (draft-07) for the ledger |
| `scripts/generate.py` | Projects `data/principles.json` to `docs/fakoli-style.md` |
| `scripts/validate.py` | Full validation: schema + lifecycle + disk + staleness |
| `docs/fakoli-style.md` | Generated report, do not hand-edit |
| `skills/style-ops/SKILL.md` | Skill definition for the four management verbs |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (handles `jsonschema` dependency automatically)

## Author and license

Author: Sekou Doumbouya  
License: MIT
