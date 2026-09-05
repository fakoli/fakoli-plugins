# Marketplace Manager

Maintain a Fakoli-compatible **source checkout** from either Claude Code or Codex. The installed plugin can live anywhere: commands target the current checkout or an explicit `--root`.

Requires Python 3.11+; validation additionally uses `uv`. The source checkout must include this repository's `scripts/catalog.py`, validator, template, and README plugin-table marker.

```sh
python3 /path/to/plugin/skills/marketplace-manager/scripts/manage.py status --root /path/to/checkout
python3 /path/to/plugin/skills/marketplace-manager/scripts/manage.py add example-workflow --root /path/to/checkout --description 'Describe the intended workflow.'
python3 /path/to/plugin/skills/marketplace-manager/scripts/manage.py remove example-workflow --root /path/to/checkout --force
python3 /path/to/plugin/skills/marketplace-manager/scripts/manage.py workflows /path/to/target --root /path/to/checkout
```

The existing `add_plugin.sh`, `remove_plugin.sh`, `marketplace_status.sh`, and `install_workflows.sh` entrypoints delegate to this same implementation. `FAKOLI_MARKETPLACE_ROOT` is an optional default; helpers no longer walk above their installation directory.

Add/remove operations synchronize both marketplaces, registry indices, and README listings. A local lock rejects overlapping manager operations; synchronous failures restore the prior plugin/catalog state. A process killed during a transaction can leave a lock and staging directory; inspect those before recovering them.

Version 2 requires explicit `--force` for deletion, always regenerates after removal, and reports failures through nonzero exit codes. Workflow installation is noninteractive and requires `--force` to replace differing files. Scaffolds deliberately report that their domain workflow still needs authoring; they do not pretend to implement it.

See [the skill](skills/marketplace-manager/SKILL.md) and [repository conventions](../../docs/PLUGIN_GUIDELINES.md). Host plugin installation and publication are separate operations.
