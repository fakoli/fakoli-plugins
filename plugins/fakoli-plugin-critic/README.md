# fakoli-plugin-critic

Five specialist critic agents that audit Claude Code plugin surfaces. Extracted from `fakoli-crew` in May 2026 so plugin-development teams can install only the review layer without pulling the eight-agent generalist crew.

## What's in here

| Agent | Color | Audits |
| --- | --- | --- |
| **agent-critic** | magenta | `<plugin>/agents/*.md` — frontmatter, color collisions, tools tightness, description-must-have-3-examples discipline, silent-failure antipatterns (`allowed-tools:` on agents) |
| **skill-critic** | teal | `<plugin>/skills/*/SKILL.md` — frontmatter, one-question-at-a-time discipline, hard-gate presence, lazy-loading, no-fuzzy-detection rule |
| **hook-critic** | gray | `<plugin>/hooks/*.sh` + `hooks.json` — shebang portability, `${CLAUDE_PLUGIN_ROOT}` usage, stdin handling per event, contract-awareness (`set -e` vs `set -euo pipefail` per declared contract) |
| **mcp-critic** | white | `.mcp.json` + MCP server source — schema validity, `@mcp.tool()` decoration discipline, typed parameter annotations, secret-leak in errors, actor identification on mutating tools |
| **structure-critic** | brown | `plugin.json` + marketplace.json + registry index + README counts + CHANGELOG Keep-a-Changelog discipline + version-string sync across every source of truth |

All five run on Opus by default — plugin auditing rewards deep reasoning over speed.

## Installation

```bash
/plugin install fakoli-plugin-critic
```

Or via the marketplace at `fakoli-plugins`.

## Usage

Dispatch any critic via the agent tool. The plugin name is `fakoli-plugin-critic`:

```
Agent({
  subagent_type: "fakoli-plugin-critic:hook-critic",
  prompt: "Review the hook layer in plugins/my-plugin/hooks/."
})
```

Each critic returns a structured report keyed by severity:

- **MUST FIX** — broken or unsafe; merge-blocking.
- **SHOULD FIX** — quality regression or convention drift; fix before next release.
- **CONSIDER** — judgment call worth thinking about.
- **NIT** — style or polish; optional.

Critics report; they do not edit. Pair them with an implementation agent (e.g. `fakoli-crew:smith` for plugin structure or `fakoli-crew:welder` for refactors) to land the fixes.

## What's *not* in here

- **Code review** — the general `fakoli-crew:critic` agent handles Staff-Engineer-level review of arbitrary source code. Use it when reviewing the implementation inside `bin/` or `src/`, not the plugin's surface.
- **End-to-end validation** — `fakoli-crew:sentinel` runs commands and reports binary PASS/FAIL scorecards. Use it after a critic recommends fixes and an implementer applies them.

## Migration from `fakoli-crew` (≤ 2.2.0)

If you previously dispatched these critics as `fakoli-crew:agent-critic` / `fakoli-crew:hook-critic` / etc., update the namespace prefix to `fakoli-plugin-critic:` and install this plugin. The agent system prompts are unchanged in this release — only the namespace moved.

`fakoli-crew` 2.3.0 drops the 5 critics from its agent set and downgrades its description from "thirteen agents" to "eight agents." Existing recipes that already depended on `fakoli-crew` continue to work for the remaining 8 generalist roles.

## License

MIT — see [LICENSE](LICENSE).
