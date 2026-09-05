# Plugin and marketplace formats

Checked 2026-09-05. This reference distinguishes documented package conventions from this helper's
optional catalog authoring checks. It is not a frozen copy of an internal ingestion schema.

## Plugin manifest

A small local plugin can use:

```json
{
  "name": "document-helper",
  "version": "0.1.0",
  "description": "Review and summarize supplied documents",
  "skills": "./skills/"
}
```

Create the referenced directory and real skill content before treating it as functional. Only the
manifest belongs in `.codex-plugin/`; components live at the plugin root.

The creator adds `author.name` and useful initial `interface` metadata for catalog presentation.
Optional publisher fields include `homepage`, `repository`, `license`, and `keywords`. Existing
plugin identifiers can contain ASCII letters, digits, hyphens, underscores, and non-empty dot-separated
segments; new scaffold names use lowercase hyphen case.

An interface example:

```json
{
  "interface": {
    "displayName": "Document Helper",
    "shortDescription": "Review documents and prepare summaries",
    "longDescription": "Extract key decisions and produce a concise summary from supplied documents.",
    "developerName": "Your team",
    "category": "Productivity",
    "capabilities": ["Read"],
    "defaultPrompt": ["Summarize the decisions in this document."]
  }
}
```

For new starter prompts use up to three strings, each at most 128 characters. The validator retains
compatibility with an existing single string and `default_prompt` spelling. Optional interface
fields include HTTPS `websiteURL`, `privacyPolicyURL`, `termsOfServiceURL`; `brandColor` as `#RRGGBB`;
and local `composerIcon`, `logo`, `logoDark`, and `screenshots` asset paths. Use `./assets/` where
practical and include the actual files.

## Component paths

Manifest component paths start with `./`, resolve relative to the plugin root, and stay inside that
root, including after resolving symlinks. Do not hardcode paths to an author's installed cache.

- `skills` points to a bundled skill directory (normally `./skills/`). Default `skills/` discovery
  remains checked by this validator alongside a custom directory. Skill `agents/openai.yaml` asset
  paths resolve relative to the skill folder.
- `mcpServers` is an inline server map or a path such as `./.mcp.json`.
- `apps` is the compatibility field for registered MCP/connector mappings, normally `./.app.json`.
- `hooks` is a path, an array of paths, an inline hooks object, or an array of inline hooks objects.
  An explicit entry replaces the default `hooks/hooks.json`.

MCP companion examples supported by the validator:

```json
{"documents": {"command": "document-mcp", "args": ["--stdio"]}}
```

```json
{"mcpServers": {"documents": {"command": "document-mcp", "args": ["--stdio"]}}}
```

Use the camelCase `mcpServers` wrapper or a direct map, without mixing forms. The Rust field
`mcp_servers` is renamed to camelCase for JSON; a snake_case JSON wrapper is not supported.
The checker validates map structure, not process startup, transport compatibility,
authentication, or every server option.

For a native stdio server shipped in the plugin, set `"cwd": "."` and use ordinary relative
arguments such as `"args": ["scripts/server.py"]` with `"command": "python3"`. The native parser
resolves relative `cwd` from the plugin root. It does not expand `${PLUGIN_ROOT}` or
`${CLAUDE_PLUGIN_ROOT}` in argument strings; hook environment variables do not imply MCP
interpolation. Omitted args are valid; when supplied they must be an array of strings.

App mappings use `{"apps": {"connection-name": {"id": "REAL_REGISTERED_ID"}}}`. Obtain the actual
technical identifier from the registered connection; do not infer it from a display name. Empty
maps are valid scaffolds, not working integrations.

An inert hook scaffold is `{"hooks": {}}`. For working hooks, use the current host's supported
events and schema. `${PLUGIN_ROOT}` points at the installed package and `${PLUGIN_DATA}` at writable
plugin data; compatibility variables `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` also exist. Never
store mutable state in the installed bundle. Installation alone does not grant hook trust. The
validator reads hook structure without executing commands or changing trust.

## Marketplace manifest

```json
{
  "name": "team-tools",
  "interface": {"displayName": "Team Tools"},
  "plugins": [
    {
      "name": "document-helper",
      "source": {"source": "local", "path": "./tools/document-helper"},
      "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
      "category": "Productivity"
    }
  ]
}
```

For `<root>/.agents/plugins/marketplace.json`, resolve the source from `<root>`. A personal root is
home, so `./.codex/plugins/document-helper` and `./plugins/document-helper` both work when they point
to real folders. The generator computes the path from `--path`; it does not relocate or symlink the
source. Marketplace identifiers allow ASCII letters, digits, underscores, and hyphens.

Keep entry order, top-level `interface.displayName`, existing policy values, optional product gating,
and source provenance stable. New entries receive installation, authentication, and category values.
Source paths can also be plain local strings. Official documentation describes Git `url` and
`git-subdir` descriptors with ref/sha selectors, plus npm package descriptors. The local scaffold does
not convert or overwrite those sources; use the appropriate source-maintenance workflow.

## Validation profiles and limits

`runtime` accepts minimal manifests while validating known fields and bundled files. `catalog` adds
required version/description, publisher name, richer interface fields, recognized top-level fields,
and UI prompt limits. Both reject non-semver versions when a version is present, invalid identifiers,
malformed known content, dangling references, and leftover `[TODO: ...]` manifest markers.

`catalog` is an explicit local quality policy carried forward from this skill's earlier checker,
not a guarantee that a public submission will pass. `runtime` is static validation, not a complete
emulation of every installed host. Unknown top-level extension fields are left to the host in that
profile. Check live product requirements before publishing; do not fabricate unsupported fields.

Bundled skill validation follows the public name/description constraints and common optional
frontmatter types. It permits extensions used by other hosts; `agents/openai.yaml` supports optional
UI, invocation policy, and tool dependencies. A policy-only agent file is valid. Trigger and workflow
behavior need representative task testing in addition to metadata validation.

Sources: [OpenAI package format](https://developers.openai.com/plugins/build/plugins),
[OpenAI skill metadata](https://learn.chatgpt.com/docs/build-skills),
[Native plugin MCP parser](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/plugin_config.rs),
[Agent Skills specification](https://agentskills.io/specification),
[OpenAI hook behavior](https://learn.chatgpt.com/docs/hooks).
