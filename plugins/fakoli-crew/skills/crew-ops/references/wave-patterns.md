# Wave Execution Patterns

Crews execute in waves to manage dependencies between agents. Each wave runs agents in
parallel where possible, and sequentially only where one agent's output is another's
input.

## The Waves + Critic Gate

### Wave 1 — Research
**Who:** scout
**What:** Gather all information needed before anything is built.
**Outputs:** Research notes, API references, codebase maps, existing pattern inventory.
**Rule:** No code is written or modified in Wave 1.

```
Wave 1
└── scout: read existing source files, map imports, find patterns, produce research docs
```

### Wave 2 — Build (parallel)
**Who:** guido + smith + herald
**What:** Create new abstractions, interfaces, manifests, and structures.
**Input:** Wave 1 research notes.
**Outputs:** New modules, updated manifests, initial docs.
**Rule:** Build agents read Wave 1 outputs before creating anything.

```
Wave 2 (parallel)
├── guido: design interfaces, type definitions, strongly-typed APIs
├── smith: create/update plugin.json, commands, hooks
└── herald: draft README and marketplace description
```

### ── CRITIC GATE ──
**Who:** critic (standing gate, not a wave agent)
**What:** Review all files modified in Wave 2. Report MUST FIX / SHOULD FIX / CONSIDER / NIT.
**Rule:** Runs after EVERY wave that writes code. Non-negotiable.

```
─── CRITIC GATE after Wave 2 ───
critic: review all modified files → severity report
  If MUST FIX → dispatch welder to fix → critic re-reviews (max 3 cycles)
  If PASS → proceed to Wave 3
```

### Wave 3 — Integrate (sequential)
**Who:** welder
**What:** Wire Wave 2 outputs into the existing codebase.
**Input:** ALL files created or modified in Waves 1 and 2.
**Outputs:** Updated existing files with backward-compatible integration.
**Rule:** welder reads every file created by upstream agents before modifying anything.

```
Wave 3 (sequential)
└── welder: read Wave 1 + 2 artifacts → refactor existing code → run tests
```

### ── CRITIC GATE ──
```
─── CRITIC GATE after Wave 3 ───
critic: review all files modified by welder → severity report
  If MUST FIX → welder fixes → critic re-reviews (max 3 cycles)
  If PASS → proceed to Wave 4
```

### Wave 4 — Final Verification
**Who:** sentinel
**What:** Run the full test suite, check version sync, produce pass/fail scorecard.
**Input:** Final state of all modified files after Wave 3 + critic gate.
**Outputs:** Evidence-based scorecard (every PASS cites a command output).
**Rule:** sentinel does not modify code. Reports only. Must run commands and read full output.

```
Wave 4
└── sentinel: run tests, check versions, verify consistency → pass/fail scorecard
```

### Wave 5 — Infrastructure + Judge (main window)
**Who:** keeper + the orchestrating human or main agent
**What:** Sync infrastructure (CLAUDE.md, CI, registry), then review findings and decide.
**Rule:** Only send agents back for MUST FIX severity. Advisory findings can be deferred.

```
Wave 5
├── keeper: update CLAUDE.md, CI workflows, registry (if needed)
├── Review sentinel scorecard
├── If FAIL: dispatch welder (code fixes) or herald (doc fixes)
└── If all PASS: tag release, close the session
```

### The Critic Gate Pattern

Critic is NOT a wave agent — it's a standing quality gate that fires after every wave
that writes code. This is the most important pattern in the crew:

- After Wave 2 (build) → critic reviews
- After Wave 3 (integrate) → critic reviews
- After fix cycles → critic re-reviews

The critic gate caught 26 bugs across 6 phases of the BAARA Next project. Each pass
takes ~2 minutes. Each bug caught saves hours of debugging.

## Real Examples

### Example 1 — Marketplace Overhaul

**Goal:** Standardize all 15 plugin READMEs and regenerate marketplace.json.

```
Wave 1 (parallel):
  scout-1: read plugins/fakoli-tts/ — map all commands and config options
  scout-2: read plugins/fakoli-search/ — map all commands and config options
  scout-3: read plugins/fakoli-crew/ — map all agents and skills

Wave 2 (parallel):
  herald-1: rewrite fakoli-tts README with standard structure
  herald-2: rewrite fakoli-search README with standard structure
  herald-3: rewrite fakoli-crew README with standard structure
  smith:   regenerate marketplace.json from updated plugin.json files

─── CRITIC GATE ───
  critic: review herald's prose for generic language and missing specifics
  2 READMEs flagged SHOULD FIX → herald rewrites → critic re-reviews → PASS

Wave 3 (sequential):
  keeper: update CLAUDE.md plugin count, remove stale references, sync registry

Wave 4:
  sentinel: verify README counts == marketplace.json counts, run validation scripts

Wave 5:
  All PASS → proceed to tag.
```

### Example 2 — Adding a New Agent to an Existing Plugin

**Goal:** Add a new `sentinel` agent to fakoli-crew with full validation suite, frontmatter, and registry integration.

```
Wave 1:
  scout: read all existing agents/*.md — map frontmatter fields, allowed-tools, system prompt patterns

Wave 2 (parallel):
  guido: design the sentinel system prompt — validation checklist, scorecard format, evidence rules
  smith: confirm plugin.json has no agent declarations (agents/ is auto-discovered)

─── CRITIC GATE ───
  critic: review guido's sentinel design for completeness
  Flagged 1 SHOULD FIX — scorecard format missing N/A case → guido fixes → PASS

Wave 3 (sequential):
  welder:
    1. Read scout's pattern map + guido's sentinel prompt
    2. Write agents/sentinel.md with all required frontmatter fields
    3. Add <example> blocks covering 3 distinct trigger phrases
    4. Verify allowed-tools uses hyphen (not underscore)

─── CRITIC GATE ───
  critic: review welder's integration → PASS

Wave 4:
  sentinel: frontmatter fields PASS, example count 3/3 PASS, allowed-tools format PASS

Wave 5:
  All PASS → merge.
```

### Example 3 — Full-Stack Monorepo Build (BAARA Next)

**Goal:** Build a 10-package TypeScript monorepo for a durable task execution engine across 6 phases.

**Phase 1 (Foundation) — 3-wave compressed pattern:**
```
Wave 1 (parallel):
  guido-1: scaffold monorepo root configs (package.json, tsconfig, turbo)
  guido-2: create packages/core with all types, interfaces, events, errors

Wave 2 (parallel):
  welder-1: build packages/store + packages/orchestrator
  welder-2: build packages/agent + packages/executor
  welder-3: build packages/transport + packages/server + packages/cli

Wave 3 (sequential):
  critic: full codebase review — found 10 MUST FIX, 15 SHOULD FIX
  welder: fix all issues
  critic: re-review — PASS
```

**Phase 4 (Chat UI + MCP) — 3-wave with sub-plans:**
```
Wave 1 (parallel):
  welder-A: 27-tool MCP server (packages/mcp) — 12 tasks
  welder-D: thread model (packages/core + packages/store) — 6 tasks

Wave 2 (parallel, after Wave 1):
  welder-B: chat SSE streaming (packages/server) — 6 tasks
  welder-E: CLI mcp-server + chat REPL (packages/cli) — 6 tasks

Wave 3 (after Wave 2):
  welder-C: web UI rewrite (packages/web) — 20 tasks
  critic: final review — found 5 MUST FIX
  welder: fix all
  critic: re-review — PASS
```

**Key learning:** The critic-after-every-wave pattern caught 26 bugs total that would have compounded. Running critic early and often is cheaper than debugging later.

## When to Collapse Waves

For tasks with 1-5 file changes, collapse to the **compressed 3-wave pattern**:
1. **Build** (parallel): appropriate agents create or modify files.
2. **Fix** (sequential): welder resolves any conflicts or typecheck failures.
3. **Review** (parallel): critic + sentinel validate.

Use the full 5-wave pattern when:
- More than 5 files will be modified.
- Multiple agents need to work on different aspects simultaneously.
- The change touches both code and infrastructure (CI, docs, registry).
- Multiple concerns overlap and require separate build phases.

See Example 3 (BAARA Next) for how the compressed 3-wave pattern scales up to handle large parallel builds by running multiple welders inside the Build wave.
