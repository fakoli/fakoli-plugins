---
name: style-ops
description: Maintain, validate or report on the Fakoli principles ledger, checking evidence pointers and keeping its Markdown projection synchronized.
---

# Style operations

Resolve the plugin root from this skill's location. Its bundled `data/principles.json` and [generated report](../../docs/fakoli-style.md) are readable reference data. For changes, select the user's durable source checkout or explicit ledger/output files; do not silently edit an installed cache.

1. Read the ledger and schema. For a new principle, use `aspirational` plus concrete `open_work`. Preserve existing IDs and history.
2. To assert or prove a principle, add repo-relative proof and embodiment pointers. A `proven` pointer must refer to a test file and real nested Python symbols when `::` symbols are present. A valid pointer does not establish that a test passed: run the relevant test and record its result before claiming verification.
3. Generate with the packaged script and explicit destinations when working outside the source checkout:

   ```bash
   uv run --script "$PLUGIN_ROOT/scripts/generate.py" --data "$LEDGER" --output "$REPORT"
   uv run --script "$PLUGIN_ROOT/scripts/validate.py" --repo-root "$SOURCE_CHECKOUT" --data "$LEDGER" --doc "$REPORT"
   ```

   Resolve these variables to actual paths. `--repo-root` is the checkout containing the evidence paths; it need not be the plugin install directory. `--schema` can select a corresponding custom schema. The generator's `--check` mode does not write.

4. For reports, summarize proven/asserted/aspirational status and the highest-risk open work. Separate pointer validation, tests actually run, and unverified claims.

When maintaining this marketplace's bundled ledger from its source checkout, the scripts' default data/schema/doc paths apply. Validation resolves a source checkout, never assumes that an arbitrary install cache's grandparents contain the evidence.

See [README](../../README.md), [ledger](../../data/principles.json), and [schema](../../schema/principles.schema.json).
