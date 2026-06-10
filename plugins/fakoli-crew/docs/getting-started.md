# Getting Started with Fakoli Crew

## Installation

```bash
claude plugin install fakoli-crew
```

## Your First Agent

The simplest way to start is with a single agent:

```
/agent:critic Review the authentication module for security issues.
```

The critic will read every file in scope, then produce a structured report with MUST FIX / SHOULD FIX / CONSIDER findings.

## Your First Crew

When a task spans multiple concerns, use a crew:

```
/agent:guido Design an interface for the new payment processor.
```
Wait for guido to finish, then:
```
/agent:welder Wire the new interface into the existing checkout flow.
```
Then:
```
/agent:critic Review the integration for correctness and backward compatibility.
```

## The Critic Gate Pattern

The most impactful workflow discovery from real-world use:

**Run critic after every code write.**

In the BAARA Next project (10-package monorepo, 44K lines), running critic after each build wave caught:
- 10 MUST FIX bugs in Phase 1 (state machine violations, broken API contracts, security holes)
- 5 MUST FIX bugs in Phase 4 (wrong HTTP methods, missing SSE fields, phantom imports)
- 4 MUST FIX bugs in Phase 5 (migration data corruption, missing schemas)
- 7 additional MUST FIX bugs across Phases 2, 3, and 6

Total: 26 runtime bugs caught before they ever ran across all 6 phases. The cost of a critic pass is ~2 minutes. The cost of debugging a compounded state machine violation is hours.

## Model Selection

Claude Code agents keep Claude-specific model tiers in `agents/*.md`:

| Tier | Agents |
|------|--------|
| `opus` | `guido`, `critic` |
| `sonnet` | `scout`, `smith`, `welder`, `herald`, `keeper` |
| `haiku` | `sentinel` |

OpenAI/Codex model selection lives in `.codex/agents/fakoli-*.toml` companion
files so Claude ignores it. Those files map the same roles to OpenAI models:

| OpenAI model | Agents |
|--------------|--------|
| `gpt-5.5` | `fakoli_guido`, `fakoli_critic` |
| `gpt-5.4` | `fakoli_scout`, `fakoli_smith`, `fakoli_welder`, `fakoli_herald`, `fakoli_keeper` |
| `gpt-5.4-mini` | `fakoli_sentinel` |

### Cursor

Cursor selection lives in `.cursor/agents/fakoli-*.md` companion files (and a
`.cursor-plugin/plugin.json` manifest), so Claude ignores them. Each companion
points back at the canonical `agents/<role>.md` prompt rather than forking it.

Cursor does **not** honor a per-subagent tool allowlist, so the Claude `tools:`
field cannot transfer directly. The closest faithful mapping is Cursor's
`readonly` flag, applied to the roles whose Claude tools are read-only:

| `readonly` | Agents | Rationale |
|------------|--------|-----------|
| `true` | `fakoli-critic`, `fakoli-sentinel` | review/validate only — "critics report, they don't fix" |
| `false` | `fakoli-guido`, `fakoli-scout`, `fakoli-smith`, `fakoli-welder`, `fakoli-herald`, `fakoli-keeper` | these roles write or edit files |

Companion `model` is `inherit` (Cursor runs the user-selected model). Cursor
encodes reasoning effort in the model ID (e.g. `-high` variants) rather than a
separate field, so per-role Cursor model IDs are left unset until verified
against a live Cursor install.

## Workflow Orchestration

To get automatic wave dispatch, critic gates, and status file management, install
**fakoli-flow** alongside fakoli-crew:

```bash
claude plugin install fakoli-flow
```

See [workflow-orchestration.md](workflow-orchestration.md) for the full comparison between
fakoli-flow and SuperPowers orchestration. The [fakoli-flow getting-started guide](https://github.com/fakoli/fakoli-plugins/blob/main/plugins/fakoli-flow/docs/getting-started.md)
walks through a complete session from brainstorm to finish.
