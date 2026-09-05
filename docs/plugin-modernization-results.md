# Plugin modernization results — September 5, 2026

Completed substantive maintenance for all 26 active plugins in this marketplace, their 147 skill entrypoints, two archived packages, and the installed system plugin creator. Two plugins in the separate private marketplace were also repaired and committed there. The adjacent `agent-plugins-private` checkout contains no plugins. Installed third-party marketplaces and unrelated personal skills were outside this source modernization pass.

The [plan](plans/2026-09-05-plugin-modernization.md) and [current conventions](PLUGIN_CONVENTIONS.md) describe scope and maintenance rules. Work starts from current upstream `7d39cc36e6ae7062caf4939741f3e9e331c4d85f` on `codex/modernize-plugins-2026-09-05`. An initial pass against the older checkout was preserved before reconciling with upstream. Archived packages remain archived.

## Changes by active plugin

Every active plugin now has coherent native Codex and Claude manifests. The table records additional capability changes; packaging alone was not treated as proof of behavior.

| Plugin | Version | Meaningful change | Verification and limits |
| --- | --- | --- | --- |
| anvil-pulse | 1.1.0 | Verifies server process and project identity; removes ambiguous workspace matching; bounds statusline work with a cache and stale fallback. | Dashboard smoke assertions and 5 lifecycle tests. |
| cli-to-plugin | 1.1.0 | Generates deterministic dual-host plugins from captured CLI help; handles nested groups and malformed input; refuses accidental overwrite. | 108 tests; 91.72% measured coverage; generated GitHub CLI fixture validated. |
| excalidraw-diagram | 1.1.0 | Repairs stable IDs, arrows, labels, frame membership and scene preservation; validates references and numbers; writes atomically; increases spacing for readable labels. | 7 Node tests; generated scene rendered and visually inspected in actual Excalidraw 0.18.1. |
| fakoli-crew | 2.10.0 | Adds a native routing workflow using available agents and preserving model selection; corrects critic fixtures that confused optional metadata with runtime requirements. | Package/skill checks and fixture inspection; live model critic quality was not evaluated. |
| fakoli-flow | 1.4.0 | Reworks the workflow for actual host tools, optional delegation, existing authorization and explicit completion evidence. | All six skill entrypoints validated; model-driven task quality remains a runtime evaluation. |
| fakoli-plugin-critic | 0.2.0 | Adds a native five-perspective audit workflow and distinguishes host requirements from optional catalog quality. | Native entrypoint and references validated; no claim of measured reviewer accuracy. |
| fakoli-speak | 2.1.0 | Adds owned playback supervision and bounded shutdown; fixes Stop payload handling; reports truncation and cost-estimate limits. | 68 tests; hardware playback and paid TTS calls were not run. |
| fakoli-state | 1.24.0 | Fixes broken distribution builds; launches from a locked external environment while preserving caller cwd; exposes provider extras explicitly; makes all 22 MCP tools accept project cwd; rewrites eight workflows around current commands. | 1,330 tests, 21 hook checks, successful wheel/sdist builds, real native STDIO initialize/tool listing, and 87 in-process MCP tests within the suite. Three live GitHub tests excluded. |
| fakoli-style | 1.3.0 | Adds explicit data/schema/project/output paths; checks real AST definitions and confined evidence paths; distinguishes evidence pointers from executed test results. | 38 tests and validation of the existing generated ledger projection. |
| fleet-exec | 1.0.1 | Rejects malformed requests before SSH; recovers from protocol errors; improves timeout handling; adds native MCP startup metadata. | 84 tests with controlled transports; no live fleet commands. |
| gate-router | 1.1.0 | Uses NUL-safe changed paths; rejects invalid refs and rules; preserves inert argv; corrects multi-file shell examples. | 22 shell checks plus Python regression cases. |
| gws | 0.4.2 | Aligns shared authentication/schema/safety instructions; fixes shell JSON quoting and broken Google Docs references. | All 100 skills validate; 2 common-contract tests and 19 structural checks. Authenticated Google Workspace recipes were not executed. |
| handoff | 0.3.0 | Uses hook payload cwd; keeps read-only recall read-only; bounds previews; aligns Unicode keys; supports external storage and macOS freshness checks. | 9 path and 23 freshness checks plus hook regressions; upgraded installed copy verified. |
| marketplace-manager | 2.0.0 | Resolves an explicit source checkout from installed locations; scaffolds both hosts; preserves metadata; updates both catalogs; rolls back failed add/remove operations; confines workflow installation paths. | Root integration tests cover installed-style location, mutations, rollback, symlinks and catalogs; basic scaffold `make test` passes. |
| nano-banana-pro | 1.4.0 | Locks script dependencies, preserves caller cwd, handles image MIME/final response data correctly, protects output, repairs configuration/optimization paths, and removes compulsory delegation. | 36 offline tests; upgraded installed copy verified. Image generation API calls were not made. |
| notebooklm-enhanced | 0.2.0 | Pins the CLI to 0.8.2; adds an installation-relative wrapper, explicit notebook selection and bounded polling; documents history deletion by `ask --new`. | 2 launcher tests with actual CLI help; no authenticated notebook operations. |
| quick-notes | 1.1.0 | Adds bounded portable locking, validates malformed records, preserves log tails, checks edits under lock and protects exports. | 25 operation tests plus utility regression cases using temporary notes. |
| recall-mode-verifier | 1.1.0 | Grounds findings in the requested review scope and available evidence; distinguishes reproduced defects from inspected risks; honors authorized fixes. | Native skill validation and workflow review; no measured model evaluation. |
| safe-fetch | 1.1.4 | Disables environment proxies to preserve IP pinning; repairs IPv6 headers and URL policy; prevents a blank Brave environment value from erasing configured credentials; validates hook JSON. | 108 tests and native MCP initialization/tool listing; no authenticated search calls. |
| session-evals | 1.1.0 | Rejects malformed specifications; stages replacements; prevents evidence/candidate clobbering; explains what configured endpoints receive. | 31 tests with isolated fixtures; no live evaluation endpoint calls. |
| session-retro | 1.3.0 | Rejects missing requested inputs and non-object records; deduplicates aliases; protects report labels and links. | 19 tests using synthetic sessions. |
| ship-loop | 1.2.0 | Uses host-aware execution and review evidence; makes dispatch requirements concrete. | 6 packet contract checks and skill validation. |
| ship-task | 1.2.0 | Prevents CI lookup errors from becoming “no CI”; pins merges to reviewed SHA; recognizes queued/unconfirmed merges; validates timing and flags. | 6 failure-path tests and 19 temporary worktree checks. No live merge was performed. |
| skill-spec-lint | 1.1.0 | Uses actual isolated YAML parsing; rejects duplicate/type errors; fixes help, direct-file inputs and deduplication; makes body-size advice advisory. | 28 existing checks plus YAML regression cases. |
| systems-thinking | 0.4.0 | Incomplete workers now block synthesis and return failure; tmux records process exit separately from generated text; host adapters preserve permissions. | 237 offline contract/unit tests; 8 live model evaluations excluded. |
| windows-cli-hygiene | 1.1.0 | Detects heredoc and combined-errexit cases; safely handles filenames/JSON and input errors; provides an optional failure gate. | 20 shell checks plus Python regressions. Native Windows execution remains untested; this is a heuristic scanner. |

## Creator and shared maintenance

The installed `plugin-creator` was upgraded, with an identical durable copy at [`tools/plugin-creator`](../tools/plugin-creator/SKILL.md). Its 32 regression tests cover lossless updates, real source-path derivation, registration without recreating plugins, optional runtime metadata versus catalog policy, MCP/hook forms, malformed inputs, symlink confinement and atomic cachebuster updates. The skill itself passes the system skill validator. A future Codex refresh may replace the installed system copy; the repository copy preserves this work.

The root catalog generator now preserves independent marketplace order, descriptions, policies and extension metadata, refuses unsupported source conversions, and makes no-op checks without rewriting files. Both catalogs and registry aggregates are current. The release helper synchronizes linked version sources and uses rollback plus a temporary Git index; 23 Python and 11 existing shell tests cover release operations. Root tests total 45, including marketplace operations, frontmatter and hook-path parsing.

Validation now parses real YAML, checks native packages and resource links, and reports catalog drift without modifying the checkout. CI runs the combined check entrypoint and uses the verified current action majors. Workflow assets match the root workflows. The basic template honestly describes an unfinished workflow and validates its actual skill packaging instead of invoking nonexistent Python code/tests.

## Archived and private packages

`archive/k8s-sidecar-testing` 2.0.0 now requires explicit context, namespace and targets, bounds commands, reports failures accurately and confines cleanup to owned resources. Twenty fake-command tests passed; no cluster or VM was changed.

`archive/rust-network-module` 1.1.0 now renders compilable templates with real protocol behavior, concurrency, drain/shutdown and error handling. Ten compiled Rust tests and Clippy passed. Dependency retrieval is explicit; generated runtime behavior is tested locally.

The separate private marketplace contains `interview-feedback` 0.4.0 and `sekou-voice` 1.1.0. Improvements cover recoverable durable state, copy-only migration, immutable snapshots, input/budget validation, fact boundaries and output preservation. All 57 private tests passed. Existing private corpus/history was preserved. Its detailed `MODERNIZATION.md` and local commit `6bc3e0d` remain in that repository; private content is not copied here.

## Executed verification

From the public repository:

```bash
./scripts/check-all.sh
make -C templates/basic test
uv build plugins/fakoli-state/bin --out-dir /tmp/fakoli-state-distribution
uv run --with PyYAML python -m unittest discover -s tools/plugin-creator/tests -v
claude plugin validate .
git diff --check
```

The combined check completed with **ALL PASSED**. It runs native and legacy validation, hook/path checks, all explicitly selected offline package suites, hook guards, roster guards, frontmatter regressions and registry consistency. The final combined log is locally available at `/tmp/fakoli-final-check-all.log`; detailed build/MCP/private logs use `/tmp/fakoli-*`. Temporary logs are supporting local evidence, not shipped dependencies.

Claude's validator succeeds with three extension warnings for marketplace `displayName`, `repository` and `categories`; these are retained for repository tooling and ignored by Claude. Safe Fetch tests emit five upstream PyMuPDF deprecation warnings. Neither warning group caused a failed check.

“Offline” here excludes authenticated application/service calls; dependency installation may access package registries. No paid generation, production deployment, SSH command, cluster operation, public merge or live model evaluation was used as test evidence. Provider authentication, actual remote service behavior, hook delivery in every host, subjective skill quality and native Windows execution are therefore not claimed verified.

## Local installation and delivery

The existing installed Fakoli plugins were upgraded through the supported `codex plugin` CLI:

- Handoff: 0.2.0 → **0.3.0**, enabled.
- Nano Banana Pro: 1.3.4 → **1.4.0**, enabled.

Both installed bundles match the verified source files. The configured `fakoli-plugins` marketplace now points to this local checkout rather than `https://github.com/fakoli/fakoli-plugins.git`, so these unpublished improvements are usable locally. The source/configuration provenance was backed up under `~/.codex/backups/plugin-modernization-2026-09-05` with restricted permissions. Only the two previously installed plugins were reinstalled; remaining source plugins are available in the local marketplace. No host hook trust was changed. Other marketplaces were preserved.

The updated skill catalog was observed during this task. Fresh tasks load the current bundles; this does not establish that every hook/event integration has been exercised. The initial modernization handoff was saved on local branches. The user subsequently authorized PR creation and merging in both repositories; that delivery is recorded in Git history. No tagged release is part of this change.

## Research basis

The current conventions were checked against the [OpenAI plugin packaging guide](https://developers.openai.com/plugins/build/plugins), [OpenAI skill guide](https://learn.chatgpt.com/docs/build-skills), [Agent Skills specification](https://agentskills.io/specification), [Claude plugin reference](https://code.claude.com/docs/en/plugins-reference), and actual `codex-cli 0.153.4` help. The [native Codex MCP parser](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/plugin_config.rs) resolved the distinction between direct/camelCase JSON server maps and unsupported snake_case wrappers and argument expansion assumptions.

Package-specific research used primary project/provider sources, including the [Google Workspace CLI](https://github.com/googleworkspace/cli), [NotebookLM client](https://github.com/teng-lin/notebooklm-py), [HTTPX environment behavior](https://www.python-httpx.org/environment_variables/), [Gemini speech documentation](https://ai.google.dev/gemini-api/docs/speech-generation), [Excalidraw restoration API](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/utils/restore), and [Agent Plugins specification](https://agent-plugins.org/specification). Research and implementation were split across three agents, then integrated and checked together.
