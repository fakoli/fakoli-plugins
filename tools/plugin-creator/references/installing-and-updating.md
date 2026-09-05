# Updating existing local plugins

Verified 2026-09-05 against the official packaging documentation and local `codex-cli 0.153.4`
command help. Commands and discovery vary by host version. This flow prepares and tests local source
changes; it does not publish releases or migrate Git/npm source descriptors.

## Confirm the source before changing install state

1. Inspect CLI support with `codex --version`, `codex plugin --help`, and
   `codex plugin marketplace --help`.
2. Read the selected marketplace and verify that its one matching local entry points to the source
   being edited:

```bash
python3 scripts/read_marketplace_name.py \
  --marketplace-path /absolute/root/.agents/plugins/marketplace.json \
  --plugin-path /absolute/root/plugins/my-plugin
```

Omit `--marketplace-path` for the personal file at `~/.agents/plugins/marketplace.json`.
`--plugin-path` is optional but recommended: it validates the manifest identifier and rejects missing,
duplicate, remote, or mismatched source entries. The command prints the validated marketplace name.

3. Use `codex plugin marketplace list` to inspect marketplaces considered by the current host and
   their resolved roots. Current CLI help explicitly includes considered marketplaces; older advice
   that this command cannot inspect local defaults is obsolete. Use `codex plugin list` when plugin
   provenance also needs inspection.

Both the personal marketplace and the active repository's `.agents/plugins/marketplace.json` can be
discovered automatically. A repo's legacy `.claude-plugin/marketplace.json` is also supported. Do not
register duplicates just because a path is non-personal. Check the active host and working directory.

For a different local marketplace that is absent from the considered sources, the current CLI command
is `codex plugin marketplace add /absolute/marketplace-root`. Run it only when marketplace installation
is part of the authorized task. Do not add a marketplace or rewrite global config just to validate a
source edit. Git-backed marketplace snapshots and Git/npm plugin sources need their own update flow;
a local cache edit is not a durable source update.

## Validate and preview the version change

```bash
uv run --with PyYAML python scripts/validate_plugin.py /absolute/plugin
python3 scripts/update_plugin_cachebuster.py /absolute/plugin --dry-run
```

Fix substantive validation errors before changing installed state. A source edit does not require a
cachebuster unless local reinstall testing needs it.

The cachebuster helper preserves everything before the first `+` and replaces build metadata with a
single `+codex.<token>` suffix:

- `1.2.3` becomes `1.2.3+codex.<token>`.
- `1.2.3-rc.1+codex.old` becomes `1.2.3-rc.1+codex.<token>`.
- Non-Codex build metadata is replaced too; inspect the dry run when it carries meaning.

The default token uses UTC time through microseconds. `--cachebuster local-check` selects a stable
token for an explicit test; spaces and punctuation normalize to hyphens. An empty token fails.
The helper requires an existing semantic version, makes an atomic write, preserves file permissions
and other manifest fields, and refuses a symlinked manifest. An intentional legacy version can use
`--allow-non-semver`, but catalog validation will still reject that version. This escape hatch is not
recommended for new bundles.

## Apply and reinstall when authorized

```bash
python3 scripts/update_plugin_cachebuster.py /absolute/plugin
codex plugin add my-plugin@verified-marketplace-name
```

Use the actual validated identifiers, never a guessed source name. The helper itself does not install,
remove, trust hooks, update marketplace files, or edit global configuration. Preserve the user's
existing authorization scope; a request for source maintenance alone does not require reinstalling.

Official packaging guidance also describes restarting the desktop app to pick up local source
changes. For the specific host, follow its supported refresh or reinstall flow and verify the result;
a version suffix by itself is not proof that new content loaded.

After an authorized install/refresh, test in a fresh task or CLI session so bundled skills and tools
are loaded anew. Run a representative skill workflow and, when applicable, MCP connection/tool and
hook-event checks. Hook trust is a separate host control: never enable or trust hooks as an incidental
part of validation. Report source changes and runtime verification separately.

Sources: [OpenAI packaging and marketplace guidance](https://developers.openai.com/plugins/build/plugins),
[plugin usage and fresh sessions](https://learn.chatgpt.com/docs/plugins).
