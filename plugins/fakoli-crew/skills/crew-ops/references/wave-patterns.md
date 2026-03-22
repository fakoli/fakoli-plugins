# Wave Execution Patterns

Crews execute in waves to manage dependencies between agents. Each wave runs agents in
parallel where possible, and sequentially only where one agent's output is another's
input.

## The Five Waves

### Wave 1 — Research (parallel)
**Who:** scout (and optionally critic for audit-style research)
**What:** Gather all information needed before anything is built.
**Outputs:** Research notes, API references, codebase maps, existing pattern inventory.
**Rule:** No code is written or modified in Wave 1.

```
Wave 1 (parallel)
├── scout: read all existing source files, map imports, find patterns
└── critic: audit existing code for quality issues to fix during the build
```

### Wave 2 — Build (parallel)
**Who:** guido + smith (and optionally herald for concurrent doc drafts)
**What:** Create new abstractions, interfaces, manifests, and structures.
**Input:** Wave 1 research notes.
**Outputs:** New modules, updated manifests, initial docs.
**Rule:** Build agents read Wave 1 outputs before creating anything.

```
Wave 2 (parallel)
├── guido: design Protocol interfaces, dataclasses, type-annotated APIs
├── smith: create/update plugin.json, commands, hooks
└── herald: draft README and marketplace description (can be refined in Wave 5)
```

### Wave 3 — Integrate (sequential)
**Who:** welder
**What:** Wire Wave 2 outputs into the existing codebase.
**Input:** ALL files created or modified in Waves 1 and 2.
**Outputs:** Updated existing files with backward-compatible integration.
**Rule:** welder reads every file created by upstream agents before modifying anything.
**Sequential because:** welder's changes build on guido's and smith's outputs; parallel
execution would cause conflicts.

```
Wave 3 (sequential)
└── welder: read Wave 1 + 2 artifacts → refactor existing code → run tests
```

### Wave 4 — Review (parallel)
**Who:** critic + sentinel
**What:** Validate the integrated result independently.
**Input:** Final state of all modified files after Wave 3.
**Outputs:** Code review findings, pass/fail scorecard.
**Rule:** Neither agent makes changes. They report only.

```
Wave 4 (parallel)
├── critic: line-by-line code review, identify issues by severity
└── sentinel: run test suite, check version sync, verify consistency
```

### Wave 5 — Judge (main window)
**Who:** You (the orchestrating human or main agent)
**What:** Review Wave 4 findings, decide what to fix, dispatch agents for a second pass
if needed.
**Rule:** Only send agents back for issues that are FAIL severity. Advisory findings
can be deferred.

```
Wave 5 (main window)
├── Review sentinel scorecard
├── Review critic findings
├── If FAIL: dispatch welder (code fixes) or herald (doc fixes) or keeper (infra fixes)
└── If all PASS: tag release, update CLAUDE.md, close the session
```

## Real Examples

### Example 1 — Marketplace Overhaul

**Goal:** Standardize all 15 plugin READMEs and regenerate marketplace.json.

```
Wave 1 (parallel):
  scout-1: read plugins/fakoli-tts/ — map all commands and config options
  scout-2: read plugins/fakoli-search/ — map all commands and config options
  scout-3: read plugins/fakoli-crew/ — map all agents and skills
  critic:  audit marketplace.json — find stale entries, missing fields

Wave 2 (parallel):
  herald-1: rewrite fakoli-tts README with standard structure
  herald-2: rewrite fakoli-search README with standard structure
  herald-3: rewrite fakoli-crew README with standard structure
  smith:   regenerate marketplace.json from updated plugin.json files

Wave 3 (sequential):
  keeper: update CLAUDE.md plugin count, remove stale references, sync registry

Wave 4 (parallel):
  sentinel: verify README counts == marketplace.json counts, run validation scripts
  critic:   review herald's prose for generic language and missing specifics

Wave 5:
  Review scorecard. 2 READMEs had generic descriptions → dispatch herald for targeted edits.
  All counts matched → proceed to tag.
```

### Example 2 — Multi-Provider TTS Refactor

**Goal:** Add three new TTS providers behind a unified Protocol interface.

```
Wave 1 (parallel):
  scout:  read existing TTS implementation, document current interface
  critic: audit existing code for tight coupling and missing abstractions

Wave 2 (parallel):
  guido: design ProviderProtocol with synthesize(), list_voices(), stream() methods
  smith: update plugin.json with new provider config fields and hooks

Wave 3 (sequential):
  welder:
    1. Read guido's Protocol + smith's manifest
    2. Create ElevenLabsProvider, PlayHTProvider, AzureProvider implementing Protocol
    3. Refactor existing OpenAIProvider to implement Protocol
    4. Add compat.py re-exporting old TTSClient name
    5. Update CLI entry-points
    6. Run pytest — all 47 tests pass

Wave 4 (parallel):
  sentinel: version sync check (PASS), test suite 47/47 (PASS), manifest fields (PASS)
  critic:   flagged 2 issues — ElevenLabsProvider missing rate-limit retry,
            AzureProvider stream() not handling chunked responses

Wave 5:
  Both critic findings are FAIL severity → dispatch guido to fix before release.
  guido adds retry decorator and fixes stream() chunking.
  Re-run sentinel → all PASS → tag v2.0.0.
```

## When to Collapse Waves

For small tasks (1-2 file changes), collapse to 3 waves:
1. **Read** (scout or self): understand the current state.
2. **Change** (appropriate agent): make the targeted modification.
3. **Verify** (sentinel): confirm nothing broke.

Full 5-wave execution is warranted when:
- More than 3 files will be modified.
- Multiple agents need to work on different aspects simultaneously.
- The change touches both code and infrastructure (CI, docs, registry).
