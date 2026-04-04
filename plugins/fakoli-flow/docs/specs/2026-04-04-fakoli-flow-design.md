# fakoli-flow v1.0.0 — Design Spec

## Context

fakoli-flow is the workflow orchestration plugin for the Fakoli ecosystem. It coordinates specialist agent plugins (fakoli-crew, systems-thinking-plugin, future plugins) through a structured pipeline: brainstorm → plan → execute → verify → finish.

**Core philosophy: Intent-driven orchestration.** Plans describe WHAT to achieve (acceptance criteria), not HOW to implement it (code). Trusted specialist agents decide the implementation. Quality is enforced through critic gates and evidence-based verification, not prescriptive plans.

**What this replaces:** SuperPowers was used as the orchestration layer during the BAARA Next project. fakoli-flow replaces it with a crew-aware, intent-driven alternative that addresses specific pain points from SuperPowers users (22k token startup, stale code-heavy plans, lost server state, no lightweight path, silent autonomous decisions).

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Location | `plugins/fakoli-flow/` in fakoli-plugins monorepo | Ships with crew, same CI, stays in sync |
| Approach | Reimagined from actual usage, not ported from SuperPowers | SuperPowers' execution model (generic subagents) is fundamentally different from wave-based crew dispatch |
| Hooks | SessionStart only (language + crew detection) | Low friction. Prompt gating and stop hooks deferred to v1.1 |
| Visual companion | Available on visual questions, not default | Auto-detect when visual would help, offer only then. PID tracking for reliable server state. |
| Plan format | Intent-driven (criteria + scope), not prescriptive (code) | Plans don't stale, agents apply live expertise, ~5x shorter |
| Crew dependency | Graceful degradation if crew not installed | Falls back to generic subagents, loses specialization |

---

## Plugin Structure

```
plugins/fakoli-flow/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── brainstorm/
│   │   ├── SKILL.md                # Design phase: 1-question-at-a-time → spec
│   │   ├── visual-companion.md     # Visual companion usage guide
│   │   └── scripts/
│   │       ├── start-server.sh     # Start local mockup server with PID tracking
│   │       ├── stop-server.sh      # Stop server, clean PID file
│   │       ├── check-server.sh     # Verify server is alive (kill -0 $PID)
│   │       ├── frame-template.html # Base HTML template for mockups
│   │       └── helper.js           # Client-side interaction (click events → events file)
│   ├── plan/
│   │   └── SKILL.md                # Plan phase: spec → intent-driven task list
│   ├── execute/
│   │   └── SKILL.md                # Execute phase: wave-based crew dispatch
│   ├── verify/
│   │   └── SKILL.md                # Verify phase: sentinel + evidence gate
│   ├── finish/
│   │   └── SKILL.md                # Ship phase: merge/PR/keep/discard
│   └── quick/
│       └── SKILL.md                # Fast path: <3 files, skip workflow
├── hooks/
│   ├── hooks.json                  # SessionStart hook
│   └── detect-context.sh           # Detect language + crew availability
├── commands/
│   └── flow.md                     # /flow — show skills + current project state
├── docs/
│   ├── intent-driven-orchestration.md  # Philosophy (blog-ready)
│   ├── wave-engine.md                  # Execution model (blog-ready)
│   └── getting-started.md             # Quick start guide
├── references/
│   ├── wave-engine-ref.md          # Wave assignment rules, parallel dispatch
│   └── status-protocol.md          # Agent status file format
├── research/
│   └── superpowers-feedback.md     # User feedback research (already written)
├── README.md
└── LICENSE
```

---

## Skill 1: Brainstorm (`/flow:brainstorm`)

**Trigger:** "design", "spec", "plan this feature", "brainstorm"

**Process:**

1. **Explore context.** Read CLAUDE.md, project files, recent git log. Honor any output path or conventions specified in CLAUDE.md.

2. **Assess scope.** If the request describes multiple independent subsystems, flag immediately. Suggest decomposition before refining details. Each sub-project gets its own brainstorm → plan → execute cycle.

3. **Ask clarifying questions.** One at a time. Multiple choice preferred. Focus on: purpose, constraints, success criteria.

4. **Auto-detect visual questions.** When the question is about layout, mockups, diagrams, or visual comparison:
   - First visual question: "I can show you this in a browser — want me to fire up the visual companion?"
   - If accepted: start server with PID tracking, serve mockups
   - Subsequent visual questions in the same session reuse the server
   - Textual questions stay in terminal even after companion is active

5. **Propose 2-3 approaches.** Lead with recommendation, explain trade-offs.

6. **Present design section by section.** Scaled to complexity. Get approval after each section.

7. **Write spec.** Save to `docs/specs/<date>-<topic>.md` (or path from CLAUDE.md). Self-review: no placeholders, no contradictions, no ambiguity.

8. **User approves.** Hand off to `/flow:plan`.

### Visual Companion Server Management

**PID tracking (fixes SuperPowers' lost-state bug):**
```bash
# start-server.sh writes PID file
echo $$ > "$STATE_DIR/server.pid"

# check-server.sh verifies before every write
PID=$(cat "$STATE_DIR/server.pid" 2>/dev/null)
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  echo "dead"  # Caller should auto-restart
else
  echo "alive"
fi
```

**Auto-restart:** If the server died (30-min inactivity timeout, crash), the brainstorm skill restarts it transparently — no re-asking the user. They already consented.

**Terminal indicator:** After starting or verifying the server, print:
```
[visual: active on http://localhost:52121]
```
or:
```
[visual: offline — will restart on next visual question]
```

### Differences from SuperPowers Brainstorming

| SuperPowers | fakoli-flow |
|---|---|
| Offers visual companion every session | Offers only on visual questions |
| Ignores CLAUDE.md output paths | Reads and honors CLAUDE.md |
| 22k tokens loaded at startup | ~500 tokens (metadata only) |
| Loses track of server state | PID file + liveness check + auto-restart |
| Terminal-only questions | Works headless (Discord, Telegram, channels) |

---

## Skill 2: Plan (`/flow:plan`)

**Trigger:** "break this into tasks", "create a plan", invoked by brainstorm handoff

**Input:** Approved spec file from brainstorm.

**Output:** Intent-driven task list saved to `docs/plans/<date>-<feature>.md`.

### Plan Format

```markdown
# <Feature> — Execution Plan

**Goal:** one sentence
**Spec:** docs/specs/<date>-<topic>.md
**Language:** TypeScript | Python | Rust (detected)
**Crew:** fakoli-crew v2.0.0 (8 agents) | generic subagents

---

### Task 1: <name>

**Intent:** What to achieve in one sentence.
**Acceptance criteria:**
- Verifiable outcome 1
- Verifiable outcome 2
- Verifiable outcome 3
**Scope:** exact/file/paths.ts
**Agent:** guido | welder | scout | smith | herald | keeper
**Verify:** exact command to confirm success
**Depends on:** (none) | Task N

### Task 2: <name>
...
```

### What Goes in a Task

- **Intent** — one sentence describing the goal (not the implementation)
- **Acceptance criteria** — 2-5 bullet points, each independently verifiable
- **Scope** — file paths the agent should focus on
- **Agent** — which crew agent (or "generic" if no crew)
- **Verify** — the exact command that proves the task is done
- **Depends on** — which prior tasks must complete first (for wave grouping)

### What Does NOT Go in a Task

- Implementation code (function bodies, test files, class definitions)
- Line numbers to modify
- Step-by-step instructions ("first do X, then Y, then Z")
- Technology choices the agent should make itself

### Exceptions (Prescriptive When Necessary)

Include exact content for:
- **Schema migrations** — exact SQL (too dangerous to leave to interpretation)
- **Security-critical code** — exact algorithm (cryptographic operations, auth flows)
- **API contracts** — exact request/response format (external systems)
- **Configuration values** — exact env vars, ports, paths

### Scout Phase

Before writing the plan, the plan skill dispatches a scout agent to verify assumptions:
- Do the libraries referenced in the spec actually exist?
- Do the APIs work as described?
- Are there existing patterns in the codebase the plan should follow?

This prevents plans that assume non-existent libraries or APIs — a real issue in SuperPowers where plans reference code that doesn't exist.

### Self-Review

After writing the plan:
1. **Spec coverage** — every requirement in the spec has a task
2. **Criteria clarity** — each acceptance criterion is independently verifiable
3. **Dependency correctness** — no circular dependencies, wave grouping is valid
4. **Agent assignment** — each task has an appropriate agent for the work type

---

## Skill 3: Execute (`/flow:execute`)

**Trigger:** "build this", "run the plan", "execute", invoked by plan handoff

**Input:** Intent-driven plan file.

**Output:** Working code with all acceptance criteria met, verified by critic + sentinel.

### Wave Engine

1. **Load plan.** Parse tasks, dependencies, agent assignments.

2. **Detect agents.** Check if fakoli-crew is installed. Log available agents. Fall back to generic subagents if needed.

3. **Group into waves.** Tasks with no dependencies → Wave 1. Tasks depending on Wave 1 → Wave 2. And so on.

4. **For each wave:**

   a. **Dispatch agents in parallel.** One Agent tool call per task, using `subagent_type="fakoli-crew:<agent>"`. Each agent receives: intent, acceptance criteria, scope, upstream context (from prior wave status files), and verify command.

   b. **Wait for completion.** Read `docs/plans/agent-<name>-status.md` files. Check for COMPLETE, BLOCKED, or NEEDS_REVIEW.

   c. **Handle escalations.** BLOCKED → surface to user, wait for resolution. NEEDS_REVIEW → surface to user, wait for decision.

   d. **Run verification.** Language-detected check:
      - TypeScript: `npx tsc --noEmit`
      - Python: `ruff check . && mypy .`
      - Rust: `cargo check`
      If verification fails → dispatch welder to fix → re-verify.

   e. **Run critic gate (non-negotiable).** Collect modified files from status files. Dispatch critic. If MUST FIX → dispatch welder → re-run critic (max 3 cycles). Proceed only on PASS.

5. **After all waves:** Dispatch sentinel for final verification.

6. **Report summary.** Files modified, tests passing, critic verdict, time elapsed.

### Default Wave Pattern (No Dependencies)

```
Wave 1 — Research (parallel): scout tasks
Wave 2 — Build (parallel): guido + smith + herald tasks
Wave 3 — Integrate (sequential): welder tasks
Wave 4 — Review (parallel): critic + sentinel
Wave 5 — Fix cycle (if MUST FIX found)
```

### Critic Gate Details

After every wave that writes code:
1. Collect modified files from agent status files
2. Dispatch `fakoli-crew:critic` with file list + acceptance criteria
3. Evaluate: PASS → next wave. MUST FIX → fix cycle. SHOULD FIX → log, proceed.
4. Fix cycle: welder fixes → critic re-reviews → max 3 iterations → escalate if stuck

### Parallel Dispatch

Multiple agents in the same wave dispatch simultaneously:
```
Agent(subagent_type="fakoli-crew:welder", prompt="Task 1...")
Agent(subagent_type="fakoli-crew:welder", prompt="Task 2...")  // parallel
Agent(subagent_type="fakoli-crew:guido", prompt="Task 3...")   // parallel
```

Each targets different files. File ownership (from `fakoli-crew/skills/crew-ops/references/file-ownership.md`) prevents conflicts.

---

## Skill 4: Verify (`/flow:verify`)

**Trigger:** "check this", "validate", "is this ready", invoked automatically after execute

**Process:**

1. Detect project language.
2. Run language-appropriate verification:
   - TypeScript: `npx tsc --noEmit && bun test`
   - Python: `ruff check . && mypy . && pytest`
   - Rust: `cargo check && cargo test`
3. Dispatch sentinel with acceptance criteria from the plan.
4. Sentinel runs each check, reads full output, produces pass/fail scorecard.
5. Every PASS must cite evidence (exact command output, not "looks good").
6. Report scorecard to user.

### Evidence Gate

Sentinel must NOT claim success without fresh evidence from a command run in this session:

| Counts as Evidence | Does NOT Count |
|---|---|
| Exit code 0 from test command | "Should work" |
| Zero errors in typecheck output | Output from a previous session |
| Expected value in command output | An agent's claim without verification |
| File existing at expected path | Partial output ("first 10 lines looked fine") |

---

## Skill 5: Finish (`/flow:finish`)

**Trigger:** "ship it", "create PR", "merge", invoked after verify passes

**Process:**

1. Verify tests pass (re-run, fresh evidence). If fail → STOP.
2. Determine base branch: `git merge-base HEAD main`.
3. Present exactly 4 options:
   ```
   1. Merge back to <base-branch> locally
   2. Push and create a Pull Request
   3. Keep the branch as-is
   4. Discard this work
   ```
4. Execute chosen option. Require typed "discard" for option 4.

**Never auto-merge or auto-push.** Always present options and wait for explicit choice.

---

## Skill 6: Quick (`/flow:quick`)

**Trigger:** Small tasks, bug fixes, quick edits. User invokes with task description.

**Process:**

```
/flow:quick "add a timeout parameter to the retry function"

1. Detect scope — estimate files affected (<3 = quick mode appropriate)
2. Detect language — TypeScript (tsconfig.json found)
3. Dispatch single agent:
   Agent(subagent_type="fakoli-crew:welder", prompt="<task>")
4. Run verification: npx tsc --noEmit && bun test
5. Dispatch critic on modified files
6. If PASS → done
7. If MUST FIX → one fix cycle → done
```

**No brainstorming, no planning, no waves.** Just: agent → verify → critic → done.

**When to suggest quick mode:**
- Bug fixes (1-2 files)
- Adding/renaming a parameter
- Fixing a typo or import
- Any task where brainstorming would take longer than the fix

**When NOT to suggest quick mode:**
- New features spanning 3+ files
- Architecture changes
- Anything the user would want a spec for

---

## Hook: SessionStart

### `hooks/hooks.json`

> **Note:** The format below was the design-time proposal. The shipped implementation
> uses the Claude Code native hook schema — see `hooks/hooks.json` for the actual format.

```json
{
  "description": "Detects project language and fakoli-crew availability at session start",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/detect-context.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Key differences from the original design: hooks is an object keyed by event name (not an
array), `command` uses `${CLAUDE_PLUGIN_ROOT}` for portability, and `timeout` is in
seconds (not milliseconds).

> **Format note:** The double-nested `hooks` structure (an outer `hooks` object keyed by
> event name, each value being an array of objects that each contain a nested `hooks`
> array of commands) is the correct Claude Code plugin schema. This matches the
> `safe-fetch` plugin's `hooks/hooks.json` and was verified by the `validate.sh` script.
> The double nesting is intentional — the outer array entry holds a `matcher` (optional)
> and the inner `hooks` array holds the actual command definitions.

### `detect-context.sh`

Detects project language and crew availability. Outputs a single-line summary (~50 tokens):

```bash
#!/bin/bash
LANG="unknown"
[ -f "Cargo.toml" ] && LANG="Rust"
[ -f "pyproject.toml" ] && LANG="Python"
[ -f "package.json" ] && LANG="TypeScript"
[ -f "tsconfig.json" ] && LANG="TypeScript"

# Check for fakoli-crew
CREW="not installed"
CREW_VERSION=""
if claude plugin list 2>/dev/null | grep -q "fakoli-crew"; then
  CREW="installed"
  CREW_VERSION=$(grep '"version"' ~/.claude/plugins/cache/fakoli-plugins/fakoli-crew/*/.claude-plugin/plugin.json 2>/dev/null | head -1 | grep -o '"[0-9.]*"' | tr -d '"')
fi

echo "[fakoli-flow] Language: $LANG | Crew: fakoli-crew ${CREW_VERSION:-$CREW} | Skills: brainstorm, plan, execute, verify, finish, quick"
```

---

## Command: `/flow`

### `commands/flow.md`

```markdown
---
description: Show fakoli-flow skills and current project state
allowed-tools:
  - Bash
  - Glob
---

Display the available fakoli-flow skills and detect the current project context.

## Skills

| Skill | Command | Purpose |
|-------|---------|---------|
| Brainstorm | `/flow:brainstorm` | Design phase — refine ideas into specs |
| Plan | `/flow:plan` | Plan phase — specs into intent-driven task lists |
| Execute | `/flow:execute` | Build phase — wave-based crew dispatch with critic gates |
| Verify | `/flow:verify` | Check phase — sentinel + evidence gate |
| Finish | `/flow:finish` | Ship phase — merge / PR / keep / discard |
| Quick | `/flow:quick <task>` | Fast path — skip workflow for small fixes |

## Workflow

```
brainstorm → plan → execute → verify → finish
                                  ↑
                           quick ──┘ (skip to here)
```

Run `detect-context.sh` to show the current project language and crew status.
```

---

## Plugin Manifest

### `.claude-plugin/plugin.json`

```json
{
  "name": "fakoli-flow",
  "version": "1.0.0",
  "description": "Intent-driven workflow orchestration — brainstorm, plan, and execute complex projects through coordinated specialist agents with critic gates and evidence-based verification.",
  "author": {
    "name": "Sekou Doumbouya",
    "url": "https://github.com/fakoli"
  },
  "repository": "https://github.com/fakoli/fakoli-plugins",
  "license": "MIT",
  "keywords": [
    "workflow",
    "orchestration",
    "planning",
    "brainstorming",
    "intent-driven",
    "agents",
    "wave-engine",
    "TDD",
    "code-review"
  ]
}
```

---

## Verification Plan

1. Install plugin: `claude plugin install fakoli-flow`
2. SessionStart hook fires — shows language + crew status
3. `/flow` command — lists all 6 skills
4. `/flow:brainstorm` — one-question-at-a-time, visual companion on visual questions
5. `/flow:plan` — reads spec, produces intent-driven tasks (no code blocks)
6. `/flow:execute` — dispatches crew agents in waves, critic gate fires after each wave
7. `/flow:verify` — sentinel runs checks with evidence
8. `/flow:finish` — presents 4 options, executes choice
9. `/flow:quick "fix typo"` — single agent dispatch, critic, done
10. Visual companion: server starts, PID tracked, auto-restarts after timeout, clean shutdown
