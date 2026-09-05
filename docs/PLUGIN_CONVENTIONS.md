# Current plugin conventions

Verified September 5, 2026 against the [OpenAI packaging guide](https://developers.openai.com/plugins/build/plugins), [Claude plugin reference](https://code.claude.com/docs/en/plugins-reference), [Agent Skills specification](https://agentskills.io/specification), and local `codex-cli 0.153.4` help.

## Host packaging

Each active package includes `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`. Match names and versions. Claude auto-discovers standard skills/commands/agents; Codex uses supported native components and skills. Claude agent definitions are not a portable substitute for a Codex skill entrypoint. Native adapters should discover the host's actual tools and provide a local fallback when delegation is unavailable.

Codex's required runtime metadata is smaller than a polished catalog entry. The shared creator validator defaults to `runtime`; `--profile catalog` checks richer publisher/UI metadata without pretending it is universally mandatory. Skill UI metadata in `agents/openai.yaml` is optional. Configure only capabilities that actually ship.

Skills need YAML `name` and a descriptive `description`. Names match the directory, use lowercase alphanumerics with single hyphens, and have at most 64 characters. Descriptions have at most 1024 characters. Load supporting detail on demand; use actual relative resource links and host tool discovery. Existing user authorization and autonomy instructions apply across the workflow.

## Paths and durable state

Resolve packaged scripts/resources from the loaded plugin or skill location. Resolve user projects from the actual working directory or explicit arguments. Never infer a source repository by walking a fixed number of parents above an installed cache. User state belongs in a stable project/user data location; migrations should preserve old data and be explicit.

Codex catalogs live at `.agents/plugins/marketplace.json`. Local source paths resolve from the marketplace root, not the nested catalog directory. This repository manages local source entries and refuses remote entries it cannot safely regenerate. It preserves independent display order and existing policy/metadata.

## Hooks and MCP

Codex supports hook manifests and supplies `PLUGIN_ROOT`/`PLUGIN_DATA` plus compatibility variables. Host event names, trust and payload schemas still need validation; attaching metadata alone does not prove hook delivery. The current native MCP parser supports a direct server map and the `mcpServers` wrapper. It normalizes relative `cwd` against the plugin root; do not assume it expands shell-style variables in `args`. The creator checks the actual native contract separately from other manifest standards. Do not silently enable external services or manufacture credentials during scaffolding.

## Maintenance

- `./scripts/generate-index.sh` updates both host catalogs and registry aggregates. `--check` reports drift without writing.
- `uv run --script scripts/validate.py` validates native packaging, Claude schema, skill metadata/resource links and cross-host/catalog consistency.
- `./scripts/check-all.sh` retains hook/path/roster checks and runs package tests through the combined test entrypoint.
- `scripts/bump-plugin.sh` synchronizes host manifests and generated catalogs. Version changes in Python package metadata must agree too.
- `tools/plugin-creator` is the durable source copy of the upgraded installed system skill. See its `references/upgrade-notes.md` for tests and refresh limits. The installed copy was also updated; a future host refresh may replace it.

Avoid compulsory model names, invented tools, repetitive option menus, fake success after failed commands, and documentation that advertises behavior its tests never exercise. Scaffolds should honestly say their domain workflow is unfinished.
