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

This is a valid metadata shape with deliberately poor workflow guidance: the description does
not identify a useful trigger, the body specifies no concrete actions, and the output is undefined.
Numbered steps, third-person phrasing, and quoted trigger phrases are optional authoring choices.

Dispatch the available skill critic with the fixture path and request an evidence-based report.
For Claude Code, the installed critic role is `fakoli-plugin-critic:skill-critic`. In Codex, follow
[the runtime adapter](../references/codex-runtime.md) and use exposed tools or review sequentially.
Write the report to `.fakoli/runs/smoke/agent-skill-critic-smoke-status.md`.

**Pass criteria:** Report actionable SHOULD FIX findings for the vague trigger and missing concrete
actions/output, quoting the relevant fixture text. PASS with quality findings is acceptable; a
MUST FIX requires a specific consequence under the selected contract.

**Fail criteria:** Invented schema rules requiring numbered steps, quoted triggers, or a grammatical
person; findings that do not match the fixture; no useful workflow critique.

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

The stdio server supplies `args` as a string. When present, `args` must be an array of strings;
omitting it is valid. This is a Claude plugin fixture, where `${CLAUDE_PLUGIN_ROOT}` is supported.
For native Codex MCP configs, verify the separate runtime path rules; shell-style expansion in
argument strings is not implied by the hook environment.

Dispatch `fakoli-plugin-critic:mcp-critic` when that Claude role is exposed; otherwise use the
[runtime adapter](../references/codex-runtime.md). Review the manifest only; there is no companion
server implementation. Write `.fakoli/runs/smoke/agent-mcp-critic-smoke-status.md`.

**Pass criteria:** At least one MUST FIX for string-valued `args`, suggesting `["--stdio"]`, and
VERDICT: FAIL. Cite the selected host's current configuration contract.

**Fail criteria:** Claims that args is missing or universally required, invented secret leaks,
or fabricated execution results. Missing server source can be recorded as unverified, not as
proof of a server implementation defect.

---

## structure-critic

**Fixture:** `plugins/fakoli-crew/tests/fixtures/audit-targets/bad-plugin.json`

Select the **publisher release profile** for this recipe: this marketplace requires an explicit
release version and a meaningful description. The fixture omits version and uses `tiny.` as its
description. Version is optional in the general runtime plugin manifest; this release requirement
must not be presented as a universal loader rule.

Dispatch `fakoli-plugin-critic:structure-critic` when that Claude role is exposed; otherwise use the
[runtime adapter](../references/codex-runtime.md). State the publisher release profile in the prompt.
The fixture is standalone, with no marketplace, registry, README, or Python metadata to compare.
Write `.fakoli/runs/smoke/agent-structure-critic-smoke-status.md`.

**Pass criteria:** MUST FIX for the absent release version under this explicit publisher policy,
SHOULD FIX for the uninformative description, and VERDICT: FAIL for this release profile. A second
review under the runtime profile must not fail merely because version is absent.

**Fail criteria:** Claiming every host requires version, flagging supported fields that are present
as missing, or inventing cross-file version drift without companion files.

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
