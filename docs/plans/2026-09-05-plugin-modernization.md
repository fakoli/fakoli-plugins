# Plugin modernization plan — 2026-09-05

## Scope and baseline

The user's request authorizes autonomous review, substantive fixes and rewrites, current-convention research, and plugin-creator upgrades without questions. The source inventory is 26 active public plugins, two intentionally archived public packages, and two private plugins. The adjacent agent-plugins-private marketplace contains no plugins. Bundled third-party plugins are not forked wholesale.

The initial working tree was at `97f21ae`. Fetching upstream revealed current main `7d39cc36e6ae7062caf4939741f3e9e331c4d85f` with 26 active plugins. Preserve the first-pass fixes in a filesystem snapshot and git stash, create `codex/modernize-plugins-2026-09-05` from that current baseline, and reconcile only useful changes. Do not resurrect packages archived intentionally in `daa5151`.

## Work order

1. **Inventory and baseline:** read source instructions, identify executable and skill entrypoints, compare upstream and local sources, run the existing combined gate.
2. **Research:** use current OpenAI, Anthropic, Agent Skills, CLI/provider documentation and actual local runtime help. Separate normative host requirements from optional catalog polish. Avoid replacing old fixed model names with a new fixed dependency on one assistant.
3. **Parallel capability audit:** repair each package against its intended output, including installed-cache behavior, dependency setup, paths, malformed input, persistent state and failure exits. Add native Codex entrypoints without discarding Claude support.
4. **Shared maintenance:** deterministic dual catalogs, preserved metadata/order/policies, read-only drift checks, complete skill YAML parsing, root/source-aware marketplace operations, a durable copy of the upgraded plugin creator, and coherent templates/CI.
5. **Verification:** retain existing meaningful suites; add regression cases for observed failures. Use isolated fake services and temporary state. Exercise real local builds/conversion where possible. Distinguish these from live authenticated provider tests.
6. **Delivery:** regenerate catalogs, verify all version sources/changelogs, finish a per-plugin report with evidence and remaining runtime conditions, and leave reviewable source changes.

## Ownership

| Group | Packages |
| --- | --- |
| Root integration | Shared scripts/catalogs/templates/CI/docs, marketplace-manager, excalidraw-diagram, fakoli-state, fakoli-style; integration of completed Nano/archive work |
| Image/private agent | nano-banana-pro; private interview-feedback and sekou-voice; then continuity/session utility group |
| Network agent | Archived k8s-sidecar-testing and rust-network-module; then anvil-pulse, fleet-exec, safe-fetch, gws, notebooklm-enhanced, fakoli-speak |
| Creator/orchestration agent | Installed plugin-creator; then cli-to-plugin, fakoli-plugin-critic, fakoli-crew, fakoli-flow, ship-loop, ship-task, systems-thinking |
| Continuity/session group | handoff, quick-notes, session-retro, session-evals, recall-mode-verifier, windows-cli-hygiene, skill-spec-lint, gate-router |

Root performs shared version/catalog reconciliation while agents edit only their packages. This is an explicit coordination exception to invoking the version helper concurrently.

## Completion evidence

Record final commands, outcomes and per-package changes in [the results report](../plugin-modernization-results.md). A schema-valid package alone is not evidence that its workflow, hook or remote integration works. No fabricated credentials, paid API runs, public data migration or live cluster changes are needed for local verification.
