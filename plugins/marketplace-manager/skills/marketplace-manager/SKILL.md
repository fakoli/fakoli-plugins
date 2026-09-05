---
name: marketplace-manager
description: Maintain a Fakoli-compatible source marketplace checkout by adding or removing plugin scaffolds, validating packages, synchronizing catalogs, or installing its CI workflows.
---

# Marketplace maintenance

Operate on the source checkout the user selected. Resolve helpers relative to this skill directory; their install/cache location does not identify the target repository. Pass `--root /absolute/checkout` or run from the checkout. `FAKOLI_MARKETPLACE_ROOT` is an optional explicit default.

The checkout must contain `.claude-plugin/marketplace.json`, `scripts/catalog.py`, `scripts/validate.sh`, and `templates/basic`. This skill maintains repository artifacts; installed-plugin management uses the host's plugin tools.

## Inspect and validate

```sh
python3 /resolved/skill/scripts/manage.py status --root /absolute/checkout
/absolute/checkout/scripts/validate.sh
/absolute/checkout/scripts/generate-index.sh --check
```

Validation requires `uv`; registry and manager operations require Python 3.11 or newer. Validation checks both manifests, skill frontmatter and links, local source containment, and catalog drift. `generate-index.sh` synchronizes the Claude/Codex marketplaces and registry while preserving catalog order and existing Codex policy.

## Add a scaffold

```sh
python3 /resolved/skill/scripts/manage.py add my-plugin --root /absolute/checkout \
  --description 'A concise description of the intended workflow.' --category Productivity
```

The helper creates both host manifests and a discoverable skill, updates the README table, validates, and synchronizes catalogs. It rolls back on failure. The result is explicitly unfinished until its domain workflow is authored and tested. Read the target project's `docs/PLUGIN_GUIDELINES.md` and use the available skill-creator guidance to implement that workflow. `--no-validate` skips only the initial scaffold check; validate before distributing it.

## Remove

Use the exact plugin name, verify the selected root, and remove only the plugin the user authorized:

```sh
python3 /resolved/skill/scripts/manage.py remove my-plugin --root /absolute/checkout --force
```

`--force` expresses the explicit deletion choice and avoids an interactive prompt. Names and containment are checked before mutation. Catalogs and the README are updated together, with rollback if regeneration fails. Never infer removal from a plugin merely being unused.

## Install workflows

```sh
python3 /resolved/skill/scripts/manage.py workflows /absolute/target --root /absolute/source
```

Workflow templates are packaged with this skill. The target needs the repository's validation, generation and test entrypoints. Existing differing workflows require `--force`; do not overwrite them unless replacing them is within the requested task. Installing files does not commit or publish them.

[README](../../README.md) describes compatibility and migration.

For validation/deep scans, run `python3 "$SKILL_DIR/scripts/manage.py" scan [plugin-name] --root "$CHECKOUT"`. Resolve the variables to the loaded skill directory and chosen source checkout. This runs the target's validator and path/hook scanner, preserving their nonzero exits.
