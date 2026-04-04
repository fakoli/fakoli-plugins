---
description: Plan phase — break approved specs into intent-driven task lists for crew execution
---

# Plan — Plan Phase

Read an approved spec, verify assumptions with a scout, write an intent-driven task list, and hand off to `/flow:execute`. Plans describe WHAT to achieve — never HOW to implement it.

<HARD-GATE>
Do NOT include implementation code (function bodies, test files, class definitions, step-by-step instructions) in tasks. This is the one inviolable rule of intent-driven planning. Plans that contain prescriptive code age immediately and suppress agent expertise.
</HARD-GATE>

---

## Process Flow

```
Start
  |
  v
[1. Read the spec]
  Load the approved spec file from brainstorm.
  Note: goal, components, constraints, acceptance criteria.
  |
  v
[2. Scout phase]
  If fakoli-crew is installed: dispatch scout to verify assumptions.
  Wait for scout status file. Read findings before writing any task.
  |
  v
[3. Map files and responsibilities]
  Identify which files will be created or modified.
  Assign clear ownership — one task per file group.
  |
  v
[4. Write intent-driven tasks]
  For each task: intent, acceptance criteria, scope, agent, verify, depends on.
  No code. No step-by-step instructions. Acceptance criteria only.
  |
  v
[5. Self-review]
  Check: spec coverage, criteria clarity, dependency graph, agent assignments.
  Fix issues inline.
  |
  v
[6. Save plan]
  Save to docs/plans/<YYYY-MM-DD>-<feature>.md
  (or the path CLAUDE.md specifies).
  |
  v
[7. Hand off to /flow:execute]
```

---

## Step-by-Step Rules

### Step 1: Read the Spec

Load the spec file (passed by brainstorm or provided by the user). Extract:
- The goal (one sentence)
- All stated requirements and acceptance criteria
- Architectural decisions and constraints
- Out-of-scope items (these must NOT appear as tasks)

If no spec file is provided, ask for it before proceeding. Do not plan from memory of a conversation — the spec is the source of truth.

### Step 2: Scout Phase

**If fakoli-crew is installed:** dispatch a scout agent before writing any task:

```
Agent(
  subagent_type = "fakoli-crew:scout",
  prompt = """
    Research task before planning.

    Spec: <path to spec file>
    Goal: <goal from spec>

    Verify:
    1. Do all libraries referenced in the spec exist at the versions implied?
    2. Do all APIs/methods used in the spec actually exist in those libraries?
    3. Are there existing patterns in this codebase that the plan should follow?
    4. Are there any files in scope that already partially implement something in the spec?

    Write your findings to docs/plans/agent-scout-status.md using the standard status file format.
    Status: COMPLETE with findings, or BLOCKED if the spec references something that doesn't exist.
  """
)
```

Wait for `docs/plans/agent-scout-status.md`. Read it fully before writing tasks. If the scout finds that a library or API doesn't exist as described, flag this to the user before proceeding — do not silently write tasks around a broken assumption.

**If fakoli-crew is not installed:** skip the scout. Note at the top of the plan: "Scout phase skipped (fakoli-crew not installed). Verify library availability manually."

### Step 3: Map Files and Responsibilities

Before writing tasks, list which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Each file should have one clear responsibility.
- Tasks that touch the same file should be assigned sequentially, not in parallel.
- Follow existing project conventions (found during context exploration in brainstorm, and from scout findings).

### Step 4: Write Intent-Driven Tasks

Write tasks in the format described below. The core rule: each task describes what to achieve, not how to achieve it. The agent reads the actual codebase and applies its expertise to reach the acceptance criteria.

#### Agent Assignment Rules

Assign agents based on the nature of the work:

| Work Type | Agent |
|---|---|
| New modules, interfaces, type definitions | guido |
| Wiring new code into existing systems, integration, adapters | welder |
| Research, codebase exploration, library verification | scout |
| Plugin manifests, commands, plugin structure | smith |
| README, documentation, changelogs | herald |
| Infrastructure files, CI, config management | keeper |
| Code review with severity ratings | critic |
| Test suite validation, evidence-based pass/fail scorecard | sentinel |
| Any task when fakoli-crew is not installed | generic |

When a task combines creation and integration, prefer welder — it is the generalist integrator.

#### Dependency Declaration Rules

Declare dependencies to enable wave grouping:
- Tasks with no dependencies run in Wave 1 (parallel).
- Tasks depending only on Wave 1 tasks run in Wave 2 (parallel within wave).
- Sequential chains form sequential waves.
- Never create circular dependencies.

If you are uncertain about a dependency, err on the side of declaring it — false sequential ordering wastes time, but false parallel ordering causes conflicts.

---

## Plan Format

Save the plan using this exact structure:

```markdown
# <Feature> — Execution Plan

**Goal:** One sentence describing what this builds.
**Spec:** docs/specs/<date>-<topic>.md
**Language:** TypeScript | Python | Rust (detected from project files)
**Crew:** fakoli-crew v<version> (<n> agents) | generic subagents (fakoli-crew not installed)

---

### Task 1: <name>

**Intent:** What to achieve in one sentence. Start with a verb. Describe the outcome, not the steps.
**Acceptance criteria:**
- Verifiable outcome stated as a fact that can be confirmed true or false
- Each criterion is independently checkable without reading other tasks
- 2-5 criteria per task; more than 5 is a signal the task should be split
**Scope:** exact/file/path.ts, another/file.py (files this agent should focus on)
**Agent:** guido | welder | scout | smith | herald | keeper | sentinel | critic | generic
**Verify:** exact command that proves this task is done (e.g., `bun test src/retry.test.ts`)
**Depends on:** (none) | Task N, Task M

### Task 2: <name>

**Intent:** ...
**Acceptance criteria:**
- ...
**Scope:** ...
**Agent:** ...
**Verify:** ...
**Depends on:** Task 1
```

---

## What Goes in a Task

- **Intent** — one sentence, verb-first, describes the outcome ("Implement retry with exponential backoff", not "We need retry logic")
- **Acceptance criteria** — 2-5 bullets, each independently verifiable, each specific enough that a reviewer can confirm it without judgment calls
- **Scope** — exact file paths the agent should focus on (not directories; files)
- **Agent** — the specific agent whose expertise matches this work type
- **Verify** — the exact shell command that confirms the task is complete
- **Depends on** — which prior task numbers must complete first

## What Does NOT Go in a Task

- Function bodies, class definitions, test file contents
- Line numbers to modify
- Step-by-step instructions ("first do X, then do Y")
- Technology choices the agent should make from the codebase ("use setTimeout")
- Code that references types or modules not yet established

The agent reads the actual codebase before implementing. It will discover existing utilities, patterns, and conventions that a plan written in advance cannot know about. Trust the agent to reach the acceptance criteria.

---

## Exceptions: When to Include Prescriptive Detail

For these domains, include exact content alongside the intent — not instead of it:

**Schema migrations** — Write the exact SQL or migration code. The intent alone is dangerous when data is at stake.

**Security-critical code** — Prescribe the exact algorithm for cryptographic operations and auth flows. "Implement JWT validation" is not sufficient — specify the algorithm, key type, and validation checks.

**API contracts** — If an external system expects a specific request/response format, include the exact schema. The agent cannot discover what an external system expects.

**Configuration values** — List exact env var names, ports, file paths, and default values. Do not leave these to interpretation.

In these cases: write the intent statement first, then add a "Prescriptive detail" subsection with the exact content. The intent still belongs in the plan — it provides the rationale for the prescriptive detail.

---

## Self-Review

After writing the complete plan, check it against these four criteria. Fix issues inline — no need to re-review:

**1. Spec coverage** — Skim every requirement in the spec. Can you point to a task that addresses it? List any gaps and add tasks for them.

**2. Criteria clarity** — Read each acceptance criterion aloud. Can you confirm it true or false from a command's output, without judgment calls? Vague criteria ("error handling is correct") must be made specific ("a request with a missing API key returns HTTP 401 with body `{error: 'unauthorized'}`").

**3. Dependency correctness** — Trace the dependency graph. No circular dependencies. Tasks within the same wave touch different files. Wave ordering is logical (research before build, build before integrate).

**4. Agent assignment** — Every task has an agent. The agent type matches the work. No task is assigned to critic or sentinel except for explicit review tasks at the end.

**5. Code-free check** — Read each task. Does any acceptance criterion contain a code block, numbered step sequence, or function signature? If so, convert it to an intent statement and verifiable criterion.

---

## Plan Header Requirements

Every plan must begin with the four-line header (Goal, Spec, Language, Crew). The Language and Crew fields are detected, not assumed:

- **Language:** check for `Cargo.toml` (Rust), `pyproject.toml` (Python), `tsconfig.json` or `package.json` (TypeScript)
- **Crew:** read the manifest JSON directly to detect fakoli-crew and its version:
  ```bash
  grep '"version"' ~/.claude/plugins/cache/fakoli-plugins/fakoli-crew/*/.claude-plugin/plugin.json 2>/dev/null \
    | head -1 | grep -o '"[0-9][0-9.]*"' | tr -d '"'
  ```
  If the file does not exist, fakoli-crew is not installed — note "generic subagents" in the plan header.

---

## Hand Off

After saving the plan, announce:

> "Plan saved to `<path>`. Handing off to `/flow:execute`."

Then invoke `/flow:execute` with the plan file path.
