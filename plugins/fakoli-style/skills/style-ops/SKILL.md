---
name: style-ops
description: Manage the Fakoli Style operating-model principles ledger: add principles, advance lifecycle status, validate the ledger, and read the current status report.
---

# style-ops

Skill for operating the Fakoli Style principles ledger. The canonical source of truth is `data/principles.json`; `docs/fakoli-style.md` is a generated projection. Edit the data, not the doc, then regenerate.

**Lifecycle rule:** a principle cannot reach `proven` unless its `proof` field resolves to a real test file on disk. The validator enforces this and exits non-zero on any violation.

## Verbs

### add

Append a new principle entry to `data/principles.json`. New entries default to `aspirational` and require an `open_work` field describing what work would raise the status. After editing, regenerate and validate.

```bash
# 1. Edit data/principles.json: add an entry with status "aspirational" and open_work
# 2. Regenerate the doc
uv run --script scripts/generate.py
# 3. Validate the ledger
uv run --script scripts/validate.py
```

Run both commands from `plugins/fakoli-style/`.

### set-status

Advance a principle's lifecycle status by editing its entry in `data/principles.json`. Rules by target status:

- `asserted`: add `proof` (repo-relative file path) and a non-empty `embodied_in` array.
- `proven`: same as `asserted`, but `proof` must point to a test file (`test_*.py`, `*_test.py`, or a file under a `tests/` directory). The validator rejects a `proven` entry whose proof is not a test file.

After editing, regenerate and validate:

```bash
uv run --script scripts/generate.py
uv run --script scripts/validate.py
```

Run both commands from `plugins/fakoli-style/`.

### validate

Run the full ledger validator. Checks schema validity, duplicate IDs, proof-path existence, embodiment-path existence, the proven-requires-test rule, and staleness of the generated doc.

```bash
uv run --script scripts/validate.py
```

Exits 0 with `OK: ledger and generated doc are valid and in sync`. Exits 1 with `FAIL: <reason>` on any violation.

### report

Read the status of all principles. Two options:

**Generated doc (formatted table):**
```bash
# Open docs/fakoli-style.md and read the "At a glance" table
cat docs/fakoli-style.md
```

**Quick jq summary (counts by status):**
```bash
jq '[.principles[].status] | group_by(.) | map({(.[0]): length}) | add' data/principles.json
```

Run from `plugins/fakoli-style/`.

## Reference

Full documentation: [README.md](../../README.md)

Ledger: [data/principles.json](../../data/principles.json)

Generated doc (do not hand-edit): [docs/fakoli-style.md](../../docs/fakoli-style.md)
