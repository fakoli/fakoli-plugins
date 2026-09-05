---
name: plan
description: "Turn a reviewed Fakoli State PRD into scored, reviewable tasks and a ready queue before implementation."
---

# Plan

Resolve this plugin's installed root from the loaded skill path. Prefer its `bin/fakoli-state` launcher when no matching CLI is on PATH; run from the user's project or pass the command's `--cwd` argument. Read `--help` when a flag is uncertain. Use only tools exposed by the current host. For native MCP calls, supply the target project's absolute `cwd`; the server's startup directory is the installed package.

1. Inspect project state and the current PRD. Resolve decisions that materially change the task graph; follow existing user choices and autonomy constraints. Do not re-ask questions already answered.
2. Run `plan --help`; select deterministic `plan --no-llm` when external model inference is unnecessary. `--use-llm` requires a configured provider and authorization for that service. Inspect the generated features/tasks before proceeding.
3. Run `score`, inspect `list` and `show TASK_ID`, and split tasks whose scope or scores make them unsuitable for one independently verifiable change. `expand TASK_ID --use-llm` proposes subtasks and needs the configured model service. Read its output before adopting changes.
4. Ensure each task has concrete acceptance criteria, likely files, dependencies and runnable verification. Run `review tasks`, then `list --status ready` and `next` to verify the queue.
5. Continue into claiming/execution when authorized. Record unresolved planning decisions and actual blockers instead of forcing repeated option menus.

Replanning can replace generated state. Inspect active claims and evidence first, and do not use `--prune-force` to discard live work. Use `score --help` to check installed LLM support; do not rely on old implementation-phase tables.

See [README](../../README.md) for setup and the full CLI/MCP surfaces.
