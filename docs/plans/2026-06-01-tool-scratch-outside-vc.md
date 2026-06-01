# Tool Scratch Outside Version Control — Execution Plan

**Goal:** Re-point the fakoli-flow/crew wave engine to write status files to a gitignored per-run scratch root (`.fakoli/runs/<run-id>/`), and record the scratch-vs-durable rule as fakoli-style principle P10 (proven).
**Spec:** docs/specs/2026-06-01-tool-scratch-outside-vc.md
**Language:** Markdown + Bash + JSON (skills, docs, a shell invariant check, ledger data); fakoli-style scripts are Python via uv.
**Crew:** fakoli-crew v2.3.0 (8 agents)

**Scout findings:** docs/plans/agent-scout-status.md (COMPLETE). Live-instruction inventory confirmed; P10 proven-check feasible as specced; only 4 of 8 crew agents hardcode a status path (spec said 8 — corrected below); fakoli-state out of scope; no test asserts the old path.

**Pre-execution:** create a feature branch off `main` before any writes.

---

### Task 1: Add the scratch gitignore guard and the proven invariant check

**Intent:** Make committing run scratch impossible and provide the executable proof that backs principle P10.
**Acceptance criteria:**
- `.gitignore` ignores `.fakoli/`; `git check-ignore .fakoli/runs/x/agent-y-status.md` resolves (exit 0).
- `tests/test-scratch-not-tracked.sh` exists at the repo-root `tests/` directory, is executable, and exits 0 on the current repo, failing with a clear message otherwise.
- The check asserts both: a representative path under `.fakoli/` is git-ignored, and `git ls-files .fakoli/` returns nothing (no scratch tracked).
**Scope:** .gitignore, tests/test-scratch-not-tracked.sh
**Agent:** keeper
**Verify:** `bash tests/test-scratch-not-tracked.sh && git check-ignore .fakoli/runs/x/agent-y-status.md`
**Depends on:** (none)

---

### Task 2: Re-point the fakoli-flow wave engine to the orchestrator-injected scratch path

**Intent:** Make the orchestrator the single authority for the status-file path, writing run scratch under `.fakoli/runs/<run-id>/` instead of `docs/plans/`.
**Acceptance criteria:**
- `references/status-protocol.md` "File Location" section describes the orchestrator-injected path with default root `.fakoli/runs/<run-id>/`, no longer a fixed `docs/plans/` location.
- `skills/execute/SKILL.md` computes a single `<run-id>` at the start of a run (derived from the plan filename plus a short timestamp), injects the absolute status-file path into every agent dispatch prompt, and reads status / collects modified files from that run directory.
- `skills/plan/SKILL.md` scout dispatch, `references/example-dispatch-prompt.md`, and `references/wave-engine-ref.md` reference the orchestrator-provided path, not a hardcoded `docs/plans/agent-*` path.
- `docs/getting-started.md` and `docs/wave-engine.md` describe the new location accurately.
- Plan-file references (`docs/plans/<date>-<feature>.md`) are left unchanged; only `agent-*-status.md` references move.
- No live status-write instruction to `docs/plans/agent-*` remains in fakoli-flow skills or references.
**Scope:** plugins/fakoli-flow/references/status-protocol.md, plugins/fakoli-flow/skills/execute/SKILL.md, plugins/fakoli-flow/skills/plan/SKILL.md, plugins/fakoli-flow/references/example-dispatch-prompt.md, plugins/fakoli-flow/references/wave-engine-ref.md, plugins/fakoli-flow/docs/getting-started.md, plugins/fakoli-flow/docs/wave-engine.md
**Agent:** welder
**Verify:** `! grep -rnE 'docs/plans/agent-[a-z]+-status' plugins/fakoli-flow/skills plugins/fakoli-flow/references`
**Depends on:** (none)

---

### Task 3: Make fakoli-crew agents write to the orchestrator-provided path

**Intent:** Remove hardcoded status paths from crew so agents write wherever the orchestrator tells them.
**Acceptance criteria:**
- The 4 agent definitions that currently hardcode a status path (welder, herald, keeper, sentinel) instruct writing to the orchestrator-provided path instead of `docs/plans/agent-*`. The other 4 agents (critic, guido, scout, smith) need no change (they receive the path via dispatch only) and are left as-is.
- `skills/crew-ops/SKILL.md` and `references/communication.md` describe the status protocol as "write to the path the orchestrator provides; default scratch root `.fakoli/runs/<run-id>/`", not a fixed `docs/plans/` location.
- `references/file-ownership.md` and `tests/RECIPES.md` references are updated for accuracy.
- No live status-write instruction to `docs/plans/agent-*` remains in fakoli-crew skills or agent definitions.
**Scope:** plugins/fakoli-crew/agents/welder.md, plugins/fakoli-crew/agents/herald.md, plugins/fakoli-crew/agents/keeper.md, plugins/fakoli-crew/agents/sentinel.md, plugins/fakoli-crew/skills/crew-ops/SKILL.md, plugins/fakoli-crew/skills/crew-ops/references/communication.md, plugins/fakoli-crew/skills/crew-ops/references/file-ownership.md, plugins/fakoli-crew/tests/RECIPES.md
**Agent:** welder
**Verify:** `! grep -rnE 'docs/plans/agent-[a-z]+-status' plugins/fakoli-crew/skills plugins/fakoli-crew/agents`
**Depends on:** (none)

---

### Task 4: Record the rule as fakoli-style principle P10 (proven)

**Intent:** Add P10 to the governed ledger so the scratch-vs-durable rule is a tracked, proven principle.
**Acceptance criteria:**
- `data/principles.json` contains a P10 entry exactly as in the Prescriptive Detail below, and validates against the schema.
- `docs/fakoli-style.md` is regenerated and in sync (the generator's staleness check passes).
- `validate.py` exits 0 with P10 present as `proven` (its proof path and embodiment refs resolve on disk).
**Scope:** plugins/fakoli-style/data/principles.json, plugins/fakoli-style/docs/fakoli-style.md
**Agent:** guido
**Verify:** `cd plugins/fakoli-style && uv run --script scripts/generate.py && uv run --script scripts/validate.py`
**Depends on:** Task 1

**Prescriptive detail (P10 entry — exact values):**
- `id`: `P10`
- `name`: `Tool scratch lives outside version control`
- `principle`: `Run-local process artifacts are gitignored; only intent (specs and plans) is committed.`
- `why`: `Committing scratch clutters history and PR diffs with mechanics that have no value after the run.`
- `status`: `proven`
- `proof`: `tests/test-scratch-not-tracked.sh`
- `embodied_in`: `[{"plugin": "repo", "ref": ".gitignore", "mechanism": "gitignores .fakoli/ so run scratch cannot be committed"}, {"plugin": "fakoli-flow", "ref": "plugins/fakoli-flow/references/status-protocol.md", "mechanism": "status files write to .fakoli/runs/<run-id>/, not docs/plans/"}]`
- `credibility_risk`: `med`

---

### Task 5: Bump versions, changelogs, and regenerate the registry

**Intent:** Record the changes per repo policy and keep the three sync sources consistent.
**Acceptance criteria:**
- `fakoli-flow` (1.0.1 to 1.1.0), `fakoli-crew` (2.3.0 to 2.4.0), and `fakoli-style` (1.0.0 to 1.1.0) each have a bumped manifest version and a matching CHANGELOG entry dated 2026-06-01.
- Any live status-path reference in `plugins/fakoli-crew/README.md` is corrected for accuracy.
- `./scripts/generate-index.sh` is run; `registry/index.json`, `categories.json`, and `tags.json` reflect the new versions.
- README "Available Plugins" table, `marketplace.json`, and `registry/index.json` agree on the active plugin set.
**Scope:** plugins/fakoli-flow/.claude-plugin/plugin.json, plugins/fakoli-flow/CHANGELOG.md, plugins/fakoli-crew/.claude-plugin/plugin.json, plugins/fakoli-crew/CHANGELOG.md, plugins/fakoli-crew/README.md, plugins/fakoli-style/.claude-plugin/plugin.json, plugins/fakoli-style/CHANGELOG.md, .claude-plugin/marketplace.json, registry/index.json, registry/categories.json, registry/tags.json
**Agent:** keeper
**Verify:** `./scripts/generate-index.sh && jq -e '.plugins[]|select(.name=="fakoli-style")|select(.version=="1.1.0")' registry/index.json`
**Depends on:** Task 2, Task 3, Task 4

---

### Task 6: Full validation scorecard

**Intent:** Produce an evidence-based pass/fail scorecard proving the rule is enforced and nothing regressed.
**Acceptance criteria:**
- `bash tests/test-scratch-not-tracked.sh` exits 0 (the P10 proof holds).
- `grep` confirms no live `docs/plans/agent-*-status` write instruction remains in fakoli-flow or fakoli-crew skills/references/agents (historical `docs/plans|specs/2026-04-04-*` and already-committed status files excepted).
- `plugins/fakoli-style` `validate.py` exits 0 with P10 proven and the doc in sync.
- `./scripts/validate.sh` passes for fakoli-flow, fakoli-crew, and fakoli-style with no ERRORs.
- The three version bumps are present and the three sync sources agree.
- Plan and spec files under `docs/plans/` and `docs/specs/` remain committed and unchanged in convention.
- Scorecard reports each check PASS/FAIL with exact command output; no fixes made by this task.
**Scope:** (read-only across the three plugins, registry, and tests/)
**Agent:** sentinel
**Verify:** `bash tests/test-scratch-not-tracked.sh && ./scripts/validate.sh plugins/fakoli-flow && ./scripts/validate.sh plugins/fakoli-crew && ./scripts/validate.sh plugins/fakoli-style`
**Depends on:** Task 5
