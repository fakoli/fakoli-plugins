# fakoli-state

Local-first project state engine: turn brainstorms and PRDs into reviewed, lockable, evidence-backed work packets that humans and AI agents can coordinate on without conflicts.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Plugin Version](https://img.shields.io/badge/version-1.9.0-blue.svg)](.claude-plugin/plugin.json)
[![Status](https://img.shields.io/badge/plugin--state-alpha%20%2F%20in--development-orange.svg)](.claude-plugin/plugin.json)

---

## What it is

fakoli-state is the third pillar of the Fakoli plugin ecosystem. `fakoli-flow` defines how work moves through a pipeline; `fakoli-crew` defines who does the work; fakoli-state defines **what is true** — the canonical, durable record of every requirement, task, claim, and piece of evidence in your project.

It stores project state in a local SQLite database under `.fakoli-state/`, never in chat history or an issue tracker. When an AI agent claims a task, that claim is an enforced database row with a lease and a heartbeat — not a convention in a markdown file that the next agent can silently overwrite.

The plugin ships a CLI for pure state operations, an MCP server that exposes 13 agent-facing tools to any runtime (Claude Code, Codex, Cursor, OpenHands, Copilot), and a set of skills and hooks that enforce coordination discipline the model would otherwise forget.

---

## Why this exists — the 5 must-do-better

AI coding agents need shared, durable project state that is not trapped in chat history or buried in an issue tracker. Current tools leave five gaps:

1. **Richer canonical state than issue text.** GitHub Issues store requirements as free-form markdown body. fakoli-state uses Pydantic v2 models backed by SQLite — structured, queryable, and validated at every transition.

2. **Explicit claim / lock / lease model.** Issue assignment and labels imply ownership but do not enforce it. fakoli-state records a `Claim` row with an expiry timestamp; stale leases are detected and released automatically on every CLI or MCP operation.

3. **LLM-optimized work packets.** An agent should receive exactly what it needs — intent, acceptance criteria, scope, constraints, non-goals — not an entire issue thread. `fakoli-state packet T012` renders a compact, task-specific markdown or JSON packet from canonical state.

4. **Six-dimension task scoring.** Tasks carry scores for complexity, parallelizability, context load, blast radius, review risk, and agent suitability. These drive routing decisions and surface expand recommendations before an agent wastes time on an under-specified task.

5. **Runtime-neutral integration via CLI + MCP.** The state engine is not coupled to any single agent runtime. The CLI works from any shell; the MCP server (FastMCP, stdio) integrates with any MCP-compatible agent.

---

## Installation

fakoli-state is not yet in the marketplace. Clone from the monorepo and wire the plugin manually:

```bash
git clone https://github.com/fakoli/fakoli-plugins.git
cd fakoli-plugins/plugins/fakoli-state
```

Then add the plugin path to your Claude Code plugin configuration.

Once published, install via `/plugin install fakoli-state` from the fakoli marketplace.

---

## Quick Start

> **Status: Coming in v1.1 — currently scaffolding (Phase 1 of 8)**

The intended first-run experience will be:

```bash
# Initialize state for your project
fakoli-state init --name "My Project"

# Author a PRD against the provided template
$EDITOR .fakoli-state/prd.md

# Parse, review, and lock the PRD
fakoli-state prd parse
fakoli-state prd review --approve

# Generate features and tasks; score and expand
fakoli-state plan
fakoli-state score
fakoli-state expand T001
fakoli-state review tasks

# Pick and claim the next task
fakoli-state next
fakoli-state claim T001          # auto-creates branch agent/t001-<slug>

# Get the work packet for the active task
fakoli-state packet T001

# Submit evidence and apply
fakoli-state submit T001 --commands "pytest" --output-file out.log --files-changed src/foo.py
fakoli-state apply T001
```

The `fakoli-state init` command scaffolds a `.fakoli-state/` directory in your project containing `config.yaml`, `state.db`, `events.jsonl`, `prd.md`, a `packets/` directory, and optional `snapshots/`.

---

## Architecture overview

The canonical specification for fakoli-state is at:
[`docs/specs/2026-05-24-fakoli-state-v0.md`](docs/specs/2026-05-24-fakoli-state-v0.md)

That document defines the data model, CLI command set, MCP tool surface, hook event mappings, phasing plan, and integration contracts with fakoli-flow and fakoli-crew.

### Component responsibilities

| Layer | What it does |
|---|---|
| Skills | Workflow choreography: brainstorm, prd, plan, claim, execute, verify, finish, state-ops |
| CLI (`fakoli-state`) | Pure state operations — CRUD, scoring, packet generation, sync |
| MCP server | 13 agent-facing tools exposed via stdio to any MCP-compatible runtime |
| Hooks | Enforce claim discipline, record file changes, capture test evidence |
| State engine | SQLite backend + append-only JSONL event log |
| Claims manager | Atomic SQLite transactions; stale lease detection on every operation |
| Planning engine | Deterministic template-based PRD parser; optional LLM augmentation |
| Context engine | Renders work packets as markdown or JSON from canonical state |
| Git ops | Auto-creates `agent/<task>-<slug>` branch on `claim` |
| Sync engine | Bidirectional GitHub Issues projection (polling, opt-in) |

### Per-project state directory

`fakoli-state init` creates this inside your project — not inside the plugin:

```text
<your-project>/.fakoli-state/
├── config.yaml        # project-level config
├── state.db           # SQLite — canonical state
├── events.jsonl       # append-only audit/event log (full replay guarantee)
├── prd.md             # PRD source
├── packets/           # generated work packets (T001.md, T001.json, ...)
└── snapshots/         # opt-in periodic snapshots
```

The event log is a hard guarantee: replaying `events.jsonl` from scratch against an empty database reconstructs `state.db` exactly.

---

## Build status

fakoli-state is built in 9 phases. Each phase ships as its own PR into the fakoli-plugins monorepo. Phases 1–8 shipped in PRs #38–#49; Phase 9 (this release, v1.9.0) closes the audit-honesty deferrals from Phase 8 and the Phase 7 LLM-augmentation cleanup.

| Phase | Name | Status |
|---|---|---|
| 1 | Plugin skeleton: manifest, README, LICENSE, CHANGELOG, `bin/` wrappers, `pyproject.toml`, `--version` stub | Done (v1.0.0) |
| 2 | State engine: models, SQLite backend, JSONL event log, `init`/`status` CLI, state-ops skill, `detect-state.sh` hook | Done (v1.1.0) |
| 3 | Planning engine: `prd parse`/`prd review`/`plan`/`score`/`expand`/`review tasks`, prd/plan skills, planner agent | Done (v1.2.0) |
| 4 | Claims manager: `claim`/`release`/`renew`/`next` CLI, git ops, claim skill, check-claim + record-file-change hooks | Done (v1.3.0) |
| 5 | Context engine: `packet`/`submit`/`apply` CLI, Review engine apply gate, execute/finish skills, critic + sentinel agents | Done (v1.4.0) |
| 6 | MCP server: 13 agent-facing tools, `.mcp.json`, `bin/fakoli-state-mcp` wrapper | Done (v1.6.0) |
| 7 | LLM augmentation: Anthropic provider, `--use-llm` flags, brainstorm skill bridge to fakoli-flow:brainstorm | Done (v1.7.0) |
| 8 | GitHub sync: bidirectional sync engine, `sync` CLI, state-keeper agent, reconciliation, marketplace release | Done (v1.8.0) |
| 9 | Audit honesty + multi-provider config + Phase 7 cleanup + 2 new doc agents (marketplace-scribe, docs-scribe) | Done (v1.9.0) |

---

## Integration with fakoli-flow and fakoli-crew

When both fakoli-state and fakoli-flow are installed, the flow pipeline upgrades automatically:

- `flow:execute` detects fakoli-state, reads `fakoli-state next`, and calls `fakoli-state claim` before each wave. Status files are replaced by `fakoli-state submit`.
- `flow:verify` calls `fakoli-state status` and dispatches the sentinel only on tasks with submitted evidence.
- `flow:finish` calls `fakoli-state apply` per accepted task before the merge or PR.

When both fakoli-state and fakoli-crew are installed, all crew agents gain access to the `fakoli-state-mcp` MCP tool surface. The plugin-owned `agents/critic.md` and `agents/sentinel.md` defer to fakoli-crew specialists when detected.

When fakoli-state is absent, fakoli-flow and fakoli-crew continue to work via their existing markdown-status conventions. Integration is opt-in.

---

## Plugin-owned agents

fakoli-state ships six specialist agents under `agents/`. Each defers outward to the
corresponding fakoli-crew specialist when crew is installed; standalone users get the
fallback behaviour.

| Agent | Color | Owns | Defers to |
|---|---|---|---|
| `planner` | white | PRD-to-tasks transformation, feature/task drafting, expand routing | `fakoli-crew:guido` |
| `critic` | magenta | Code-review verdict on submitted-evidence diffs vs task acceptance criteria | `fakoli-crew:critic` |
| `sentinel` | gray | Verification-command + evidence-completeness scorecard | `fakoli-crew:sentinel` |
| `state-keeper` | teal | Sync drift detection + reconciliation triage across SQLite / FS / git | `fakoli-crew:keeper` |
| `marketplace-scribe` | cyan | `.claude-plugin/marketplace.json`, root README plugin table, `registry/*.json` | `fakoli-crew:keeper` |
| `docs-scribe` | purple | Plugin `docs/` cross-references, `CHANGELOG.md`, `plugin.json.description` | `fakoli-crew:herald` |

The Iron Rule (review agents never `Edit`/`Write`) is enforced at the
`allowed-tools` frontmatter level for `critic`, `sentinel`, `state-keeper`, and
`docs-scribe`; `planner` proposes-but-does-not-mutate (deletion-proof against
hallucinated row writes); `marketplace-scribe` is the only agent that may run
`Bash` (it executes `scripts/generate-index.sh` and validates regenerated
JSON).

Install the full ecosystem:

```bash
claude plugin install fakoli-crew
claude plugin install fakoli-flow
claude plugin install fakoli-state   # once published
```

---

## Background research

The design of fakoli-state is informed by three source documents in [`docs/specs/`](docs/specs/):

- The original vision brief covering PRD authoring, task decomposition, claims and locks, work packets, evidence-based completion, and MCP surface design.
- A competitive gap analysis against CCPM and against issue-tracker-as-state patterns — the source of the "5 must-do-better" list above.
- The Fakoli plugin primer defining the plugin-first, skills-encode-choreography, hooks-enforce-rules operating model.

The canonical spec at [`docs/specs/2026-05-24-fakoli-state-v0.md`](docs/specs/2026-05-24-fakoli-state-v0.md) synthesizes all three into the build plan.

---

## Requirements

- Claude Code with plugin support
- Python 3.11+ with `uv` (resolved on first invocation — no manual install needed)
- fakoli-flow (recommended — enables pipeline integration)
- fakoli-crew (recommended — provides specialist agents)

---

## Author

Sekou Doumbouya — [github.com/fakoli](https://github.com/fakoli)

## License

MIT — see [LICENSE](LICENSE)
