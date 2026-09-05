---
name: plugin-creator
description: Create, validate, and maintain Codex plugins and local marketplace entries. Use when scaffolding a plugin, bundling skills, hooks, MCP servers or registered connectors, registering an existing plugin without changing its source, or preparing a local plugin update. Preserve existing metadata, configuration, source paths, and marketplace policies.
---

# Plugin Creator

Build the requested capability first, then package and validate it. A scaffold is a starting point;
empty skills, hooks, MCP, and app files do not provide a working integration.

All script paths below are relative to this skill directory. Scaffolding and update helpers use
Python 3.10+. Skill YAML validation additionally requires PyYAML; use an existing environment that
has it, or `uv run --with PyYAML python ...` without changing global Python packages.

## Create a plugin

```bash
python3 scripts/create_basic_plugin.py my-plugin --with-skills
```

The default destination is `~/plugins/my-plugin`. New names normalize to lowercase hyphen case,
up to 64 characters. The folder and manifest name match. The manifest contains useful initial UI
metadata and a version, with component paths only for components being created.

Add just the components needed:

```bash
python3 scripts/create_basic_plugin.py my-plugin \
  --path /absolute/parent-directory \
  --with-skills --with-scripts --with-assets --with-hooks --with-mcp --with-apps
```

- `.codex-plugin/plugin.json` is required. Other components belong at the plugin root.
- `--with-skills` creates `skills/`; add focused `skills/<skill-name>/SKILL.md` workflows.
- `--with-hooks` creates an empty `hooks/hooks.json`, which Codex discovers by default. It adds no
  executable commands. An explicit manifest `hooks` entry replaces that default discovery.
- `--with-mcp` creates `.mcp.json` and its manifest reference.
- `--with-apps` creates `.app.json` and its manifest reference. Populate it with real registered
  connection IDs; never invent IDs, credentials, or working endpoints.
- `--with-scripts` and `--with-assets` create companion directories.
- Replace generic descriptions and starter prompts with the actual capability. Keep secrets in the
  user's configured environment or credential store, never in the bundle.

## Register a marketplace entry

A personal marketplace defaults to `~/.agents/plugins/marketplace.json`. A repository marketplace
uses `<repo-root>/.agents/plugins/marketplace.json`. Follow the user's requested destination;
otherwise use the personal default when a local listing is needed.

```bash
python3 scripts/create_basic_plugin.py my-plugin --with-skills --with-marketplace
```

For a repository marketplace:

```bash
python3 scripts/create_basic_plugin.py my-plugin \
  --path /absolute/repo/plugins \
  --with-marketplace \
  --marketplace-path /absolute/repo/.agents/plugins/marketplace.json
```

The script derives `source.path` from the actual plugin location. It is relative to the marketplace
root, **not** to `.agents/plugins/`. For example, a plugin in `~/plugins/demo` has `./plugins/demo`;
one in `~/.codex/plugins/demo` has `./.codex/plugins/demo`. Custom directories work too. The plugin
must remain inside that marketplace root; an inconsistent destination fails before creating files.
The helper recognizes `.agents/plugins/marketplace.json` and legacy `.claude-plugin/marketplace.json`;
for a directly supplied JSON file elsewhere it treats the containing directory as the root. Confirm
that root against the active host before installing from a nonstandard layout.

Register an existing plugin without recreating its manifest or companions:

```bash
python3 scripts/create_basic_plugin.py my-plugin \
  --path /absolute/existing-parent \
  --marketplace-only --with-marketplace \
  --marketplace-path /absolute/repo/.agents/plugins/marketplace.json
```

This mode preserves the exact existing plugin identifier, including valid dots and underscores.
Use `--force` to extend an existing scaffold or update an existing marketplace entry. It preserves
manifest metadata and existing companion files, adds only missing requested component references,
and preserves marketplace order, display name, source descriptor, custom fields, and existing
policies. Explicit `--install-policy`, `--auth-policy`, or `--category` values update only those fields.
It never redirects an existing marketplace entry to a different local or remote source. Edit such a
source intentionally as a separate reviewed change.

New marketplace entries include `policy.installation: AVAILABLE`,
`policy.authentication: ON_INSTALL`, and `category: Productivity`. Supported installation policies are
`AVAILABLE`, `NOT_AVAILABLE`, and `INSTALLED_BY_DEFAULT`; authentication policies are `ON_INSTALL` and
`ON_USE`. Existing product gating is preserved. Do not introduce product gating unless requested.
New entries append to `plugins[]`. Use `--marketplace-name` only to name a new marketplace; it refuses
to rename an existing one.

## Validate before handing back

```bash
uv run --with PyYAML python scripts/validate_plugin.py /absolute/plugin
uv run --with PyYAML python scripts/validate_plugin.py /absolute/plugin --profile catalog
```

The default `runtime` profile is a **static package preflight**: it checks known metadata types,
component paths and files, skill YAML and assets, hook structure, and MCP/app maps. Minimal local
manifests can omit publisher/UI metadata. Unknown top-level extension fields are tolerated by this
profile; this does not establish that a host supports those fields.

The `catalog` profile adds the earlier creator's richer publisher/UI requirements, rejects unknown
manifest fields, and checks starter prompt display limits. It is a local authoring policy, not a
claim to reproduce the service's current submission validator. An online catalog may impose more
requirements. Neither profile executes hooks, connects an MCP server, authenticates a connector,
installs a plugin, or confirms runtime behavior.

The validator supports documented `hooks` path/object forms, custom paths under the plugin root,
and direct or camelCase `mcpServers`-wrapped MCP companion maps. The native JSON format does not
support a snake_case `mcp_servers` wrapper. It detects
missing components and paths/symlinks escaping the bundle. Existing single-string starter prompts
remain accepted; new scaffolds use a prompt array.

For bundled skills, follow the [Agent Skills format](https://agentskills.io/specification): name
matches its directory, uses lowercase letters/digits/single hyphens, and is at most 64 characters;
a meaningful description is at most 1024 characters. Keep workflows focused and move detailed
references out of SKILL.md. `agents/openai.yaml` is optional and can contain just policy or
understood tool dependencies. Prefer `policy.allow_implicit_invocation: false` there when a skill
should require explicit invocation. Test realistic positive and negative trigger prompts and one
representative workflow; schema validation alone does not test skill quality.

## Update an existing installation

Edit the source that the selected marketplace actually references. Verify that binding read-only:

```bash
python3 scripts/read_marketplace_name.py \
  --marketplace-path /absolute/root/.agents/plugins/marketplace.json \
  --plugin-path /absolute/root/plugins/my-plugin
```

Prepare a version change when local reinstall testing is part of the request:

```bash
python3 scripts/update_plugin_cachebuster.py /absolute/plugin --dry-run
python3 scripts/update_plugin_cachebuster.py /absolute/plugin
```

The helper changes only `version` to `<base>+codex.<token>` and preserves other manifest data. It
requires semver by default, has an explicit legacy opt-in, uses a UTC timestamp with microseconds,
and replaces the previous build suffix rather than stacking suffixes. Cachebusters are a local
development convention, not a release-version strategy or a guarantee of host refresh behavior.
See [installing and updating](references/installing-and-updating.md) for version-aware CLI discovery,
source verification, authorized reinstall, and testing in a fresh task. Do not rewrite global config,
install a marketplace, or reinstall merely to validate a bundle.

## App handoff

When this workflow created or updated a marketplace entry, end the response with `To view this in
the Codex app:` and Markdown links labeled `View <plugin-name>` and `Share <plugin-name>`:

- View: `codex://plugins/<plugin-name>?marketplacePath=<absolute-marketplace.json-path>`
- Share: the same URL followed by `&mode=share`

URL-encode the plugin path segment and marketplace query value. Do not add `pluginName` or `hostId`
query parameters. Omit these links when no marketplace entry changed. A link is a UI handoff, not
proof of installation or successful loading.

## References and regression tests

- [Package and marketplace formats](references/plugin-json-spec.md)
- [Local installation and update workflow](references/installing-and-updating.md)
- [Upgrade notes and verified sources](references/upgrade-notes.md)

After modifying this skill:

```bash
uv run --with PyYAML python -m unittest discover -s tests -v
uv run --with PyYAML python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .
```

Tests use temporary directories and never install plugins or modify real marketplaces/configuration.
