# Claude Code Compatibility Review

Updated: 2026-06-26

This note records the T012 Claude Code compatibility pass for the active
plugins under `plugins/`. It focuses on whether the refreshed plugin surfaces
still load in Claude Code and whether any previously advertised behavior now
has a documented replacement.

## Compatibility Basis

The review used the local Claude Code runtime available in this workspace:

- `claude --version`: `2.1.193 (Claude Code)`
- `claude plugin validate plugins/<name>` for every active plugin: passed.
- `claude plugin validate .claude-plugin/marketplace.json`: passed with
  warnings for marketplace-only metadata fields (`displayName`, `repository`,
  `categories`) that Claude Code ignores at load time.
- `./scripts/validate.sh`: passed with 218 checks, 0 warnings, 0 failures.
- `./scripts/test-path-resolution.sh`: passed with 27 checks, 0 warnings,
  0 errors.
- `claude -p "/flow"` and `claude -p "/flow:brainstorm"`: returned
  `Unknown command`, confirming the short fakoli-flow aliases are not supported.
- `claude -p "/fakoli-flow:flow"` and
  `claude -p "/fakoli-flow:brainstorm Please do not write files; just say READY if this command route is recognized."`:
  routed successfully, confirming the Claude Code plugin namespace.

The documented Claude Code plugin surface represented by this repository is:

- Plugin manifests live at `.claude-plugin/plugin.json`.
- Standard component directories are auto-discovered from plugin root:
  `commands/`, `skills/`, `agents/`, and `hooks/hooks.json`.
- Plugin-internal hook and MCP paths use `${CLAUDE_PLUGIN_ROOT}` so installed
  cache copies do not depend on the repository checkout path.
- Skill frontmatter uses documented hyphenated fields such as
  `allowed-tools` and `user-invocable`.
- Agent frontmatter uses `tools`, not command/skill-style `allowed-tools`.
- MCP config is declared through `mcpServers` and points at `.mcp.json` when a
  plugin ships an MCP server.

## Plugin Matrix

| Plugin | Runtime surface | Compatibility status | Notes |
| --- | --- | --- | --- |
| `cli-to-plugin` | 1 command | Compatible | Minimal manifest and `/cli-to-plugin` command validate. Generated skill templates use hyphenated skill frontmatter. |
| `excalidraw-diagram` | 1 command, 1 skill, 1 agent | Compatible | Skill uses `allowed-tools`; agent uses `tools`; all components are in standard auto-discovered directories. |
| `fakoli-crew` | 1 command, 2 skills, 9 agents | Compatible | Agent frontmatter uses `tools`; the 9-agent roster is documented. Older plugin-surface critic roles now live in `fakoli-plugin-critic`. |
| `fakoli-flow` | 1 command, 6 skills, hooks | Compatible | `/fakoli-flow:flow`, `/fakoli-flow:brainstorm`, and hooks validate. The unsupported short `/flow` and `/flow:<skill>` aliases were replaced in docs with the Claude Code plugin namespace. |
| `fakoli-plugin-critic` | 5 agents | Compatible | Agents use `tools` and are standard Claude Code subagent files. No command or skill surface is advertised. |
| `fakoli-speak` | 7 commands, hooks | Compatible | Command surface is intact. `/voices` now documents `OPENAI_TTS_VOICE`, matching the implementation. |
| `fakoli-state` | 8 skills, 6 agents, hooks, MCP | Compatible | Manifest declares `mcpServers: "./.mcp.json"`; hooks and MCP paths use `${CLAUDE_PLUGIN_ROOT}`. Agents use `tools`. |
| `fakoli-style` | 1 skill | Compatible | `style-ops` uses documented skill frontmatter and description-driven invocation. |
| `gws` | 15 commands, 100 skills, 11 agents, hooks | Compatible | Agent `allowed_tools` was replaced with `tools`. Old skill `trigger` and `version` fields were removed; replacement is description-driven skill invocation. |
| `handoff` | 2 commands, 2 skills, hooks | Compatible | Unsupported `author.github` was replaced by `author.url`. Missing `/handoff` and `/recall` command wrappers were added. |
| `marketplace-manager` | 4 commands, 1 skill | Compatible with cleanup note | Manifest validates. Some command files include `name:` frontmatter; command identity should continue to come from the filename, so this is a cleanup candidate rather than a load blocker. |
| `nano-banana-pro` | 5 commands, 1 skill, 5 agents | Compatible with cleanup note | Agent `allowed-tools` was replaced with `tools`; command argument metadata now uses `argument-hint`. Some command files include `name:` frontmatter, which is harmless but not needed for filename-derived commands. |
| `notebooklm-enhanced` | 7 commands, 2 skills, 1 agent | Compatible | README now documents both `notebooklm-core` and `notebooklm-research`; no command removal found. |
| `quick-notes` | 1 command, 2 skills | Compatible | `/note` still exists. Export behavior now writes `notes.md` next to `$NOTES_LOG` / `~/technical-notes/notes.jsonl` instead of into plugin code. |
| `safe-fetch` | 3 commands, 1 skill, 1 agent, hooks, MCP | Compatible with config caveat | `mcpServers` resolves to `.mcp.json`; hooks use wrapper shape, matchers, timeouts, and `${CLAUDE_PLUGIN_ROOT}`. `/search` requires runtime Brave API configuration. |
| `session-retro` | 1 command, 1 skill | Compatible | The advertised `/session-retro` command wrapper now exists. Skill frontmatter uses `user-invocable`. |

## Behavior Preservation And Replacements

No active plugin lost a currently advertised Claude Code command without a
documented replacement. The notable refresh changes are:

- `fakoli-crew`: plugin-surface critic agents were split into
  `fakoli-plugin-critic`. Existing workflows should install and invoke
  `fakoli-plugin-critic` for structure, skill, agent, hook, and MCP reviews.
- `fakoli-flow`: live smoke tests showed `/flow` and `/flow:brainstorm` are not
  recognized by Claude Code, while `/fakoli-flow:flow` and
  `/fakoli-flow:brainstorm` route correctly. The documented replacement is the
  namespaced Claude Code plugin form: `/fakoli-flow:<skill>`.
- `gws`: unsupported skill `trigger` and `version` metadata was removed.
  Skills now rely on Claude Code's description-driven skill selection.
- `handoff`: the previously documented slash commands are now backed by real
  command files, so no replacement is needed.
- `marketplace-manager`: stale `extended.category`, `extended.tags`, and
  JSON component guidance was replaced with `keywords`, marketplace/registry
  metadata, and Markdown component files.
- `nano-banana-pro`: old structured command `arguments` metadata was replaced
  with `argument-hint` plus command-body parsing examples.
- `quick-notes`: export output moved from plugin code to the active notes log
  directory, preserving the documented user-data location.
- `safe-fetch`: `/fetch` now uses `$ARGUMENTS`; the skill search API documents
  `country` and `city`; hooks use Claude Code's hook-specific permission deny
  output rather than relying only on a legacy top-level block decision.
- `session-retro`: the advertised `/session-retro` command was added, and the
  skill frontmatter key was corrected from `user_invocable` to
  `user-invocable`.

## Remaining Caveats

- `fakoli-flow` no longer documents the unsupported `/flow:<skill>` shorthand.
  Users should invoke `/fakoli-flow:<skill>`.
- `safe-fetch` search depends on runtime configuration for `BRAVE_API_KEY`.
  The plugin loads without it, but `/search` should report missing config until
  the key is provided.
- Marketplace metadata fields that are useful to this repository's registry
  (`displayName`, `repository`, `categories`) are not load-bearing in Claude
  Code and are intentionally ignored by the Claude validator.
- Command `name:` frontmatter in `marketplace-manager` and `nano-banana-pro`
  appears harmless but redundant because Claude Code command names are
  filename-derived.

## Verification Commands

These commands were run from the repository root:

```bash
claude --version
for d in plugins/*/; do claude plugin validate "$d"; done
claude plugin validate .claude-plugin/marketplace.json
./scripts/validate.sh
./scripts/test-path-resolution.sh
claude -p "/flow"
claude -p "/flow:brainstorm"
claude -p "/fakoli-flow:flow"
claude -p "/fakoli-flow:brainstorm Please do not write files; just say READY if this command route is recognized."
test -f docs/compatibility.md && grep -qi 'claude code' docs/compatibility.md
for d in plugins/*/; do python -m json.tool "$d/.claude-plugin/plugin.json" > /dev/null || echo "BAD: $d"; done
```
