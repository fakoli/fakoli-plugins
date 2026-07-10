# Runtime Compatibility Review

Updated: 2026-07-09 (anvil-pulse, ship-loop, handoff freshness, gate-router added; validation re-run)

This note records the T012 Claude Code compatibility pass and the T013 Codex
compatibility pass for the active plugins under `plugins/`. It focuses on
whether refreshed plugin surfaces still load in their target runtime and whether
runtime-specific behavior now has a documented replacement or graceful
degradation path.

## Compatibility Basis

### Claude Code

The review used the local Claude Code runtime available in this workspace:

- `claude --version`: `2.1.193 (Claude Code)`
- `claude plugin validate plugins/<name>` for every active plugin: passed.
- `claude plugin validate .claude-plugin/marketplace.json`: passed with
  warnings for marketplace-only metadata fields (`displayName`, `repository`,
  `categories`) that Claude Code ignores at load time.
- `./scripts/validate.sh`: passed with 218 checks, 0 warnings, 0 failures
  (re-run 2026-07-09 through gate-router: 327 checks, 0 warnings, 0 failures).
- `./scripts/test-path-resolution.sh`: passed with 27 checks, 0 warnings,
  0 errors (re-run 2026-07-09 with anvil-pulse: 44 checks, 0 warnings, 0 errors).
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

### Codex

The Codex compatibility pass used the current Codex desktop session and local
plugin cache as the runtime surface:

- Codex curated plugins use `.codex-plugin/plugin.json`.
- Codex plugin manifests point at `skills`, optional `mcpServers`, and optional
  `apps`. Skills are the main model-facing compatibility surface.
- Codex skills are exposed by skill name, usually prefixed by plugin name in
  this session, such as `handoff:recall` and `nano-banana-pro:generate`.
- Codex does not expose this marketplace's Claude Code slash commands as
  slash commands in the current session.
- Codex does not expose this marketplace's Claude Code `agents/` directory as
  custom subagent roles in the current session; use Codex's available subagent
  tools/roles or the plugin skill's inline fallback strategy.
- Codex does not run this marketplace's Claude Code `hooks/hooks.json` in the
  current session. Hook behavior should be treated as Claude Code only unless a
  Codex-specific hook surface is added.
- Codex can use MCP/app tools when a Codex plugin manifest wires them through
  `mcpServers` or `apps`. Claude-only `.claude-plugin/plugin.json` MCP entries
  should be treated as requiring Codex-side verification before being promised.
- Local Codex cache evidence confirms the installed `handoff` and
  `nano-banana-pro` fakoli plugins expose their `skills/` payloads in this
  session, even though those cached copies still carry `.claude-plugin`
  manifests rather than Codex-native manifests.

## Claude Code Plugin Matrix

| Plugin | Runtime surface | Compatibility status | Notes |
| --- | --- | --- | --- |
| `anvil-pulse` | 1 command, 1 skill, server scripts | Compatible | Dependency-free Node dashboard server with PID-file lifecycle; `/pulse` wraps the `pulse` skill. Statusline segment is opt-in and edits only the user's own statusline script on request. |
| `cli-to-plugin` | 1 command | Compatible | Minimal manifest and `/cli-to-plugin` command validate. Generated skill templates use hyphenated skill frontmatter. |
| `excalidraw-diagram` | 1 command, 1 skill, 1 agent | Compatible | Skill uses `allowed-tools`; agent uses `tools`; all components are in standard auto-discovered directories. |
| `fakoli-crew` | 1 command, 2 skills, 9 agents | Compatible | Agent frontmatter uses `tools`; the 9-agent roster is documented. Older plugin-surface critic roles now live in `fakoli-plugin-critic`. |
| `fakoli-flow` | 1 command, 6 skills, hooks | Compatible | `/fakoli-flow:flow`, `/fakoli-flow:brainstorm`, and hooks validate. The unsupported short `/flow` and `/flow:<skill>` aliases were replaced in docs with the Claude Code plugin namespace. |
| `fakoli-plugin-critic` | 5 agents | Compatible | Agents use `tools` and are standard Claude Code subagent files. No command or skill surface is advertised. |
| `fakoli-speak` | 7 commands, hooks | Compatible | Command surface is intact. `/voices` now documents `OPENAI_TTS_VOICE`, matching the implementation. |
| `fakoli-state` | 8 skills, 6 agents, hooks, MCP | Compatible | Manifest declares `mcpServers: "./.mcp.json"`; hooks and MCP paths use `${CLAUDE_PLUGIN_ROOT}`. Agents use `tools`. |
| `fakoli-style` | 1 skill | Compatible | `style-ops` uses documented skill frontmatter and description-driven invocation. |
| `gate-router` | 1 command, 1 skill, 1 script | Compatible | Script-backed; no hooks. |
| `gws` | 15 commands, 100 skills, 11 agents, hooks | Compatible | Agent `allowed_tools` was replaced with `tools`. Old skill `trigger` and `version` fields were removed; replacement is description-driven skill invocation. |
| `handoff` | 2 commands, 2 skills, hooks, 3 scripts | Compatible | Unsupported `author.github` was replaced by `author.url`. Missing `/handoff` and `/recall` command wrappers were added. |
| `marketplace-manager` | 4 commands, 1 skill | Compatible with cleanup note | Manifest validates. Some command files include `name:` frontmatter; command identity should continue to come from the filename, so this is a cleanup candidate rather than a load blocker. |
| `nano-banana-pro` | 5 commands, 1 skill, 5 agents | Compatible with cleanup note | Agent `allowed-tools` was replaced with `tools`; command argument metadata now uses `argument-hint`. Some command files include `name:` frontmatter, which is harmless but not needed for filename-derived commands. |
| `notebooklm-enhanced` | 7 commands, 2 skills, 1 agent | Compatible | README now documents both `notebooklm-core` and `notebooklm-research`; no command removal found. |
| `quick-notes` | 1 command, 2 skills | Compatible | `/note` still exists. Export behavior now writes `notes.md` next to `$NOTES_LOG` / `~/technical-notes/notes.jsonl` instead of into plugin code. |
| `safe-fetch` | 3 commands, 1 skill, 1 agent, hooks, MCP | Compatible with config caveat | `mcpServers` resolves to `.mcp.json`; hooks use wrapper shape, matchers, timeouts, and `${CLAUDE_PLUGIN_ROOT}`. `/search` requires runtime Brave API configuration. |
| `ship-loop` | 1 command, 1 skill | Compatible | Procedural skill (no scripts/hooks); `/ship-loop` wraps the skill. |
| `session-retro` | 1 command, 1 skill | Compatible | The advertised `/session-retro` command wrapper now exists. Skill frontmatter uses `user-invocable`. |

## Codex Plugin Matrix

| Plugin | Codex-supported surface | Codex status | Degradation or documentation strategy |
| --- | --- | --- | --- |
| `anvil-pulse` | `pulse` skill | Skill-compatible | Codex has no statusline/UI extension point, so the local web dashboard IS the display surface; start the server in a persistent terminal (`--foreground`; detached processes are reaped). Claude command wrapper and statusline segment do not carry over. |
| `cli-to-plugin` | None currently; ships only a Claude command | Not Codex-exposed | Keep Claude command support. Add a Codex skill wrapper before promising first-class Codex use. |
| `excalidraw-diagram` | `excalidraw` skill | Skill-compatible | Use the skill as `excalidraw-diagram:excalidraw` when installed. Claude command and agent are not Codex-first surfaces; converter path guidance should resolve relative to the installed skill/plugin root. |
| `fakoli-crew` | `crew-ops`, `debugging` skills | Skill-compatible with agent degradation | Skills can guide work. Claude custom agents (`guido`, `critic`, `warden`, etc.) should degrade to Codex subagents/roles available in the session or inline execution. The repo's `.codex/agents` files are not treated as a plugin runtime surface here unless separately installed/exposed. |
| `fakoli-flow` | 6 workflow skills | Skill-compatible with hook degradation | Use Codex skill invocation (`fakoli-flow:brainstorm`, `fakoli-flow:plan`, `fakoli-flow:execute`, `fakoli-flow:verify`, `fakoli-flow:finish`, `fakoli-flow:quick`) when installed. Claude slash commands and hook-enforced critic gates do not carry over; Codex runs should enforce gates procedurally with subagents and verification evidence. |
| `fakoli-plugin-critic` | None currently; ships only Claude agents | Not Codex-exposed | Keep as Claude Code agent pack. Add review skills if Codex should invoke these critics directly. |
| `fakoli-speak` | None currently; ships Claude commands and a Stop hook | Not Codex-exposed | Do not promise automatic Codex TTS behavior. A Codex skill or app/tool integration is required before Codex support. |
| `fakoli-state` | 8 Anvil-style skills; MCP requires Codex verification | Skill-compatible, MCP unverified | Skills can guide the workflow in Codex. Claude hooks are unavailable. MCP should be promised only after a Codex `.codex-plugin` manifest or installed-tool check proves the server is exposed; existing MCP paths also need Codex runtime path-variable verification. |
| `fakoli-style` | `style-ops` skill | Skill-compatible | Use as a Codex skill for ledger work. |
| `gate-router` | `gate-check` skill | Skill-compatible | Same bash script runs under Codex; Claude slash wrapper does not carry over. |
| `gws` | 100 Google Workspace skills | Skill-compatible with command/agent/hook degradation | Skills document Google Workspace workflows. Claude slash commands, custom agents, and SessionStart hook do not carry over to Codex without adapters, so users should manually verify `gws` CLI/auth readiness. |
| `handoff` | `handoff`, `recall` skills (0.2.0 freshness is skill-driven bash, so it carries to Codex) | Confirmed in Codex cache | Current Codex session can load the fakoli `handoff` skills. Claude slash wrappers and SessionStart hook are not required for Codex use; no automatic startup recall banner should be expected. |
| `marketplace-manager` | `marketplace-manager` skill | Skill-compatible | Use the skill for Codex marketplace maintenance. Claude slash commands need Codex wrappers before being promised. |
| `nano-banana-pro` | `generate` skill | Confirmed in Codex cache | Current Codex session can load the `nano-banana-pro:generate` skill. Claude slash commands and custom agents are not Codex-first surfaces; use the skill/scripts path and direct `uv run` fallback. |
| `notebooklm-enhanced` | `notebooklm-core`, `notebooklm-research` skills | Skill-compatible, external CLI dependent | Codex can use skills when installed, but NotebookLM CLI/auth remains a runtime dependency. Claude commands, slash setup examples, and research-agent delegation do not automatically become Codex surfaces. |
| `quick-notes` | `take-note`, `find-notes` skills | Skill-compatible | Codex users should invoke skills rather than the Claude `/note` command. File behavior remains local and portable. |
| `safe-fetch` | `safe-fetch` skill; MCP requires Codex verification | Skill-compatible, MCP unverified | Skill can document safe-fetch practice. MCP-backed commands/search require Codex tool exposure before being promised; Claude hooks blocking WebFetch/WebSearch do not intercept Codex web or shell behavior. |
| `ship-loop` | `ship-loop` skill | Skill-compatible | The procedure is fully expressible as a Codex skill; the Claude slash wrapper does not carry over. |
| `session-retro` | `session-retro` skill | Skill-compatible | Codex can run the local-log analysis as a skill. Claude `/session-retro` command is a Claude wrapper, not the Codex invocation surface. |

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

For Codex, the compatibility rule is skills-first:

- Claude Code slash commands degrade to Codex skill invocation or are documented
  as Claude-only until a Codex command wrapper exists.
- Claude Code custom agents degrade to Codex subagents/roles available in the
  session, or to inline execution with the same review/verification protocol.
- Claude Code hooks degrade to documentation and procedural checks unless a
  Codex-specific hook or automation surface is introduced.
- MCP support is only promised where Codex exposes the MCP/app tools. Existing
  `.claude-plugin` `mcpServers` entries remain Claude-compatible, but Codex
  support must be verified per installation.

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
- Codex compatibility is strongest for plugins that ship skills. Command-only,
  agent-only, and hook-only plugins need Codex-specific wrappers before being
  represented as fully supported in Codex.
- This repository still uses `.claude-plugin/plugin.json` for the marketplace.
  Codex-native marketplace packaging would require `.codex-plugin/plugin.json`
  manifests with `skills`, optional `mcpServers`, optional `apps`, and Codex
  interface metadata.

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
grep -qi 'codex' docs/compatibility.md
grep -qi 'claude code' docs/compatibility.md && grep -qi 'codex' docs/compatibility.md
```
