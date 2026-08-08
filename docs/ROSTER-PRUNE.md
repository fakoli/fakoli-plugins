# Roster prune — measurement, verdicts, and the operator action list

**Date:** 2026-08-08 · **Issue:** [#145](https://github.com/fakoli/fakoli-plugins/issues/145)
· **Program:** [SESSION-TOOLING-PROGRAM](SESSION-TOOLING-PROGRAM.md) workstream 4

Every installed skill, plugin command, and plugin agent is listed in the system
prompt of **every** session, used or not. That listing is a fixed tax paid
before any work happens. This document measures the tax, buckets each roster
unit, and hands the operator an approval list.

The instrument is [`scripts/roster-audit.py`](../scripts/roster-audit.py),
guarded by [`tests/test-roster-audit.sh`](../tests/test-roster-audit.sh). It is
re-runnable, so the quarterly re-measurement is one command.

---

## 1. What the measurement actually found

Two independent methods, run separately and cross-checked:

| Method | Scope | Result |
| --- | --- | --- |
| `session-report` bundled analyzer (`analyze-sessions.mjs --json`) | 142 sessions, 25,354 API calls, all-time | 22 distinct skills with any recorded use |
| Direct transcript scan of `~/.claude/projects/**/*.jsonl` | 779 files, 113,894 lines, 0 parse failures | 36 Skill-tool invocations across 19 skills; 17 distinct slash commands |

They agree. The union is ~24 distinct roster units with any recorded use, out of
**58 loaded units**.

### The fixed cost

| Scope | Units | Entries | Est. tokens |
| --- | --- | --- | --- |
| Global user skills (`~/.claude/skills/`) | 20 | 20 | 2,094 |
| Plugins (both install roots) | 48 | 218 | 17,077 |
| Project-scoped (out of scope) | 1 | 10 | 418 |
| **Raw total** | **69** | **248** | **19,589** |
| **Deduplicated** (a plugin installed twice is listed once) | **58** | — | **16,926** |

Cost estimate is `ceil((len(id) + len(description)) / 4)` per entry — a
documented estimate for relative before/after comparison, not a measurement.

### Two findings that changed the shape of this work

**The roster has two install mechanisms, not one.** `~/.claude/plugins/cache/`
holds the CLI's 27 enabled plugins. The desktop app materialises a *separate*
set of 27 plugins under a session-scoped runtime directory
(`AppData/Roaming/Claude/local-agent-mode-sessions/<id>/<id>/rpm/plugin_*/`).
`caveman`, `ponytail`, `data`, `design`, `engineering`, `finance`,
`operations`, `product-management`, `productivity` and others exist **only**
there and are invisible to `enabledPlugins`. An audit of the CLI cache alone
measures roughly half the roster. Hence `--plugin-root`.

**Thirteen plugins are installed under both roots** (`plugin-dev`,
`feature-dev`, `commit-commands`, `code-review`, `code-simplifier`,
`skill-creator`, `agent-sdk-dev`, `claude-code-setup`, `claude-md-management`,
`frontend-design`, `playground`, `security-guidance`,
`explanatory-output-style`). A live session lists each **once**, so the
duplication costs no context — but it is a real drift hazard (two copies, two
versions, one name). See CONSOLIDATE below.

---

## 2. The rubric applied

From the issue, in order — first match wins:

1. KEEP regardless: safety/boundary skills, anything another kept unit depends
   on, anything under 30 days old.
2. KEEP: recorded use, or one use that clearly earned its place.
3. CONSOLIDATE: functional overlap — name the survivor and what migrates.
4. ARCHIVE: zero use, no standing role, not a dependency.
5. **When torn: KEEP.** A wrong prune breaks a session; a kept dud costs ~40
   tokens. That asymmetry is encoded in the tool, which only ever emits
   `CANDIDATE` — never `ARCHIVE`. A human assigns the bucket.

The prune **unit** is a plugin or a standalone global skill, never an individual
skill: `enabledPlugins` and the desktop plugin UI both toggle whole plugins.

---

## 3. Verdicts

### 3a. ARCHIVE — proposed, pending `[operator]` approval

Zero recorded use across 142 sessions, no standing role, no cross-unit
dependency. **All are local-disable actions; see §4 for why none of them is a
repository move.**

| Unit | Entries | Est. tokens | Age | Evidence |
| --- | --- | --- | --- | --- |
| `systems-thinking@fakoli-plugins` | 15 | 1,496 | 42d | 0 invocations; largest single line item |
| `code-modernization@claude-plugins-official` | 17 | 841 | 30d | 0 invocations; no legacy-modernization work in window |
| Cloudflare suite (11 global skills) | 11 | 1,064 | 47d | 0 invocations across all eleven — see note |
| `microsoft-docs@claude-plugins-official` | 3 | 348 | 42d | 0 invocations |
| `quick-notes@fakoli-plugins` | 3 | 282 | 56d | 0 invocations |
| `claude-md-management` | 2 | 117 | 42d | 0 invocations |
| `claude-code-setup` | 1 | 101 | 42d | 0 invocations |
| `playground` | 1 | 73 | 30d | 0 invocations |
| `blog-tts-mlx@blog-tts-mlx` | 1 | 62 | 42d | 0 invocations |
| **Total** | **54** | **4,384** | | |

**Cloudflare suite** = `cloudflare`, `cloudflare-one`, `cloudflare-one-migrations`,
`cloudflare-email-service`, `workers-best-practices`, `durable-objects`,
`agents-sdk`, `sandbox-sdk`, `wrangler`, `turnstile-spin`, `web-perf`. These are
eleven separate global skills that cross-reference each other, so a
per-unit rule keeps some and nominates others — an incoherent split. They are
one suite and get one all-or-nothing decision. Zero recorded use of any member.

Against the deduplicated 16,926-token baseline this is a **−4,384 token
(−25.9%) fixed-cost reduction**.

### 3b. KEEP — zero recorded use, but a standing role

Rubric rule 1. Each of these would look prunable on counts alone; each has a
reason that outranks the count.

| Unit | Est. tokens | Why it stays |
| --- | --- | --- |
| `caveman@rpm` | 962 | Hook-driven. Active in the session that produced this document. Invocation counters cannot see hook plugins at all. |
| `ponytail@rpm` | 621 | Same — hook-driven and active, though it also has 25 recorded uses. |
| `agent-sdk-dev` | 177 | The operator's global instruction mandates the Claude Agent SDK for all model-calling code. Standing role beats a zero count. |
| `anvil-pulse@fakoli-plugins` | 169 | Operator dashboard for long autonomous `anvil` runs; `anvil` is the single heaviest-used plugin (243 calls). |
| `recall-mode-verifier@fakoli-plugins` | 166 | Verification/safety role; referenced by `ship-loop`. |
| `gate-router@fakoli-plugins` | 155 | Workstream 2 of this very program expands it into ship mode. |
| `session-report@claude-plugins-official` | 46 | **It is the measurement instrument for this audit** and for the quarterly re-measurement. Its analyzer runs as a script, so it records zero Skill invocations. The clearest case of usage ≠ value in the whole roster. |
| `pdf`, `find-skills`, `skill-improver`, `code-maturity-assessor`, `vercel-react-best-practices`, `secure-workflow-guide` | 553 | All under 30 days old — rubric rule 1, no usage window exists yet. |

### 3c. CONSOLIDATE

| Overlap | Survivor | Action |
| --- | --- | --- |
| 13 plugins installed under both the CLI cache and the desktop root | Pick one install root per plugin | **No token win** — a session lists each once. Deferred: this is a version-drift hazard, not a context cost. Worth a follow-up, not this PR. |
| 11 Cloudflare global skills | — | Folded into the ARCHIVE decision above; they are one suite. |

### 3d. Out of scope — operator judgment required

**Desktop-bundled suites the tool cannot age.** These have no `manifest.json`
entry, so no reliable install date exists and the under-30-days guard protects
them by default. All show **zero recorded use** across 142 sessions. The tool
will not nominate them; the operator must decide directly.

| Unit | Entries | Est. tokens |
| --- | --- | --- |
| `data@rpm` | 10 | 869 |
| `operations@rpm` | 9 | 676 |
| `finance@rpm` | 8 | 584 |
| `design@rpm` | 7 | 496 |
| `productivity@rpm` | 4 | 270 |
| `cowork-plugin-management@rpm` | 2 | 180 |
| `andrej-karpathy-skills@rpm` | 1 | 66 |
| `skill-codex@rpm` | 1 | 41 |
| **Total** | **42** | **3,182** |

If the operator disables all eight, the combined reduction with §3a is
**−7,566 tokens (−44.7%)** against the 16,926 baseline.

**MCP servers.** Explicitly out of scope per the issue — auth state is
invisible to the audit. Worth recording, though: in this harness MCP tool
schemas are **deferred** (surfaced by name, loaded on demand via `ToolSearch`),
so they are not part of the fixed per-session tax the way skill listings are.
Pruning them would not buy what pruning the roster buys.

**Project-scoped skills** in `anvil-serving` (10 entries, 418 tokens) are that
repository's product surface and are never touched here.

---

## 4. Why this PR moves nothing into `archive/`

The issue's decided method was "move to `fakoli-plugins/archive/` with a
tombstone". Measurement contradicts the assumption underneath it, so per the
program's fidelity note (*prefer reality, say so in the PR, keep the change
minimal*), no plugin is moved. Three reasons, each independently sufficient:

1. **The tax is not in this repository.** It lives in `~/.claude/settings.json`
   (`enabledPlugins`) and in the desktop app's plugin set. Archiving a plugin
   *from the marketplace* removes it for every consumer and changes this
   operator's session cost by exactly zero. Only disabling it locally does.
2. **Archiving would destroy public product surface for a private win.** The
   two largest fakoli-plugins candidates — `systems-thinking` (1,496) and
   `quick-notes` (282) — are general-purpose published plugins with no defects.
   `archive/README.md`'s policy is about *reuse value* (project-specific,
   superseded, no documented reuse path), not about one operator's usage.
   Neither meets it.
3. **Fifteen of the marketplace's 24 plugins are not installed here at all**, so
   no usage signal exists for them. Judging them from this data would be
   inventing evidence.

The retirement contract is still honoured — see the PR body — but it retires
*roster entries in the operator's configuration*, which is where the cost is.

---

## 5. Operator action list

Approve §3a (and optionally §3d) as a PR review, then apply. Nothing here is
destructive: every plugin remains installed and one flag flips back.

CLI-installed plugins — edit `enabledPlugins` in `~/.claude/settings.json`,
setting these to `false`:

```
systems-thinking@fakoli-plugins
code-modernization@claude-plugins-official
microsoft-docs@claude-plugins-official
quick-notes@fakoli-plugins
claude-md-management@claude-plugins-official
claude-code-setup@claude-plugins-official
playground@claude-plugins-official
blog-tts-mlx@blog-tts-mlx
```

Global skills — the Cloudflare suite. Move rather than delete, so restoring is
one `mv`:

```bash
mkdir -p ~/.claude/skills-disabled && cd ~/.claude/skills && mv cloudflare cloudflare-one cloudflare-one-migrations cloudflare-email-service workers-best-practices durable-objects agents-sdk sandbox-sdk wrangler turnstile-spin web-perf ~/.claude/skills-disabled/
```

Desktop-installed plugins (§3d) — no config file; use the desktop app's plugin
settings UI.

Then re-measure and confirm the delta:

```bash
node ~/.claude/plugins/cache/claude-plugins-official/session-report/*/skills/session-report/analyze-sessions.mjs --json > /tmp/usage.json && python scripts/roster-audit.py --roster-root ~/.claude --usage /tmp/usage.json
```

---

## 6. Known ceilings of the instrument

Stated plainly so the next run is not misled:

- **Hook-driven plugins record zero invocations.** `caveman` and `ponytail`
  shape every response without ever appearing as a Skill call. Any plugin whose
  value is a hook is invisible to the usage join and must be judged by hand.
- **Desktop plugins without a `manifest.json` entry cannot be aged.** Their
  files are re-materialised each launch, so mtime is always "today". They fall
  through to the under-30-days KEEP guard permanently.
- **Bare-name reference matching is deliberately strict.** A unit named for a
  common word (`update`, `analyze`, `runbook`) would otherwise match ordinary
  prose in dozens of bodies — one earlier draft reported `productivity@rpm` as a
  "dependency of 32" on that basis. Only slug-shaped (hyphenated) bare names,
  namespaced ids, and delimited forms (`` `name` ``, `/name`) count. The trade:
  a genuine single-word dependency expressed in undelimited prose is missed.
- **Usage is all-time, not a rolling window.** 142 sessions span 2026-06-27 to
  2026-08-08. A skill used once in June counts the same as one used yesterday.
- **`--usage` is optional and its absence is silent.** Run without it, every
  unit reads as unused and the candidate list becomes meaningless. Always pass
  it.
