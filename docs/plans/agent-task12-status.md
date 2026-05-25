# Task 12 — Marketplace Integration for `cli-to-plugin`

**Status:** DONE
**Date:** 2026-05-25

## Changes Made

### 1. README.md — "Development & Workflow" section
Added `cli-to-plugin` as the first row (alphabetically before `fakoli-crew`) in the "Development & Workflow" table:

```md
| [**cli-to-plugin**](plugins/cli-to-plugin) | Convert any CLI with `--help` support into a Claude Code plugin: one skill per command group plus optional LLM-proposed workflow meta-skills. |
```

Alphabetical position: first in "Development & Workflow" (c < f).

### 2. `.claude-plugin/marketplace.json` — entry structure
Added `"category": "utilities"` to the existing `cli-to-plugin` entry. Final entry structure (mirrors sibling entries with the addition of `category`):

```json
{
  "name": "cli-to-plugin",
  "version": "1.0.1",
  "description": "Convert any CLI tool into a self-contained Claude Code plugin by walking its --help tree and generating one skill per command group, plus optional LLM-proposed workflow meta-skills.",
  "category": "utilities",
  "source": "./plugins/cli-to-plugin"
}
```

Note: No other sibling entries have a `category` field. The field is optional per `schemas/marketplace.schema.json` (line 138). Adding it to `cli-to-plugin` is schema-valid.

### 3. `scripts/generate-index.sh` — surgical fix to `update_marketplace`
The script's `update_marketplace` function was reconstructing the marketplace.json plugins array from scratch, stripping any `category` field added manually. A targeted fix was applied to preserve `category` from the existing marketplace.json entry when rebuilding:

- Read the existing marketplace.json plugins into `$existing_marketplace`
- For each plugin, merge back the `category` field from the existing entry if present
- All other sibling entries (without `category`) are unaffected

### 4. `registry/index.json`
Already contained `cli-to-plugin` prior to this task. `generate-index.sh` confirmed no changes were needed to the registry content.

## Verification Results

All five clauses from the task's verify command passed:

```
generate-index.sh   -> exits 0, 11 plugins
registry/index.json -> cli-to-plugin entry present
marketplace.json    -> cli-to-plugin entry with category: utilities
README.md           -> cli-to-plugin row present
validate.sh         -> Passed: 152, Warnings: 2 (pre-existing), Failed: 0
```

## Source Agreement

All three sync sources agree:

| Source | name | version | description prefix |
|--------|------|---------|-------------------|
| `plugins/cli-to-plugin/.claude-plugin/plugin.json` | cli-to-plugin | 1.0.1 | "Convert any CLI tool..." |
| `.claude-plugin/marketplace.json` | cli-to-plugin | 1.0.1 | "Convert any CLI tool..." |
| `registry/index.json` | cli-to-plugin | 1.0.1 | "Convert any CLI tool..." |
