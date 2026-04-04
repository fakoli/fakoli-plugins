# Getting Started with fakoli-flow

fakoli-flow coordinates specialist agents through a five-stage pipeline — brainstorm,
plan, execute, verify, finish — without prescribing implementation. Plans describe
acceptance criteria, not code. Quality is enforced through critic gates after every wave.

## Installation

```bash
claude plugin install fakoli-flow
```

Fakoli-flow works standalone but is most powerful paired with fakoli-crew, which provides
the specialist agents (welder, critic, sentinel, guido, smith, herald, scout) used in
wave execution.

```bash
claude plugin install fakoli-crew
claude plugin install fakoli-flow
```

Without fakoli-crew, the wave engine falls back to generic subagents. The pipeline still
runs; you lose the specialized expertise (TDD enforcement, Staff Engineer review depth,
interface-first design).

## The Five-Stage Workflow

```
brainstorm  →  plan  →  execute  →  verify  →  finish
```

| Stage | Skill | What Happens |
|-------|-------|-------------|
| Design | `/flow:brainstorm` | Clarifying questions one at a time → approved spec |
| Plan | `/flow:plan` | Reads spec, verifies assumptions, writes intent-driven task list |
| Execute | `/flow:execute` | Groups tasks into waves, dispatches agents in parallel, critic gates between waves |
| Verify | `/flow:verify` | Sentinel checks all acceptance criteria with fresh evidence |
| Ship | `/flow:finish` | Re-runs tests, presents merge options |

## Quick Mode for Small Tasks

For tasks touching fewer than three files, skip the full workflow:

```
/flow:quick "add a timeout parameter to the retry function"
```

Quick mode: single agent → verify → critic → done.

Use quick mode for: bug fixes, parameter additions, import corrections, renames.
Use the full workflow for: new features, architecture changes, anything you would want a spec for.

## Example Session Walkthrough

### 1. Start with brainstorm

```
/flow:brainstorm I want to add a retry mechanism to our HTTP client
```

The brainstorm skill reads your CLAUDE.md and project files, then asks clarifying
questions one at a time:

```
What should trigger a retry — all failures, or only specific status codes?
  A. All failures (network errors + 5xx)
  B. Network errors only
  C. Configurable per-request
```

After 3-5 questions, it proposes 2-3 approaches, presents the design section by section
(architecture, data model, error handling, testing), and asks you to review each section
before writing the spec.

When you approve, it saves the spec to `docs/specs/YYYY-MM-DD-retry-mechanism.md` and
hands off to `/flow:plan`.

### 2. Plan breaks the spec into tasks

```
/flow:plan docs/specs/2026-04-02-retry-mechanism.md
```

The plan skill runs a scout agent to verify that the libraries and APIs referenced in the
spec actually exist and behave as expected. Then it writes an intent-driven task list to
`docs/plans/YYYY-MM-DD-retry-mechanism.md`:

```markdown
### Task 1: Implement retry logic

**Intent:** HTTP client must retry failed requests with exponential backoff.

**Acceptance criteria:**
- Configurable max retries (default 3) and initial delay (default 500ms)
- Delay doubles each attempt with ±10% jitter
- Only retries on 429, 503, and network errors

**Scope:** src/http-client.ts
**Agent:** welder
**Verify:** bun test — retry scenarios pass
```

### 3. Execute dispatches the agents

```
/flow:execute docs/plans/2026-04-02-retry-mechanism.md
```

The execute skill reads the plan, groups tasks by their declared dependencies into waves,
and dispatches agents in parallel within each wave. After every wave that writes code, a
critic agent reviews all modified files. MUST FIX findings trigger a fix cycle (welder
fixes, critic re-reviews) before the next wave starts.

### 4. Verify checks the result

```
/flow:verify docs/plans/2026-04-02-retry-mechanism.md
```

The sentinel agent reads the acceptance criteria from the plan and verifies each one with
fresh evidence — exit codes, exact test output, actual behavior. Every PASS must be
supported by a specific observation, not an assumption.

### 5. Finish ships the work

```
/flow:finish
```

Re-runs the full test suite, then presents four options:
- Merge locally (fast-forward to main)
- Push to remote + open PR
- Keep branch for later review
- Discard changes

---

## Visual Companion

When brainstorming involves layout, mockups, or visual comparisons, the skill detects
this and offers:

```
This question would be clearer if I can show it to you in a browser.
I can render mockups and diagrams as we go. Want me to fire up the visual companion?
```

The companion is never started without your consent. Once accepted, it stays running for
all visual questions in the session. Textual questions always stay in the terminal.

The server uses PID tracking: before every HTML write, the skill checks
`check-server.sh`. If the server has died (e.g., 30-minute inactivity timeout), it
restarts automatically without asking again.

---

## Where Files Are Saved

| File type | Default location | Override |
|-----------|-----------------|---------|
| Specs | `docs/specs/YYYY-MM-DD-<topic>.md` | Path specified in `CLAUDE.md` |
| Plans | `docs/plans/YYYY-MM-DD-<topic>.md` | Path specified in `CLAUDE.md` |
| Agent status | `docs/plans/agent-<name>-status.md` | Not configurable |
| Visual mockups | `<project>/.fakoli-flow/brainstorm/<session>/` | `--project-dir` argument |

Add `.fakoli-flow/` to `.gitignore` if you use the visual companion.

---

## Further Reading

- [wave-engine.md](wave-engine.md) — How the wave engine groups tasks and dispatches agents
- [intent-driven-orchestration.md](intent-driven-orchestration.md) — Why intent-driven plans outperform prescriptive ones
- [../references/wave-engine-ref.md](../references/wave-engine-ref.md) — Quick reference: wave assignment, dispatch syntax, critic gate
- [../references/status-protocol.md](../references/status-protocol.md) — Agent status file format

## Troubleshooting

**fakoli-crew not installed:**
fakoli-flow works without crew — it falls back to generic subagents. Install crew for specialist agents: `claude plugin install fakoli-crew`

**Visual companion won't start:**
Check for port conflicts. The server picks a random high port. If it fails, check `$STATE_DIR/server.pid` for a stale PID and remove it.

**detect-context.sh shows "unknown" language:**
The hook checks for Cargo.toml (Rust), pyproject.toml (Python), and package.json/tsconfig.json (TypeScript) in the current directory. Make sure you're in the project root.

