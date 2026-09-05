---
name: plugin-review
description: Review plugin manifests, skills, hooks, MCP configuration, and specialist agent definitions for concrete defects. Use when auditing a Codex or Claude Code plugin, checking marketplace readiness, or investigating why a bundled capability is unavailable.
---

# Plugin Review

Identify the target host and actual plugin root before applying any checklist. A Markdown role file
is not automatically a registered Codex agent type. Inspect the current tool/agent inventory and
inherit the current model settings. Perform focused review locally when delegation is unavailable;
when parallel agents are available and authorized, assign independent read-only scopes.

Read the specialist reference for each changed surface:

| Surface | Reference |
| --- | --- |
| Manifests, catalog paths, versions | [Structure critic](../../agents/structure-critic.md) |
| Skill triggers and executable workflows | [Skill critic](../../agents/skill-critic.md) |
| Hook events, paths, failure behavior | [Hook critic](../../agents/hook-critic.md) |
| MCP wiring, transport and secret handling | [MCP critic](../../agents/mcp-critic.md) |
| Host-specific agent configuration | [Agent critic](../../agents/agent-critic.md) |

These legacy checklists include Claude conventions and project preferences. Apply the target
host's current contract rather than treating every preference as a universal requirement:

- Codex uses `.codex-plugin/plugin.json`; keep skills under a declared/discoverable skill directory.
  Do not add unsupported `agents` or `commands` keys just because those folders exist.
- Resolve marketplace local sources from the marketplace root, and manifest paths from the plugin
  root. Read actual resolved files. Preserve other source types, policies and ordering.
- Hooks are supported in current Codex, but event coverage, trust and payloads depend on the host.
  `${PLUGIN_ROOT}` is the native root variable; `${CLAUDE_PLUGIN_ROOT}` is compatible in documented
  Codex hook contexts. Verify the actual context before reporting a portability defect.
- Core Agent Skills metadata requires a valid name and meaningful description. Three examples,
  minimum 250-character descriptions, mandatory hard gates and specific model tiers are local
  preferences unless the repository explicitly requires them.
- `agents/openai.yaml` can contain invocation policy without an interface block. Runtime tool names
  and transports come from the exposed schema; do not require invented MCP prefixes or pre-allows.
- Skill references should load on demand. Read the files needed to validate the changed behavior;
  do not demand eager loading of the entire bundle to conduct a small scoped review.

Trace each suspected defect from trigger to effect, cite the relevant file/line and applicable
contract, and reproduce it safely when possible. Do not run hook commands, send messages, install
plugins, or invoke remote mutating tools merely to audit their declarations. Tests may use temp
fixtures or mocked servers. Mark unreproduced concerns `SUSPECTED` and explain the missing evidence.

Return only actionable findings with severity, trigger, effect, evidence and a concrete fix, followed
by checks performed and limitations. Separate MUST FIX correctness/contract failures from SHOULD FIX
maintenance issues and optional advice. A clean review is a valid result. Critics report; edits are
made only when the user also requested fixes.

Current primary references: [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins),
[Agent Skills](https://agentskills.io/specification), and the target host's current hook/MCP docs.
