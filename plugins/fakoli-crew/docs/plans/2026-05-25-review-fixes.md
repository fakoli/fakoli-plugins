# fakoli-crew Review Fixes — Execution Plan

**Goal:** Resolve 10 spec-compliance and duplication issues identified by `/plugin-dev:agent-development` and `/plugin-dev:skill-development` reviews of fakoli-crew.
**Spec:** Inline below (no separate spec file — issues delivered as user prompt and captured in "Source Issues" section).
**Language:** Markdown + Bash (plugin authoring repo — no TS/Py/Rust source).
**Crew:** fakoli-crew v2.0.1 (8 agents) — self-modifying plan.

---

## Source Issues

### From agent review (`/plugin-dev:agent-development`)
1. All 8 agents use `allowed-tools:` instead of the documented `tools:` field for agent frontmatter.
2. All 8 agents hardcode `model: sonnet` instead of the recommended `model: inherit`.
3. `sentinel` uses non-canonical color `orange`; `keeper` uses `purple` (spec lists blue/cyan/green/yellow/magenta/red).
4. None of the 8 agents include `<commentary>` blocks inside their `<example>` description sections.
5. The "Iron Rule" prose ("Never modify a file you have not read in full in this session") is duplicated verbatim across smith, keeper, critic, herald, welder, and guido.

### From skill review (`/plugin-dev:skill-development`)
6. `crew-ops` and `debugging` descriptions list scenarios but no literal quoted user trigger phrases.
7. Agent roster table is duplicated between `skills/crew-ops/SKILL.md` and `commands/crew.md`.
8. `crew-ops` "Skills" subsection mixes a slash command (`/crew`) with a real skill (`Debugging`) under one label.
9. `debugging` skill has zero `references/` or worked examples to ground its abstract 4-phase method.
10. `crew-ops/SKILL.md` opens with "Use this skill to orchestrate…" — second-person, not the imperative form the spec requires.

---

## Scout Notice

Scout phase is embedded as **Task 1** (rather than pre-dispatched) because the schema questions in issues 1–3 are about Claude Code's current agent frontmatter contract — and the answer materially shapes Task 7's acceptance criteria. Execution should not proceed past Wave 1 until scout's findings are in.

---

## Wave Overview

| Wave | Tasks | Parallelism | Purpose |
|------|-------|-------------|---------|
| 1 | T1, T2, T3, T5 | parallel | Research + create new shared references |
| 2 | T4, T6, T7, T8 | parallel | Apply edits that depend on Wave 1 outputs |
| — CRITIC GATE — | review all modified files | — | Severity-rated review before version bump |
| 3 | T9, T10 | sequential | Version bump + registry regeneration |
| 4 | T11 | single | Evidence-based sentinel scorecard |

---

### Task 1: Verify agent frontmatter schema against current Claude Code docs

**Intent:** Confirm the canonical field names and allowed values for agent frontmatter in current Claude Code releases so the agent edits in Task 7 use the right schema.
**Acceptance criteria:**
- A scout status file documents whether `tools:` or `allowed-tools:` (or both) are accepted in agent frontmatter — citing the official docs URL where this is stated.
- The file documents whether `model: inherit` is officially supported, and what fallback values are accepted.
- The file documents the canonical color palette accepted for the `color:` field, and whether `orange` and `purple` are accepted, rejected, or undocumented.
- Each finding cites a source URL or commit; no finding is asserted without evidence.
- The file ends with a one-line `Status: COMPLETE` or `Status: BLOCKED` per the crew status-file protocol.
**Scope:** `plugins/fakoli-crew/docs/plans/agent-scout-status.md`
**Agent:** scout
**Verify:** `test -f plugins/fakoli-crew/docs/plans/agent-scout-status.md && grep -qE "tools:|allowed-tools:" plugins/fakoli-crew/docs/plans/agent-scout-status.md && grep -qE "model:" plugins/fakoli-crew/docs/plans/agent-scout-status.md && grep -qE "color" plugins/fakoli-crew/docs/plans/agent-scout-status.md`
**Depends on:** (none)

---

### Task 2: Create shared Iron Rule reference

**Intent:** Establish one source of truth for the "never modify a file you have not read in full" constraint so agent prompts can link to it instead of duplicating the prose.
**Acceptance criteria:**
- A reference file exists at `skills/crew-ops/references/iron-rule.md`.
- The file states the rule, explains the production-incident framing that justifies it, and shows how an agent should announce compliance ("I read all N files before editing").
- The file is short enough to load in full (under 500 words).
- The file is written in imperative voice — no "you should" / "the agent must" framing.
- The file ends with a one-line "Agents bound by this rule:" list so cross-references are discoverable.
**Scope:** `plugins/fakoli-crew/skills/crew-ops/references/iron-rule.md`
**Agent:** guido
**Verify:** `test -f plugins/fakoli-crew/skills/crew-ops/references/iron-rule.md && [ "$(wc -w < plugins/fakoli-crew/skills/crew-ops/references/iron-rule.md)" -lt 500 ]`
**Depends on:** (none)

---

### Task 3: Create shared agent roster reference

**Intent:** Extract the duplicated agent roster table out of `crew-ops/SKILL.md` and `commands/crew.md` into a single reference file that both can link to.
**Acceptance criteria:**
- A reference file exists at `skills/crew-ops/references/agent-roster.md` listing all 8 agents with role, color, best-for, and a link to the agent file path.
- The file is the canonical roster — no other location in the plugin contains a full agent roster after Tasks 4 and 8 complete.
- The file uses imperative/objective prose — not "Use this agent when…" framing (that belongs in the agent files themselves).
- File length is between 200 and 800 words.
**Scope:** `plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md`
**Agent:** guido
**Verify:** `test -f plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md && [ "$(grep -c "^| " plugins/fakoli-crew/skills/crew-ops/references/agent-roster.md)" -ge 9 ]`
**Depends on:** (none)

---

### Task 4: Update crew-ops SKILL.md for spec compliance

**Intent:** Bring `crew-ops/SKILL.md` into spec compliance: add literal trigger phrases, fix the second-person opening, rename the confusing "Skills" subsection, and replace the duplicated agent roster with a pointer.
**Acceptance criteria:**
- The frontmatter `description:` includes a "trigger phrases" segment listing at least 5 literal quoted phrases a user might type (examples: `"assemble a crew"`, `"who owns this file"`, `"plan the waves"`, `"run the crew on X"`, `"coordinate agents to Y"`).
- The body's first non-heading line is in imperative form — does not start with "Use this skill" or any second-person framing.
- The inline 8-row agent roster is removed and replaced with a one-line pointer to `references/agent-roster.md`.
- The current "Skills" subsection is replaced with cleanly separated sections (e.g., "Companion Command: `/crew`" and "Related Skill: `debugging`") — a slash command and a skill are no longer grouped under one heading.
- Word count of the body remains under 700 words (currently 543; the changes should net shorter, not longer).
**Scope:** `plugins/fakoli-crew/skills/crew-ops/SKILL.md`
**Agent:** guido
**Verify:** `grep -qiE "trigger phrases" plugins/fakoli-crew/skills/crew-ops/SKILL.md && ! awk '/^---$/{c++; next} c==2 && /^[A-Z]/{print; exit}' plugins/fakoli-crew/skills/crew-ops/SKILL.md | grep -q "^Use this skill" && grep -q "agent-roster.md" plugins/fakoli-crew/skills/crew-ops/SKILL.md && [ "$(wc -w < plugins/fakoli-crew/skills/crew-ops/SKILL.md)" -lt 700 ]`
**Depends on:** Task 3

---

### Task 5: Add trigger phrases to debugging skill description

**Intent:** Strengthen the `debugging` skill's frontmatter description with literal quoted user phrases so the skill is matched on phrase patterns, not only on scenario similarity.
**Acceptance criteria:**
- The `description:` field includes at least 5 literal quoted phrases users would actually type when stuck on a bug (e.g., `"why is this failing"`, `"I've tried three fixes"`, `"systematic debugging"`, `"root cause"`, `"this test keeps failing"`).
- The existing scenario sentences ("when a test is failing inexplicably", etc.) are retained alongside the new phrases.
- The full description remains under 80 words.
- Only the frontmatter is changed in this task — the body of `SKILL.md` is untouched.
**Scope:** `plugins/fakoli-crew/skills/debugging/SKILL.md`
**Agent:** guido
**Verify:** `awk '/^---$/{c++; next} c==1' plugins/fakoli-crew/skills/debugging/SKILL.md | tr ',' '\n' | grep -c '"[a-zA-Z][^"]*"' | awk '{exit ($1<5)}'`
**Depends on:** (none)

---

### Task 6: Create debugging case-studies reference

**Intent:** Ground the abstract 4-phase debugging method in 3 worked examples so a reader can see what each phase produces in practice.
**Acceptance criteria:**
- A reference file exists at `skills/debugging/references/case-studies.md` with at least 3 case studies.
- Each case study walks all 4 phases — Investigate, Pattern Analysis, Hypothesis, Implementation — for a single bug.
- Each case study names the symptom, the wrong-fix temptation, and the actual root cause.
- Each case study is grounded in plausible technology (real libraries, real error messages) — no fictional APIs.
- The `debugging/SKILL.md` body adds one line pointing at this new reference under an "Additional Resources" section.
- File length is between 800 and 2,500 words.
**Scope:** `plugins/fakoli-crew/skills/debugging/references/case-studies.md`, `plugins/fakoli-crew/skills/debugging/SKILL.md`
**Agent:** guido
**Verify:** `test -f plugins/fakoli-crew/skills/debugging/references/case-studies.md && grep -q "case-studies.md" plugins/fakoli-crew/skills/debugging/SKILL.md && wc=$(wc -w < plugins/fakoli-crew/skills/debugging/references/case-studies.md) && [ "$wc" -ge 800 ] && [ "$wc" -le 2500 ]`
**Depends on:** Task 5

---

### Task 7: Update all 8 agent frontmatters and bodies

**Intent:** Bring every agent file in `agents/` into schema compliance using the field names scout verified, allow model inheritance, normalize colors, add commentary blocks to examples, and replace the duplicated Iron Rule prose with a pointer to the shared reference.
**Acceptance criteria:**
- All 8 agent files use the frontmatter field name confirmed by scout in Task 1 (likely `tools:`, but follow scout's evidence — if scout finds `allowed-tools:` is required for agents too, keep it and document in the status file).
- All 8 agents set `model:` to the value scout identifies as recommended — or document inline in the prompt body why a specific model is locked.
- `sentinel.md` and `keeper.md` use a color from the palette scout confirms is canonical (if `orange`/`purple` are confirmed accepted, leave them and update the review evidence; otherwise change to a canonical color).
- Every `<example>` block in every agent's `description:` has a `<commentary>` child explaining why that example should trigger the agent.
- The Iron Rule prose is removed from the bodies of all agents that contained it (smith, keeper, critic, herald, welder, guido) and replaced with one line of the form: "Iron Rule: see `skills/crew-ops/references/iron-rule.md`."
- All 8 files still parse as valid YAML frontmatter + non-empty markdown body.
**Scope:** `plugins/fakoli-crew/agents/critic.md`, `plugins/fakoli-crew/agents/guido.md`, `plugins/fakoli-crew/agents/herald.md`, `plugins/fakoli-crew/agents/keeper.md`, `plugins/fakoli-crew/agents/scout.md`, `plugins/fakoli-crew/agents/sentinel.md`, `plugins/fakoli-crew/agents/smith.md`, `plugins/fakoli-crew/agents/welder.md`
**Agent:** smith
**Verify:** `for f in plugins/fakoli-crew/agents/*.md; do grep -q "<commentary>" "$f" || { echo "missing commentary: $f"; exit 1; }; grep -q "iron-rule.md\|Iron Rule:" "$f" || true; done && [ "$(grep -l "^model: sonnet$" plugins/fakoli-crew/agents/*.md | wc -l)" -le 1 ]`
**Depends on:** Task 1, Task 2

---

### Task 8: De-duplicate agent roster from /crew command

**Intent:** Remove the agent roster duplication from the `/crew` slash command; have it point at the shared reference instead, while preserving its pre-built crew composition content (which is distinct, not duplicated).
**Acceptance criteria:**
- The 8-row agent roster table is removed from `commands/crew.md`.
- The command body links to `skills/crew-ops/references/agent-roster.md` as the source of the roster.
- The "Pre-Built Crews" section (Code Quality, Plugin Development, Research & Build, Full Overhaul) is preserved — it is distinct content, not a duplicate.
- The command frontmatter (description, argument-hint, allowed-tools) is unchanged.
**Scope:** `plugins/fakoli-crew/commands/crew.md`
**Agent:** smith
**Verify:** `! grep -qE "^\| guido \| blue \|" plugins/fakoli-crew/commands/crew.md && grep -q "agent-roster.md" plugins/fakoli-crew/commands/crew.md && grep -q "Pre-Built Crews" plugins/fakoli-crew/commands/crew.md`
**Depends on:** Task 3

---

> ### ── CRITIC GATE after Wave 2 ──
>
> Critic reviews all files modified in Tasks 2-8 before Wave 3 proceeds. Critic produces a MUST FIX / SHOULD FIX / CONSIDER / NIT report. If any MUST FIX issues exist, smith and guido fix them and re-run their tasks. Wave 3 does not start until critic returns PASS.

---

### Task 9: Bump plugin version to 2.1.0 and update changelog

**Intent:** Reflect that the 10 review fixes have been applied with a minor semver bump and a changelog entry that names every modified file and category of change.
**Acceptance criteria:**
- `plugin.json` `version` field is updated from `2.0.1` to `2.1.0`.
- `CHANGELOG.md` has a new top-of-file entry dated 2026-05-25 summarizing the fixes grouped by category: frontmatter compliance, color palette normalization, deduplication, trigger phrases, new references.
- The changelog entry names the 3 new reference files (`iron-rule.md`, `agent-roster.md`, `case-studies.md`) and lists the modified agent file count.
- No other version-bearing locations in the plugin are missed (search for `2.0.1` literal — every match is updated or accounted for).
**Scope:** `plugins/fakoli-crew/.claude-plugin/plugin.json`, `plugins/fakoli-crew/CHANGELOG.md`
**Agent:** smith
**Verify:** `grep -q '"version": "2.1.0"' plugins/fakoli-crew/.claude-plugin/plugin.json && grep -q "2.1.0" plugins/fakoli-crew/CHANGELOG.md && ! grep -rn "2.0.1" plugins/fakoli-crew/ --include="*.json"`
**Depends on:** Task 4, Task 5, Task 6, Task 7, Task 8

---

### Task 10: Regenerate marketplace registry

**Intent:** Sync the marketplace registry index with the new plugin version so consumers see the update via auto-discovery.
**Acceptance criteria:**
- `./scripts/generate-index.sh` runs to completion with exit code 0 from the repo root.
- `registry/index.json` shows the `fakoli-crew` entry at version `2.1.0`.
- The total plugin count in `registry/index.json` is unchanged (no plugins accidentally added or removed by the regeneration).
- No archived plugins appear in the regenerated index.
**Scope:** `registry/index.json` (regenerated, not hand-edited)
**Agent:** keeper
**Verify:** `./scripts/generate-index.sh && jq -r '.plugins[] | select(.name=="fakoli-crew") | .version' registry/index.json | grep -q "^2.1.0$"`
**Depends on:** Task 9

---

> ### ── CRITIC GATE after Wave 3 (optional) ──
>
> Critic spot-checks the version bump and registry regeneration for consistency. This gate is light — metadata changes — but is run for symmetry with the workflow.

---

### Task 11: Evidence-based sentinel validation

**Intent:** Produce a pass/fail scorecard proving each of the 10 original review issues is resolved, with command-output evidence for every PASS.
**Acceptance criteria:**
- A scorecard exists at `docs/plans/agent-sentinel-status.md` listing each of the 10 original issues as `[PASS]` or `[FAIL]`.
- Each `[PASS]` line includes the exact command run and the relevant output substring proving resolution.
- `./scripts/validate.sh plugins/fakoli-crew` exits with code 0 — output is captured verbatim in the scorecard.
- `./scripts/test-path-resolution.sh plugins/fakoli-crew` exits with code 0 — output is captured verbatim.
- All 8 agent files parse: YAML frontmatter valid, body non-empty.
- Both skill `SKILL.md` files parse: frontmatter valid, description includes the new trigger phrases.
- `registry/index.json` reflects v2.1.0 for `fakoli-crew`.
- The scorecard names a fix owner for any `[FAIL]` finding.
**Scope:** `plugins/fakoli-crew/docs/plans/agent-sentinel-status.md`
**Agent:** sentinel
**Verify:** `test -f plugins/fakoli-crew/docs/plans/agent-sentinel-status.md && [ "$(grep -cE "^\[(PASS|FAIL|N/A )\]" plugins/fakoli-crew/docs/plans/agent-sentinel-status.md)" -ge 10 ] && grep -q "validate.sh" plugins/fakoli-crew/docs/plans/agent-sentinel-status.md && grep -q "test-path-resolution.sh" plugins/fakoli-crew/docs/plans/agent-sentinel-status.md`
**Depends on:** Task 10

---

## Self-Review Notes

**Spec coverage:** All 10 source issues map to tasks — issues 1–4 → T7; issue 5 → T2 + T7; issue 6 → T4 + T5; issue 7 → T3 + T4 + T8; issue 8 → T4; issue 9 → T6; issue 10 → T4. T9 (version), T10 (registry), T11 (validation) are infrastructure-driven by the change set, not the original issues.

**File conflict check within waves:**
- Wave 1 (T1/T2/T3/T5): scout-status.md, iron-rule.md, agent-roster.md, debugging/SKILL.md — four distinct files. ✓
- Wave 2 (T4/T6/T7/T8): crew-ops/SKILL.md, debugging/SKILL.md (body) + case-studies.md, 8 agent files, commands/crew.md — no overlap. ✓ (T5 finished before T6 starts; T6 owns debugging/SKILL.md exclusively.)

**Code-free check:** Acceptance criteria describe outcomes, not implementations. Verify lines are shell commands (allowed per plan format).

**Risk:** Task 7 depends on scout (T1) finding what the spec actually says. If scout returns evidence that `allowed-tools:` is the correct field for agents (i.e., the agent-development skill is outdated), then issue 1 should not be "fixed" — instead T7's acceptance criteria pivot to documenting that the current usage is correct. The task is intentionally written so the criterion is "use the field scout verified," not "change to `tools:`."

---

## Hand Off

Plan saved to `plugins/fakoli-crew/docs/plans/2026-05-25-review-fixes.md`. Ready to hand off to `/flow:execute`.
