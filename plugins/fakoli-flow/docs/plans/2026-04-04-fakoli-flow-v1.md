# fakoli-flow v1.0.0 — Execution Plan

> **For agentic workers:** Use `fakoli-crew:crew-ops` to execute this plan wave-by-wave. Tasks describe WHAT each file must contain and its acceptance criteria — agents write the actual content. Do NOT copy spec prose verbatim. Read each task's intent, then write the file from first principles.

**Goal:** Ship fakoli-flow v1.0.0 — a Claude Code plugin that orchestrates the brainstorm → plan → execute → verify → finish workflow through intent-driven plans and wave-based crew dispatch.

**Spec:** `docs/specs/2026-04-04-fakoli-flow-design.md`

**Plugin type:** Claude Code plugin — no compiled code. All deliverables are markdown (SKILL.md, commands), shell scripts (hooks, visual companion), HTML/JS (visual companion template), and JSON (plugin.json, hooks.json).

**Crew:** fakoli-crew agents (smith, herald, keeper, guido, welder, sentinel, critic)

---

## Wave 1 (parallel) — Foundation

These four tasks are independent. Dispatch all four agents simultaneously.

---

### Task 1: Plugin manifest

**File:** `.claude-plugin/plugin.json`

**Intent:** Declare this as a valid Claude Code plugin so the harness can load it, discover its skills and commands, and display it in `claude plugin list`.

**Acceptance criteria:**
- `name` is `"fakoli-flow"`
- `version` is `"1.0.0"`
- `description` accurately describes intent-driven workflow orchestration in one sentence (under 150 characters)
- `author` block includes name and URL matching the fakoli-plugins monorepo author
- `repository` points to the correct GitHub URL
- `license` is `"MIT"`
- `keywords` array includes at minimum: `workflow`, `orchestration`, `intent-driven`, `wave-engine`, `brainstorming`, `planning`
- Valid JSON — no trailing commas, no comments

**Agent:** smith

**Verify:** `cat .claude-plugin/plugin.json | python3 -m json.tool` exits 0 with no parse errors

**Depends on:** (none)

---

### Task 2: SessionStart hook

**Files:**
- `hooks/hooks.json`
- `hooks/detect-context.sh`

**Intent:** At session start, detect the project language and whether fakoli-crew is installed, then emit a single-line summary (~50 tokens) that the harness injects into the session context. This gives all skills immediate awareness of language + crew availability without them having to do their own detection.

**Acceptance criteria for `hooks/hooks.json`:**
- Declares a single `SessionStart` hook
- `command` points to `detect-context.sh`
- `timeout` is `5` (seconds in the shipped Claude Code hook schema; the design spec originally said 5000ms)
- Valid JSON

**Acceptance criteria for `hooks/detect-context.sh`:**
- Executable shell script (`chmod +x`)
- Detects language by file presence: `Cargo.toml` → Rust, `pyproject.toml` → Python, `package.json` or `tsconfig.json` → TypeScript; defaults to `unknown`
- Checks for fakoli-crew via `claude plugin list`; if found, extracts version from the plugin manifest path
- Emits exactly one line in the format: `[fakoli-flow] Language: <lang> | Crew: fakoli-crew <version or "not installed"> | Skills: brainstorm, plan, execute, verify, finish, quick`
- Handles `claude` command not found gracefully (no crash, outputs "not installed")
- Runs in under 5 seconds on a typical project

**Agent:** keeper

**Verify:** `bash hooks/detect-context.sh` outputs one line matching the format above; `cat hooks/hooks.json | python3 -m json.tool` exits 0

**Depends on:** (none)

---

### Task 3: `/flow` command

**File:** `commands/flow.md`

**Intent:** Give users a single entry point to orient themselves. Running `/flow` shows all available skills with their commands, the workflow diagram, and the current project's detected context (language + crew status).

**Acceptance criteria:**
- Valid YAML frontmatter with `description` and `allowed-tools` (Bash, Glob at minimum)
- Skills table lists all 6 skills: brainstorm, plan, execute, verify, finish, quick — with their `/flow:<skill>` command and a one-line purpose
- Workflow diagram shows the pipeline: `brainstorm → plan → execute → verify → finish` and where `quick` fits (fast path)
- Command body calls `detect-context.sh` to show live language + crew status
- Reads naturally — a new user should understand what to do next

**Agent:** smith

**Verify:** The file parses as valid markdown with YAML frontmatter; the skills table contains all 6 rows; running `/flow` in a Claude Code session shows the table and invokes `detect-context.sh`

**Depends on:** (none)

---

### Task 4: README.md

**File:** `README.md`

**Intent:** The top-level README is the first thing users see when browsing the plugin. It must communicate what fakoli-flow does, why it's different from SuperPowers, how to install it, and how to get started — in under 400 words of prose.

**Acceptance criteria:**
- Opens with a one-sentence description of fakoli-flow's purpose
- Includes a "What it is" section: the brainstorm → plan → execute → verify → finish pipeline, intent-driven plans, wave-based crew dispatch
- Includes a "What it replaces / why it's different" section covering the key SuperPowers pain points: token overhead, stale prescriptive plans, lost server state, no quick path
- Includes an installation section: `claude plugin install fakoli-flow`
- Includes a quick start with the most common entry points: `/flow`, `/flow:brainstorm`, `/flow:quick`
- Links to `docs/specs/2026-04-04-fakoli-flow-design.md` for full design details
- No placeholder text, no TODO items
- Accurate — every claim matches what the plugin actually does

**Agent:** herald

**Verify:** File exists, under 500 lines, no instances of "TODO" or "TBD", all linked files exist

**Depends on:** (none)

---

## Wave 2 (parallel) — Core Skills

These three tasks are independent of each other. Dispatch all three agents simultaneously. All depend on Wave 1 completing first (context about language detection, crew protocol, and plugin structure).

---

### Task 5: Brainstorm skill

**File:** `skills/brainstorm/SKILL.md`

**Intent:** The brainstorm skill guides users from a rough idea to an approved spec. It must do this one question at a time, detect when visual questions arise and offer the visual companion, and produce a spec file that the plan skill can consume. It replaces SuperPowers brainstorming but is crew-aware and significantly lower overhead.

**Acceptance criteria:**
- YAML frontmatter with `name: brainstorm` and a `description` that triggers appropriately (design, spec, brainstorm, "plan this feature")
- Step-by-step process documented: explore context → assess scope → ask clarifying questions → propose approaches → present design → write spec → self-review → hand off to `/flow:plan`
- Hard gate documented: no implementation action until design is approved
- Scope assessment documented: if the request spans multiple independent subsystems, flag it and suggest decomposition before refining details
- One-question-at-a-time rule stated explicitly; multiple-choice preferred
- Visual companion section explains: offer on visual questions only (not every session), auto-detect when visual would help, offer only once per session, subsequent visual questions reuse an already-running server, terminal questions stay in terminal
- Visual companion server management documented: PID tracking via `scripts/check-server.sh`, auto-restart after inactivity, terminal indicator format `[visual: active on http://localhost:52121]`
- CLAUDE.md awareness: read and honor output paths and conventions
- Spec self-review checklist: placeholder scan, consistency check, scope check, ambiguity check
- Output path: `docs/specs/<date>-<topic>.md` (overridden by CLAUDE.md if present)
- Handoff: invokes `/flow:plan` after user approves the spec

**Differences from SuperPowers brainstorming that must be present:**
- Only offers visual companion on visual questions, not every session
- Reads CLAUDE.md and honors its conventions
- No 22k token startup — metadata only
- PID-tracked server with auto-restart

**Agent:** guido

**Verify:** SKILL.md has YAML frontmatter, contains "visual companion" section, contains "one question at a time" rule, contains hard gate language, references `scripts/check-server.sh` for liveness check, does not contain TODO/TBD placeholders

**Depends on:** Task 2 (hook establishes session context pattern), Task 3 (command references brainstorm skill)

---

### Task 6: Plan skill

**File:** `skills/plan/SKILL.md`

**Intent:** The plan skill reads an approved spec and produces an intent-driven task list — acceptance criteria and scope, not implementation code. It dispatches a scout agent to verify assumptions before writing, then self-reviews the plan against the spec for coverage and correctness.

**Acceptance criteria:**
- YAML frontmatter with `name: plan` and a description that triggers on "break this into tasks", "create a plan", or brainstorm handoff
- Input/output documented: input is an approved spec file, output is `docs/plans/<date>-<feature>.md`
- Plan format documented with all required fields per task: Intent, Acceptance criteria, Scope, Agent, Verify, Depends on
- "What goes in a task" vs "what does NOT go in a task" distinction stated clearly — no implementation code, no line numbers, no step-by-step instructions
- Exceptions documented: schema migrations, security-critical code, API contracts, configuration values where prescriptive content is appropriate
- Scout phase documented: before writing the plan, dispatch a scout to verify that referenced libraries exist, APIs work as described, and codebase patterns to follow
- Self-review checklist documented: spec coverage, criteria clarity (each criterion independently verifiable), dependency correctness (no circular deps, valid wave grouping), agent assignment appropriateness
- Language and crew detection in plan header (from SessionStart context)
- Handoff: invokes `/flow:execute` after plan is complete

**Agent:** guido

**Verify:** SKILL.md has YAML frontmatter, plan format section includes all six task fields (Intent, Acceptance criteria, Scope, Agent, Verify, Depends on), scout phase is documented, self-review checklist has four items, no TODO/TBD placeholders

**Depends on:** Task 2 (hook provides language + crew context for plan header), Task 5 (plan is the handoff target from brainstorm)

---

### Task 7: Execute skill

**File:** `skills/execute/SKILL.md`

**Intent:** The execute skill reads an intent-driven plan and runs it: groups tasks into waves by their declared dependencies, dispatches crew agents in parallel within each wave, enforces language verification between waves, enforces critic gates after every code-writing wave, and handles BLOCKED/NEEDS_REVIEW escalations. This is the wave engine described in `docs/wave-engine.md`.

**Acceptance criteria:**
- YAML frontmatter with `name: execute` and a description that triggers on "build this", "run the plan", "execute", or plan handoff
- Wave engine process documented in order: load plan → detect agents → group into waves → per-wave dispatch loop → final sentinel
- Per-wave loop steps all present: parallel agent dispatch, wait for status files, handle escalations (BLOCKED/NEEDS_REVIEW), language verification, critic gate
- Agent dispatch format documented: `Agent(subagent_type="fakoli-crew:<agent>", ...)` with the five fields each agent receives (intent, acceptance criteria, scope, upstream context, verify command)
- Graceful degradation documented: if fakoli-crew not installed, fall back to generic subagents with a logged warning
- Critic gate documented as non-negotiable: fires after every wave that writes code; PASS → proceed, SHOULD FIX → log and proceed, MUST FIX → fix cycle (welder fixes → critic re-reviews → max 3 cycles → escalate)
- Status file protocol documented: agents write to `docs/plans/agent-<name>-status.md`; execute skill reads these to detect completion, blockers, escalations, modified files, and upstream decisions
- Default wave pattern documented for plans without explicit dependencies: Wave 1 Research (scout), Wave 2 Build (guido/smith/herald), Wave 3 Integrate (welder), Wave 4 Review (critic/sentinel), Wave 5 Fix cycle
- Parallel dispatch syntax shown for multiple agents in same wave
- Summary report format at end: files modified, tests passing, critic verdict, time elapsed
- References `docs/wave-engine.md` and `fakoli-crew/docs/flow-protocol.md` for deeper detail

**Agent:** guido

**Verify:** SKILL.md has YAML frontmatter, contains "critic gate" section marked non-negotiable, contains status file protocol, contains graceful degradation language, contains all five default waves, no TODO/TBD placeholders

**Depends on:** Task 6 (execute is the handoff target from plan), Task 2 (hook establishes language context used for verification commands)

---

## Wave 3 (parallel) — Supporting Skills

These three tasks are independent of each other. Dispatch all three agents simultaneously.

---

### Task 8: Verify skill

**File:** `skills/verify/SKILL.md`

**Intent:** The verify skill runs after execution and provides an evidence-gated quality check: language-appropriate tool commands followed by a sentinel dispatch that produces a pass/fail scorecard. Every PASS claim must cite fresh command output from this session.

**Acceptance criteria:**
- YAML frontmatter with `name: verify` and a description that triggers on "check this", "validate", "is this ready", or execute handoff
- Language detection documented: TypeScript (`npx tsc --noEmit && bun test`), Python (`ruff check . && mypy . && pytest`), Rust (`cargo check && cargo test`)
- Sentinel dispatch documented: sentinel receives acceptance criteria from the plan and runs each check independently
- Evidence gate documented and unambiguous: sentinel must NOT claim success without fresh command output from this session; lists what counts (exit code 0, zero errors in output, expected value in output, file at expected path) and what does not count (agent claims, output from previous session, partial output, "should work")
- Scorecard format documented: each acceptance criterion listed with PASS/FAIL and the exact evidence (command + output excerpt)
- No-claim-without-evidence principle stated prominently — this is the core of the skill

**Agent:** guido

**Verify:** SKILL.md has YAML frontmatter, contains evidence gate section with "counts as evidence" / "does not count" distinction, references sentinel agent, no TODO/TBD placeholders

**Depends on:** Task 7 (verify is the handoff target from execute; understands what sentinel checks)

---

### Task 9: Finish skill

**File:** `skills/finish/SKILL.md`

**Intent:** The finish skill guides users through the final disposition of completed work: re-verify tests, determine the base branch, present exactly four options (merge locally, push + PR, keep, discard), and execute the chosen option. It must never auto-merge or auto-push.

**Acceptance criteria:**
- YAML frontmatter with `name: finish` and a description that triggers on "ship it", "create PR", "merge", or verify handoff
- Step 1 documented: re-run tests with fresh evidence; if failing, STOP and report — do not proceed to options
- Step 2 documented: determine base branch via `git merge-base HEAD main`
- Step 3 documented: present exactly these 4 options with no extra explanation: (1) Merge back to `<base-branch>` locally, (2) Push and create a Pull Request, (3) Keep the branch as-is, (4) Discard this work
- Step 4 documented: execute each option — merge, push + `gh pr create`, keep, or discard with typed "discard" confirmation
- Discard confirmation gate documented: require the user to type the word "discard" before deleting any work
- Hard rule stated: never auto-merge, never auto-push — always present options and wait for explicit choice

**Agent:** herald

**Verify:** SKILL.md has YAML frontmatter, the four options are listed verbatim, "discard" confirmation requirement is present, hard rule against auto-merge/auto-push is stated, no TODO/TBD placeholders

**Depends on:** Task 8 (finish is the handoff target from verify)

---

### Task 10: Quick skill

**File:** `skills/quick/SKILL.md`

**Intent:** The quick skill is the fast path for small tasks: no brainstorming, no planning, no waves. It dispatches a single agent, verifies, runs the critic, and is done. The skill must help users recognize when quick mode is appropriate and when the full workflow is needed.

**Acceptance criteria:**
- YAML frontmatter with `name: quick` and a description that triggers when the task description implies a small, bounded change
- Process documented in order: detect scope (estimate files affected) → detect language → dispatch single agent (welder) → run verification → dispatch critic on modified files → if PASS done, if MUST FIX one fix cycle then done
- "When to use" section with concrete examples: bug fixes (1-2 files), parameter changes, import fixes, typos
- "When NOT to use" section with concrete examples: new features spanning 3+ files, architecture changes, anything the user would want a spec for
- Usage syntax documented: `/flow:quick "<task description>"`
- Scope check documented: if estimated scope exceeds 3 files, suggest switching to `/flow:brainstorm`
- Single fix cycle maximum — if critic still finds MUST FIX after one round, surface to user rather than looping

**Agent:** guido

**Verify:** SKILL.md has YAML frontmatter, "when to use" and "when NOT to use" sections both present, fix cycle documented as single-iteration maximum, no TODO/TBD placeholders

**Depends on:** Task 7 (quick mirrors execute's agent dispatch and critic gate pattern)

---

## Wave 4 (parallel) — Visual Companion

Both tasks are independent. Dispatch both agents simultaneously. Both depend on Wave 2 (brainstorm skill defines visual companion requirements).

---

### Task 11: Visual companion scripts

**Files:**
- `skills/brainstorm/scripts/start-server.sh`
- `skills/brainstorm/scripts/stop-server.sh`
- `skills/brainstorm/scripts/check-server.sh`
- `skills/brainstorm/scripts/frame-template.html`
- `skills/brainstorm/scripts/helper.js`

**Intent:** The visual companion scripts power the browser-based mockup server used during brainstorming. The implementation should be adapted from the SuperPowers visual companion scripts (at `/Users/sdoumbouya/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/brainstorming/scripts/`) — specifically the PID tracking pattern and platform detection logic. The key new behavior is PID tracking for reliable server state and auto-restart transparency.

**Acceptance criteria for `start-server.sh`:**
- Accepts `--project-dir`, `--host`, `--url-host`, `--foreground`, `--background` flags
- Generates a unique session ID (`$$-$(date +%s)`)
- Creates `SESSION_DIR/content/` and `SESSION_DIR/state/` directories
- Writes server PID to `STATE_DIR/server.pid`
- Auto-detects Windows/Git Bash and Codex environments, switches to foreground mode
- If using `--project-dir`, session lives under `<project>/.fakoli-flow/brainstorm/<session-id>/`; otherwise `/tmp/fakoli-brainstorm-<session-id>/`
- Outputs a JSON object: `{"type":"server-started","port":N,"url":"http://localhost:N","screen_dir":"...","state_dir":"..."}`
- Writes the same JSON to `STATE_DIR/server-info` for recovery
- Waits up to 5 seconds for server to confirm start; exits with error JSON if it doesn't

**Acceptance criteria for `stop-server.sh`:**
- Reads PID from `STATE_DIR/server.pid`
- Sends SIGTERM to the server process
- Removes the PID file
- Exits cleanly if server is already dead

**Acceptance criteria for `check-server.sh`:**
- Reads PID from `STATE_DIR/server.pid`
- Uses `kill -0 $PID` to check if process is alive (does not send a signal, just checks existence)
- Outputs `alive` or `dead` (one word)
- Brainstorm skill uses this before every write to `screen_dir` to decide whether to auto-restart

**Acceptance criteria for `frame-template.html`:**
- Self-contained HTML template the server wraps around content fragments
- Includes CSS theme for: options (A/B/C choices), cards (visual designs), mockup container, split view, pros/cons, mock elements (nav, sidebar, content, button, input)
- Includes the selection indicator bar that shows which option(s) the user has selected
- All scripts injected by the server should be noted with a comment placeholder

**Acceptance criteria for `helper.js`:**
- Client-side script injected by server into every served page
- Handles `toggleSelect(el)` for single and multi-select option clicks
- Records click events to `state_dir/events` as JSON lines: `{"type":"click","choice":"<id>","text":"<label>","timestamp":<unix>}`
- Clears events file when a new screen is served (new HTML file)

**Note on adaptation:** The SuperPowers scripts use `.superpowers/brainstorm/` path convention. fakoli-flow uses `.fakoli-flow/brainstorm/`. Node.js server internals can be adapted directly; only adapt, don't reinvent.

**Agent:** keeper (scripts) + smith (HTML/JS if keeper delegates)

**Verify:**
- All five files exist and are non-empty
- `bash skills/brainstorm/scripts/check-server.sh` outputs `dead` (no server running)
- `bash skills/brainstorm/scripts/start-server.sh --project-dir /tmp/test-fakoli-flow` outputs valid JSON with a `url` key
- `bash skills/brainstorm/scripts/stop-server.sh` (after starting) exits 0

**Depends on:** Task 5 (brainstorm skill defines how these scripts are called and what they must do)

---

### Task 12: Visual companion guide

**File:** `skills/brainstorm/visual-companion.md`

**Intent:** A reference guide the brainstorm skill reads (after the user accepts the companion) to understand how to operate the server, write content fragments, use CSS classes, read browser events, and clean up. Adapted from the SuperPowers visual-companion.md pattern but with fakoli-flow's `.fakoli-flow/brainstorm/` paths and the updated script names.

**Acceptance criteria:**
- "When to use" section with clear use-the-browser vs use-the-terminal guidance (per-question decision, not per-session)
- "How it works" section: server watches content directory, serves newest HTML file, helper.js records click events
- "Starting a session" section: exact `start-server.sh` invocation, JSON output format, how to find `screen_dir` and `state_dir`
- Platform notes: macOS/Linux (default), Windows (run_in_background: true), Codex (auto-detects), Gemini CLI (--foreground + is_background)
- The loop documented: check server alive → write HTML to `screen_dir` → tell user URL + brief summary → on next turn read events → iterate or advance → unload when returning to terminal
- Content fragments vs full documents explained: write fragments by default (server wraps in frame template)
- CSS classes reference: options, cards, mockup, split, pros-cons, mock elements, typography
- Browser events format: JSON lines in `STATE_DIR/events`, event structure
- Design tips: scale fidelity to question, explain question on page, 2-4 options max
- File naming convention: semantic names, never reuse filenames, version suffixes for iterations
- Cleanup: `scripts/stop-server.sh $SESSION_DIR`
- All paths use `.fakoli-flow/brainstorm/` not `.superpowers/brainstorm/`

**Agent:** herald

**Verify:** File exists, contains "When to use" and "How It Works" sections, all script references use `scripts/` paths, no `.superpowers/` paths present, no TODO/TBD placeholders

**Depends on:** Task 11 (scripts must exist before the guide can accurately document them), Task 5 (brainstorm skill defines when the guide is read)

---

## Wave 5 — Documentation + Integration

These two tasks are independent of each other but depend on the full plugin being in place (Waves 1-4 must complete first).

---

### Task 13: Getting started guide

**File:** `docs/getting-started.md`

**Intent:** A practical guide for a developer installing fakoli-flow for the first time. It should get them from zero to running their first brainstorm in under 10 minutes, and introduce the quick path for immediate value on day one.

**Acceptance criteria:**
- Prerequisites section: Claude Code installed, fakoli-crew recommended (with install command), optional for standalone use
- Installation section: `claude plugin install fakoli-flow`, verify with `claude plugin list`
- First run section: start a session, run `/flow` to see skills and project context
- Quick start section: walk through `/flow:quick "add a timeout to the retry function"` as a concrete example showing the single-agent + critic flow
- Full workflow section: walk through `/flow:brainstorm` → spec → `/flow:plan` → plan → `/flow:execute` → waves → `/flow:verify` → scorecard → `/flow:finish` → options
- Visual companion section: when it appears, how to accept/decline, what to do with the URL
- Troubleshooting section: crew not installed (graceful degradation note), server won't start (port conflict, check PID file), detect-context.sh shows "unknown" language
- All commands shown are real and accurate
- Links to `docs/specs/2026-04-04-fakoli-flow-design.md`, `docs/wave-engine.md`, and `docs/intent-driven-orchestration.md` for deeper reading

**Agent:** herald

**Verify:** File exists, all six sections present, no TODO/TBD, all referenced file paths exist in the plugin structure

**Depends on:** Tasks 1-12 (references the full plugin structure)

---

### Task 14: Reference files

**Files:**
- `references/wave-engine-ref.md`
- `references/status-protocol.md`

**Intent:** These are quick-reference cards for the execute skill to include in agent dispatch prompts and for developers building on top of fakoli-flow. They should be dense and scannable — not narrative docs.

**Acceptance criteria for `references/wave-engine-ref.md`:**
- Wave assignment rules: tasks with no dependencies → Wave 1; tasks depending only on Wave N tasks → Wave N+1
- Default wave pattern table: Wave number | Agent types | Purpose | Code writes?
- Critic gate trigger rule: fires after every wave where "Code writes?" is yes
- Fix cycle rule: welder → critic re-review → max 3 iterations → escalate
- Parallel dispatch syntax example (two agents in same wave)
- Agent capabilities table: agent name | creates files | modifies files | reviews only | appropriate tasks
- File ownership rule: no two agents modify the same file in the same wave

**Acceptance criteria for `references/status-protocol.md`:**
- Status file location: `docs/plans/agent-<name>-status.md`
- Full status file format with all sections: Status, Wave, Timestamp, Files Modified, Files Read, Decisions, Notes for Specific Agents, Blockers
- Status values table: IN_PROGRESS / COMPLETE / NEEDS_REVIEW / BLOCKED with meaning and next action for each
- What the orchestrator reads between waves: completion check, blockers, escalations, modified files for critic, upstream decisions for next-wave prompts
- Cross-reference to `fakoli-crew/docs/flow-protocol.md` for canonical definition

**Agent:** herald

**Verify:** Both files exist, `wave-engine-ref.md` contains agent capabilities table and critic gate rule, `status-protocol.md` contains all four status values and the status file format, no TODO/TBD placeholders

**Depends on:** Tasks 1-12 (references the agent protocol and wave patterns established by the skill files)

---

## Verification

After all waves complete, run the full verification pass:

```bash
# 1. Plugin structure is complete
ls .claude-plugin/plugin.json hooks/hooks.json hooks/detect-context.sh \
   commands/flow.md README.md \
   skills/brainstorm/SKILL.md skills/brainstorm/visual-companion.md \
   skills/brainstorm/scripts/start-server.sh \
   skills/brainstorm/scripts/stop-server.sh \
   skills/brainstorm/scripts/check-server.sh \
   skills/brainstorm/scripts/frame-template.html \
   skills/brainstorm/scripts/helper.js \
   skills/plan/SKILL.md \
   skills/execute/SKILL.md \
   skills/verify/SKILL.md \
   skills/finish/SKILL.md \
   skills/quick/SKILL.md \
   docs/getting-started.md \
   references/wave-engine-ref.md \
   references/status-protocol.md

# 2. JSON files are valid
cat .claude-plugin/plugin.json | python3 -m json.tool
cat hooks/hooks.json | python3 -m json.tool

# 3. Scripts are executable
bash hooks/detect-context.sh
bash skills/brainstorm/scripts/check-server.sh 2>/dev/null || true

# 4. No placeholder text remains
grep -r "TODO\|TBD\|placeholder\|FIXME" skills/ hooks/ commands/ references/ docs/getting-started.md README.md

# 5. Visual companion server starts
bash skills/brainstorm/scripts/start-server.sh --project-dir /tmp/test-fakoli-flow-verify
```

Expected: all files exist, JSON valid, scripts executable, no placeholder grep hits, server start outputs JSON with `url` key.
