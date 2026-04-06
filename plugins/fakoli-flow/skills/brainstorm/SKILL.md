---
name: brainstorm
description: "Design phase — refine ideas into structured specs through collaborative dialogue. Use when starting a new feature, planning architecture, exploring requirements, or turning vague ideas into actionable specifications before coding. Triggers on 'brainstorm', 'design', 'spec', 'plan a feature', 'new feature', 'requirements', and 'explore idea'."
---

# Brainstorm — Design Phase

Turn ideas into fully-formed specs through structured dialogue: explore context, assess scope, ask one question at a time, propose approaches, present the design section by section, and hand off to `/flow:plan`.

<HARD-GATE>
Do NOT invoke `/flow:plan`, write any code, scaffold any files, or take any implementation action until the spec has been written, self-reviewed, and the user has explicitly approved it.
</HARD-GATE>

---

## Process Flow

```
Start
  |
  v
[1. Explore project context]
  Read CLAUDE.md, project files, recent git log.
  Note any output path or naming conventions CLAUDE.md specifies.
  |
  v
[2. Assess scope]
  Does the request describe multiple independent subsystems?
  |
  YES --> Flag decomposition immediately. Do not ask detailed questions yet.
  |       Help the user decompose into sub-projects, then brainstorm the first one.
  |
  NO
  |
  v
[3. Ask clarifying questions]
  One question per message. Multiple choice preferred.
  Focus: purpose, constraints, success criteria.
  |
  v
[4. Auto-detect visual questions]
  Is this question about layout, mockups, diagrams, or visual comparison?
  |
  YES --> Offer visual companion (first time only, its own message).
  |       If accepted: start server, track PID, serve mockup.
  |       Subsequent visual questions in the same session reuse the server.
  |
  NO --> Stay in terminal even if companion is active.
  |
  v
[5. Propose 2-3 approaches]
  Lead with recommendation. Explain trade-offs.
  |
  v
[6. Present design section by section]
  Scale each section to its complexity.
  Ask "Does this section look right?" after each one.
  Revise before moving forward.
  |
  v
[7. Write spec]
  Save to docs/specs/<YYYY-MM-DD>-<topic>.md
  (or the path CLAUDE.md specifies — that path always wins).
  |
  v
[8. Self-review]
  Run the four checks inline. Fix issues before showing the user.
  |
  v
[9. User reviews spec]
  Ask the user to review the file. Wait for explicit approval.
  If changes requested: update the file, re-run self-review, re-ask.
  |
  v
[10. Hand off to /flow:plan]
```

---

## Step-by-Step Rules

### Step 1: Explore Project Context

Before asking anything, read:
- `CLAUDE.md` — project conventions, output paths, naming rules, toolchain
- Key project files (package.json / pyproject.toml / Cargo.toml, src/ structure)
- Recent git log: `git log --oneline -10`

Record any path CLAUDE.md specifies for specs. That path takes precedence over the default `docs/specs/` in every subsequent step.

### Step 2: Assess Scope

Scope check happens BEFORE detailed questions. If the request names multiple independent subsystems (e.g., "build a platform with chat, billing, file storage, and analytics"), stop immediately:

> "This touches several independent systems. Before we refine details, let's map the pieces:
>
> - System A: [description]
> - System B: [description]
> - System C: [description]
>
> Each should get its own brainstorm → plan → execute cycle. Which do you want to start with?"

Do not ask detailed clarifying questions about a project that needs decomposition first.

### Step 3: Clarifying Questions

- One question per message, always.
- Multiple choice preferred: give 2-4 options with a clear default.
- Open-ended is fine when options would artificially constrain the answer.
- Focus on: purpose, users, constraints, success criteria.
- Stop asking once you have enough to propose approaches. Three to five questions is usually sufficient.

### Step 4: Visual Companion (Conditional)

Offer the visual companion ONLY when the question at hand is inherently visual: mockups, wireframes, layout comparisons, architecture diagrams. Do not offer it for requirement questions, tradeoff lists, or conceptual choices — those are terminal questions regardless of topic.

**First visual question of the session** — send this as its own message, nothing else:

> "This question would be clearer if I can show it to you in a browser. I can render mockups and diagrams as we go. Want me to fire up the visual companion? (Requires opening a local URL)"

Wait for the response. If declined, continue in terminal for all visual questions — diagrams can be rendered as ASCII.

**If accepted:** locate the plugin directory first, then run the start script:

```bash
# Note: Script paths are relative to the fakoli-flow plugin directory.
# Use Glob to locate it if needed:
#   ${CLAUDE_PLUGIN_ROOT}/skills/brainstorm/scripts/
```

Run `${CLAUDE_PLUGIN_ROOT}/skills/brainstorm/scripts/start-server.sh`. The script writes a PID file to `$STATE_DIR`. Before each subsequent write to the server, run `${CLAUDE_PLUGIN_ROOT}/skills/brainstorm/scripts/check-server.sh "$STATE_DIR"`. If it returns "dead", run `start-server.sh` again — no need to ask the user again. They already consented.

After starting or re-verifying the server, print exactly one line:
```
[visual: active on http://localhost:52121]
```
or if offline and will restart on next visual question:
```
[visual: offline — will restart on next visual question]
```

**Textual questions always stay in terminal** — even after the companion is active.

### Step 5: Propose 2-3 Approaches

Present options conversationally. Structure each option as:
- Name
- One-sentence description
- Key trade-offs

Lead with your recommendation and explain why in one sentence. Do not present options as equal if they are not.

### Step 6: Present Design Section by Section

Once you understand what you are building, present the design. Do not present everything at once.

Sections to cover (scale each to its complexity — a sentence if simple, a short paragraph if nuanced):
1. **Architecture** — the overall structure and components
2. **Data model / interfaces** — types, schemas, or key APIs
3. **Data flow** — how information moves through the system
4. **Error handling** — failure modes and how they surface
5. **Testing** — how correctness will be verified

After each section: "Does this section look right before we move on?"

Be ready to revise. A design that gets approved section by section is more reliable than one presented all at once.

### Step 7: Write the Spec

Save the validated design to:
- The path specified in CLAUDE.md (if present) — this always takes priority
- Otherwise: `docs/specs/<YYYY-MM-DD>-<topic>.md`

The spec should be complete enough that a plan can be written from it without re-asking you. Include: goal, context, architectural decisions, data model, key behaviors, error handling, acceptance criteria, and out-of-scope items.

### Step 8: Self-Review

After writing, check the spec against these four criteria. Fix issues inline — no need to re-read:

1. **Placeholder scan** — Any "TBD", "TODO", "implement later", or vague requirements? Resolve them.
2. **Internal consistency** — Does any section contradict another? Does the architecture match the feature descriptions?
3. **Scope** — Is this focused enough for a single plan, or does it need further decomposition?
4. **Ambiguity** — Could any requirement be interpreted two ways? Pick one and make it explicit.

### Step 9: User Review Gate

After self-review passes:

> "Spec written to `<path>`. Please review it and let me know if you want any changes before we start planning."

Wait. If changes are requested: update the file, re-run self-review, ask again.

Only proceed to step 10 once the user explicitly approves.

### Step 10: Hand Off

Invoke `/flow:plan` and pass the spec file path.

---

## When NOT to Brainstorm

Use `/flow:quick` instead when:
- The task is a bug fix in 1-2 files
- Adding or renaming a parameter
- Fixing a typo, import, or config value
- Any task where brainstorming would take longer than the fix itself

Rule of thumb: if you can describe the complete change in one sentence and it touches fewer than 3 files, use `/flow:quick`.

Use brainstorm for: new features, architectural changes, anything spanning multiple files, anything where the user would benefit from seeing a spec before any code is written.

---

## Key Differences from SuperPowers Brainstorming

| SuperPowers brainstorming | fakoli-flow brainstorm |
|---|---|
| Offers visual companion every session, as its own message | Offers only when the current question is inherently visual |
| Saves spec to `docs/superpowers/specs/` always | Reads CLAUDE.md first; honors any path it specifies |
| Loads ~22k tokens of skill content at startup | ~500 tokens (metadata only) — lazy by design |
| Loses track of server state across sessions | PID file + liveness check + auto-restart on next visual question |
| Questions are terminal-only | Works headless — questions through any active channel (Discord, Telegram, etc.) |
| Scope check happens during question phase | Scope check happens BEFORE detailed questions |

---

## Key Principles

- **One question at a time.** Never two questions in the same message.
- **Multiple choice preferred.** Easier to answer than open-ended when options are known.
- **Scope before details.** Decompose large projects before refining any piece.
- **Visual only when visual.** Do not default to the companion. Offer it when visual understanding is genuinely better than text.
- **CLAUDE.md wins on paths.** The project's declared conventions override built-in defaults.
- **No implementation until approved.** The hard gate is absolute.
- **Works headless.** All questions are text-first. The visual companion is additive, never required.
