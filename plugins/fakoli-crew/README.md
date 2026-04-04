# fakoli-crew

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Plugin Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](.claude-plugin/plugin.json)

Eight specialized AI agents — TypeScript architect, code reviewer, API researcher, plugin
engineer, integration specialist, documentation writer, infrastructure keeper, and QA
validator — that run independently or as coordinated multi-wave crews for complex
development projects.

## Installation

```bash
claude plugin install fakoli-crew
```

## Available Agents

| Agent | Role | Trigger Phrases |
|-------|------|-----------------|
| **guido** | TypeScript architect | "design an interface", "make this more TypeScript", "create an interface" |
| **critic** | Code reviewer | "review this code", "find the bugs", "audit the imports" |
| **scout** | Researcher | "explore this codebase", "look up the API docs", "map the dependencies" |
| **smith** | Plugin engineer | "update the manifest", "add a command", "set up the hooks" |
| **welder** | Integration engineer | "wire up the new", "refactor to use", "connect these modules" |
| **herald** | Documentation writer | "improve the README", "make this appealing", "rewrite the description" |
| **keeper** | Infrastructure engineer | "update CLAUDE.md", "fix the CI", "sync the registry" |
| **sentinel** | QA engineer | "validate everything", "run all tests", "check if this is ready" |

## Using Agents Individually

Each agent is a focused expert. Invoke one directly when you know what you need:

```
/agent:guido Design a Provider interface for the new TTS backend.

/agent:critic Review src/client.py for correctness and TypeScript style.

/agent:scout Read the Stripe API docs and map the endpoints we need.

/agent:smith Add a `tts generate` command to the plugin manifest.

/agent:welder Wire the new ProviderProtocol into the existing TTSClient.

/agent:herald Rewrite the README — make it appealing to first-time visitors.

/agent:keeper Sync CLAUDE.md and marketplace.json after the restructure.

/agent:sentinel Validate everything before we tag v2.0.0.
```

## Pre-Built Crews

Use the crew skill when a task spans multiple concerns:

### Code Quality
**guido + critic + sentinel** — audit and improve an existing codebase.

```
critic finds issues (with severity ratings) →
guido rewrites with idiomatic TypeScript alternatives →
sentinel validates with a pass/fail scorecard
```

### Plugin Development
**smith + guido + sentinel + herald** — ship a new plugin or major feature.

```
scout researches existing patterns →
smith builds the manifest, guido builds the code →
sentinel validates, herald writes the README
```

### Research & Build
**scout + guido + welder + critic** — integrate an external API you haven't used before.

```
scout maps the API →
guido designs the wrapper interface →
welder wires it in →
critic reviews the integration
```

### Documentation Sprint
**herald + keeper + sentinel** — rewrite docs, update infrastructure, verify consistency.

```
herald rewrites READMEs and descriptions →
keeper updates CLAUDE.md, CI, contributor docs →
sentinel verifies all sources are in sync
```

### Full Overhaul
**All 8 agents in 5 waves** — major version bump, structural refactor, or public launch prep.

## The Wave Pattern

Crews execute in waves to manage dependencies. No two agents write the same file.

```
Wave 1 — Research  (parallel): scout + critic gather information
Wave 2 — Build     (parallel): guido + smith + herald create new artifacts
Wave 3 — Integrate (sequential): welder wires everything together
Wave 4 — Review    (parallel): critic + sentinel validate the result
Wave 5 — Judge     (main window): review scorecard, send back for fixes if needed
```

Each agent writes a status file to `docs/plans/agent-<name>-status.md` with its
decisions, files modified, and notes for downstream agents. This is how agents
coordinate without a shared conversation.

## Commands

| Command | Description |
|---------|-------------|
| `/crew` | List all 8 agents and suggested crew compositions |

## Agent Design Principles

**guido** applies TypeScript naming conventions, strict typing, interface-first design, and generics.
Reviews with severity levels: MUST / SHOULD / CONSIDER / NIT.

**critic** reads line by line, proposes alternative implementations, and never approves
code that swallows exceptions, uses mutable defaults, or lacks type annotations.

**scout** explores before concluding. Reads actual source files and official docs rather
than guessing. Reports what it found, not what it expected to find.

**smith** follows the plugin manifest schema precisely. Validates every field before
writing. Cross-references CLAUDE.md to confirm nothing is missing.

**welder** reads ALL upstream agent files before modifying anything. Maintains backward
compatibility through re-exports and facade patterns. Runs tests after every change.

**herald** writes for strangers, not existing users. Starts with a concrete value
proposition. Never writes "A tool for X" — always says what X specifically does.

**keeper** keeps every source of truth in sync: CLAUDE.md, marketplace.json, registry,
CI workflows, and contributor docs. Makes surgical edits, never wholesale rewrites.

**sentinel** produces a binary pass/fail scorecard for every check. Reports exact error
output. Names the fix owner for every failure. Never modifies code itself.

## Requirements

- Claude Code with plugin support
- No external dependencies — agents use built-in Claude Code tools only

## Author

Sekou Doumbouya — [github.com/fakoli](https://github.com/fakoli)

## License

MIT — see [LICENSE](LICENSE)
