# fakoli-crew Critic Smoke-Test Recipes

Manual-verification recipes for each of the 5 fakoli-crew critic agents. Bash cannot dispatch Claude Code subagents (the `Agent` tool only exists inside a live Claude Code session), so smoke-testing the critics is a developer-driven procedure: open Claude Code in this repo, copy-paste a one-liner, then inspect the resulting status file against the pass/fail criteria below.

Run these recipes before merging any change to a critic's system prompt — the fixtures under `tests/fixtures/audit-targets/` are the regression baseline.

## How to use this file

1. Pick the critic you changed (or are validating).
2. Read its section below.
3. Copy the dispatch one-liner verbatim into Claude Code (this repo as cwd).
4. Wait for the agent to finish and write its status file.
5. Open the status file referenced in **Pass criteria** and check that the expected findings are present.
6. If a check fails, re-read the critic's system prompt against `plugins/fakoli-crew/agents/<critic>.md` — the prompt likely drifted.

Companion runner: `bash tests/test_critics.sh --list` prints a one-line summary per critic and points back here. `bash tests/test_critics.sh --recipes` prints this file to stdout.

---

## agent-critic

**Fixture:** `plugins/fakoli-crew/tests/fixtures/audit-targets/bad-agent.md`

**Antipatterns intentionally present:**
- Missing `name:` frontmatter key (silent dispatch failure — the agent loads but Claude never picks it).
- Uses `allowed-tools:` (the COMMAND frontmatter key) instead of `tools:` (the AGENT key). On an agent file `allowed-tools:` is silently ignored, and the agent loads with FULL unrestricted tool access — the author's intended restriction has no effect. This is the canonical silent-failure antipattern `agent-critic` exists to catch.

**Dispatch one-liner (run in Claude Code):**

```
Agent(
  subagent_type="fakoli-plugin-critic:agent-critic",
  prompt="Review the agent file at plugins/fakoli-crew/tests/fixtures/audit-targets/bad-agent.md. Report findings using the standard MUST FIX / SHOULD FIX / CONSIDER / NIT severity rubric. Write the structured report to .fakoli/runs/smoke/agent-agent-critic-smoke-status.md."
)
```

**Pass criteria** (read `.fakoli/runs/smoke/agent-agent-critic-smoke-status.md` after dispatch):
- At least 1 **MUST FIX** finding mentioning the missing `name:` field.
- At least 1 **MUST FIX** finding mentioning `allowed-tools:` as an agent-frontmatter antipattern, with the fix to rename to `tools:`.
- **VERDICT: FAIL** at the bottom of the report (any MUST FIX → FAIL by definition).
- May report additional CONSIDER or NIT findings (e.g., on the embedded example commentary) — that is fine and does not affect pass/fail.

**Fail criteria:**
- Zero MUST FIX findings → critic prompt is too lenient or the frontmatter rules section regressed; re-read `plugins/fakoli-crew/agents/agent-critic.md` checklist `Frontmatter Validity` and `Antipattern Detection`.
- VERDICT is PASS → mathematically wrong given the fixture; the prompt's verdict rule (FAIL on any MUST FIX) regressed.
- Findings reference fields the fixture does not have (e.g., flagging a `bash:` key that is not present) → hallucination; the critic is grading from memory rather than reading the file.

**Note:** This is a developer-driven smoke test, not an automated check. Run it before merging any change to `agent-critic.md`'s system prompt. The fixture is the regression baseline — if you change the fixture, also update this section.

---

## skill-critic

**Fixture:** `plugins/fakoli-crew/tests/fixtures/audit-targets/bad-skill/SKILL.md`

**Antipatterns intentionally present:**
- Vague description ("a skill that helps with things") — fails the `description must include specific quoted trigger phrases` rule. Claude reads the description to decide when to load a skill; this phrasing will never match concrete user input.
- No numbered decision flow / no enumerated steps — the skill is a wall of prose with no `Step 1 — ...`, `Step 2 — ...` headings, and no decision branches called out. Fails the `multi-step skills MUST present their flow as a numbered workflow or explicit decision table` rule.

**Dispatch one-liner (run in Claude Code):**

```
Agent(
  subagent_type="fakoli-plugin-critic:skill-critic",
  prompt="Review the skill at plugins/fakoli-crew/tests/fixtures/audit-targets/bad-skill/SKILL.md. Report findings using the standard MUST FIX / SHOULD FIX / CONSIDER / NIT severity rubric. Write the structured report to .fakoli/runs/smoke/agent-skill-critic-smoke-status.md."
)
```

**Pass criteria** (read `.fakoli/runs/smoke/agent-skill-critic-smoke-status.md` after dispatch):
- At least 1 finding at **MUST FIX** or **SHOULD FIX** severity flagging the vague description (must reference the description being a vague capability claim, not naming concrete trigger phrases).
- At least 1 **SHOULD FIX** finding flagging the absence of numbered steps / decision flow on a multi-step skill.
- **VERDICT: FAIL** if either finding is MUST FIX; otherwise PASS with two SHOULD FIX items called out is acceptable.
- The critic should explicitly cite the third-person + quoted-trigger-phrases rule from its standards.

**Fail criteria:**
- Zero findings on the description → critic is not applying the description-quality bar; re-read `plugins/fakoli-crew/agents/skill-critic.md` `Frontmatter` checklist.
- Zero findings on the missing decision flow → critic skipped the `Decision Flow` checklist; the prose body is plainly multi-step.
- Critic invents broken-reference findings (e.g., `references/foo.md does not exist`) when the fixture references no such file → hallucination; the critic is not actually reading the SKILL.md.

**Note:** The fixture intentionally keeps the frontmatter `name: bad-skill` matching the directory name `bad-skill/` so the only frontmatter finding is on the description quality — that isolation is on purpose. If skill-critic also flags a path or naming issue, double-check the fixture has not drifted.

---

## hook-critic

**Fixture:** `plugins/fakoli-crew/tests/fixtures/audit-targets/bad-hook.sh` (with `bad-hooks.json` in the same directory as the contract-detection source)

**Antipatterns intentionally present:**
- `set -e` declared on a script governed by a **non-blocking contract** (the leading comment block and the companion `bad-hooks.json` `_contract` field both document `non-blocking — hooks never block tool calls, always exit 0, warning-only`). Under this contract, `set -e` is a MUST FIX because a failing `grep` (line 53) will cause the script to exit non-zero on that line, which Claude Code interprets as a `PreToolUse` BLOCK — the unconditional `exit 0` at the bottom never runs.
- Bare relative path `./hooks/state.txt` (line 53) instead of `${CLAUDE_PLUGIN_ROOT}/hooks/state.txt`. The script's cwd is the user's project, not the plugin directory, so this resolves to the wrong place and fails for portability reasons.

**Dispatch one-liner (run in Claude Code):**

```
Agent(
  subagent_type="fakoli-plugin-critic:hook-critic",
  prompt="Review the hook layer in plugins/fakoli-crew/tests/fixtures/audit-targets/. Read bad-hooks.json (the manifest) and bad-hook.sh (the dispatched script). Perform the standard contract-detection rule (Steps 1-3 in your system prompt) before flagging set -e. Report findings using the standard MUST FIX / SHOULD FIX / CONSIDER / NIT severity rubric. Write the structured report to .fakoli/runs/smoke/agent-hook-critic-smoke-status.md."
)
```

**Pass criteria** (read `.fakoli/runs/smoke/agent-hook-critic-smoke-status.md` after dispatch):
- The report's header explicitly names the **Detected contract: non-blocking** (with a citation to either the `bad-hook.sh` leading comment block or the `bad-hooks.json` `_contract` field — the critic MUST state which detection step produced the conclusion).
- At least 1 **MUST FIX** finding flagging `set -e` as a contract violation, naming the unconditional `exit 0` at the bottom that will never run.
- At least 1 **SHOULD FIX** (or higher) finding flagging the missing `${CLAUDE_PLUGIN_ROOT}` on the `./hooks/state.txt` path.
- **VERDICT: FAIL**.

**Fail criteria:**
- Detected contract is reported as `standard` or `ambiguous` → contract detection regressed; the critic did not read the leading comment of `bad-hook.sh` or the `_contract` field in `bad-hooks.json`. The non-blocking signals are explicit and lower-case-substring matchable; missing them is a real bug.
- Zero MUST FIX on `set -e` → critic flagged the contract correctly but did not enforce the rule that matches the contract; re-read the `Enforce the rule that matches the detected contract` section of `hook-critic.md`.
- `set -e` is flagged when the critic ALSO detected the contract as standard → the rule mapping in the critic's prompt is wired wrong.

**Note:** This is the most subtle critic to verify because the verdict depends on a two-step inference (detect contract → apply contract-specific rule). If the smoke test fails here, the failure mode is usually in Step 2 of contract detection (the grep for signal phrases) rather than the rule application — check the README/comment scan first.

---

## mcp-critic

**Fixture:** `plugins/fakoli-crew/tests/fixtures/audit-targets/bad-mcp.json`

**Antipatterns intentionally present:**
- stdio server entry missing the required `args` field. Per the mcp-critic Manifest Schema checklist: "stdio servers have `command` (string) and `args` (array of strings); missing or wrong-typed fails install." The server will silently fail to start because Claude Code's MCP loader requires `args` (even an empty `[]`) for stdio transports.

Note: the fixture intentionally uses `${CLAUDE_PLUGIN_ROOT}` for the `command` path so portability is satisfied — the MUST FIX is scoped strictly to the missing `args` field, not to portability noise.

**Dispatch one-liner (run in Claude Code):**

```
Agent(
  subagent_type="fakoli-plugin-critic:mcp-critic",
  prompt="Review the MCP manifest at plugins/fakoli-crew/tests/fixtures/audit-targets/bad-mcp.json. Treat this as a standalone .mcp.json (there is no companion server implementation source — the fixture is manifest-only). Report findings using the standard MUST FIX / SHOULD FIX / CONSIDER / NIT severity rubric. Write the structured report to .fakoli/runs/smoke/agent-mcp-critic-smoke-status.md."
)
```

**Pass criteria** (read `.fakoli/runs/smoke/agent-mcp-critic-smoke-status.md` after dispatch):
- At least 1 **MUST FIX** finding flagging the missing `args` field on the `bad-server` stdio entry, with the suggested fix to add `"args": []` (or a populated array if the wrapper takes arguments).
- The finding cites the Manifest Schema rule from the critic's checklist.
- **VERDICT: FAIL**.
- The critic does NOT flag `${CLAUDE_PLUGIN_ROOT}` usage as a problem (the fixture uses it correctly).
- The critic may also note absence of a server implementation file — that is acceptable, but flag it as a CONSIDER (no source to audit) rather than a MUST FIX (the fixture is manifest-only by design).

**Fail criteria:**
- Zero MUST FIX → the schema check regressed; re-read `plugins/fakoli-crew/agents/mcp-critic.md` `Manifest Schema` checklist.
- Critic flags hardcoded paths or secret leaks → hallucination; the fixture has neither (the `command` uses `${CLAUDE_PLUGIN_ROOT}` and there is no `env` block).
- VERDICT is PASS → mathematically wrong given the fixture; the verdict rule regressed.

**Note:** This fixture is intentionally narrow — one antipattern, one expected MUST FIX. If `mcp-critic` finds additional MUST FIX items, verify the fixture file has not been edited.

---

## structure-critic

**Fixture:** `plugins/fakoli-crew/tests/fixtures/audit-targets/bad-plugin.json`

**Antipatterns intentionally present:**
- `version` field is MISSING. Per the Manifest Required Fields checklist: "`version` present, valid semver (`X.Y.Z` or `X.Y.Z-prerelease`)." Without `version`, structure-critic cannot run its version-sync-across-sources check and the plugin cannot be released. Expected: **MUST FIX**.
- `description` is 6 characters long (`"tiny."`). The spec requires `non-empty, accurately describes the plugin` — a placeholder fails the bar. Expected: **SHOULD FIX** (or MUST FIX depending on how strictly the critic enforces the meaningful-description bar).

The fixture keeps `name`, `author`, `repository`, `license`, and `keywords` valid so the critic's findings concentrate on the two intentional bugs.

**Dispatch one-liner (run in Claude Code):**

```
Agent(
  subagent_type="fakoli-plugin-critic:structure-critic",
  prompt="Review the plugin manifest at plugins/fakoli-crew/tests/fixtures/audit-targets/bad-plugin.json. Treat it as a standalone plugin.json (no surrounding marketplace.json, registry/index.json, CHANGELOG, README, or pyproject.toml — the fixture is manifest-only by design). Apply the Manifest Required Fields checklist. Report findings using the standard MUST FIX / SHOULD FIX / CONSIDER / NIT severity rubric. Write the structured report to .fakoli/runs/smoke/agent-structure-critic-smoke-status.md."
)
```

**Pass criteria** (read `.fakoli/runs/smoke/agent-structure-critic-smoke-status.md` after dispatch):
- At least 1 **MUST FIX** finding flagging the missing `version` field, with the suggested fix to add a semver `"version": "0.1.0"` (or whatever the author intends).
- At least 1 finding (MUST FIX or SHOULD FIX) flagging the placeholder 6-char `description: "tiny."` as not accurately describing the plugin.
- **VERDICT: FAIL** (any MUST FIX → FAIL).
- The critic may note the absence of marketplace.json/registry/CHANGELOG and either skip those sections or call them out as CONSIDER (no companion files to cross-check) — both behaviours are acceptable given the manifest-only fixture.

**Fail criteria:**
- Zero MUST FIX → the `version` required-field check regressed; re-read `plugins/fakoli-crew/agents/structure-critic.md` `Manifest (plugin.json) Required Fields` checklist.
- Critic flags `name`, `author`, `repository`, `license`, or `keywords` as missing → hallucination; the fixture has all five.
- Critic attempts to verify cross-file version sync against marketplace.json/registry/index.json and reports a fabricated mismatch (no such files exist for this fixture) → the critic is grading from a hallucinated repo layout rather than what is on disk.

**Note:** Because this fixture is manifest-only, the version-sync-across-sources check has nothing to compare against — that is expected. The smoke test is specifically validating the single-file required-field discipline; the cross-file sync logic is exercised in real plugin audits (e.g., the live `fakoli-state` and `fakoli-crew` plugins), not in this fixture.

---

## Composite smoke test

To exercise all five critics in one Claude Code session, dispatch them in parallel waves rather than serially — every critic above is read-only and the fixtures are independent. Example:

```
Run all 5 fakoli-crew critic smoke tests against the fixtures under
plugins/fakoli-crew/tests/fixtures/audit-targets/ in parallel.
Dispatch the 5 Agent calls in one message and aggregate the
verdicts into docs/plans/critic-smoke-summary.md.
```

The summary should show **FAIL** verdicts from all 5 critics — the fixtures are deliberately broken. A PASS verdict from any critic is a regression and must be investigated before merging that critic's prompt.

---

## Maintenance contract

- When you change a fixture, update the matching section above so the antipatterns list, dispatch one-liner, and pass/fail criteria still match what the fixture actually contains.
- When you change a critic's system prompt, run the matching smoke test before merging — the fixture is the regression baseline.
- When you add a new critic, add a new section here following the same template (Fixture / Antipatterns / Dispatch one-liner / Pass criteria / Fail criteria / Note) and add a fixture to `tests/fixtures/audit-targets/`.
- Status file paths in the dispatch one-liners use a `-smoke-status.md` suffix to avoid clobbering production status files from real critic dispatches (which use `-status.md`).
