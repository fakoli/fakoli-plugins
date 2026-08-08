# Roster prune — measurement, verdicts, and the operator action list

**Date:** 2026-08-08 · **Issue:** [#145](https://github.com/fakoli/fakoli-plugins/issues/145)
· **Program:** [SESSION-TOOLING-PROGRAM](SESSION-TOOLING-PROGRAM.md) workstream 4

Every installed skill, plugin command, and plugin agent is listed in the system
prompt of **every** session, used or not. That listing is a fixed tax paid
before any work happens. This document measures the tax, buckets each roster
unit, and hands the operator an approval list.

The instrument is [`scripts/roster-audit.py`](../scripts/roster-audit.py),
guarded by [`tests/test-roster-audit.sh`](../tests/test-roster-audit.sh).

---

## 1. What the measurement found

Two passes over the same corpus (`~/.claude/projects/**/*.jsonl`), run
separately as a cross-check on the parsing — **not** two independent
instruments:

| Pass | Scope | Result |
| --- | --- | --- |
| `session-report`'s bundled analyzer (`analyze-sessions.mjs --json`) | 142 sessions, 25,354 API calls, all-time | 22 units with recorded use |
| Direct transcript scan | 779 files, 113,894 lines, 0 parse failures | 19 units via Skill tool-calls; 17 distinct slash commands |

**They do not fully agree, and the gap is informative.** 22 vs 19: the
analyzer's `by_skill` includes `ponytail:ponytail-audit` and
`product-management:product-brainstorming`, which entered as *slash commands*
rather than Skill tool-calls. Counting only one invocation form is the classic
undercount; the union across both forms is ~24 units with any recorded use, out
of **57 loaded units**. What the cross-check establishes is that the parsing is
sound — not that the usage signal is complete. See §6 for what it still misses.

### The fixed cost

| Scope | Units | Entries | Est. tokens |
| --- | --- | --- | --- |
| Global user skills (`~/.claude/skills/`) | 20 | 20 | 2,094 |
| Plugins (both install roots) | 48 | 218 | 17,077 |
| Project-scoped (out of scope) | 1 | 10 | 418 |
| **Raw inventory** | **69** | **248** | **19,589** |
| **Loaded cost — the figure a prune moves** | **57** | — | **16,508** |

The loaded figure counts only enabled, non-project units and deduplicates by
plugin name. A disabled unit is not listed in any prompt and a plugin installed
under two roots is listed once, so charging for either would make the
before/after delta of disabling something come out as zero.

Cost is `ceil((len(id) + len(description)) / 4)` per entry — an estimate for
relative comparison, not a measurement. Percentages below are **of measured
roster listing**, not of the whole system prompt (§6 names what is outside it).

### Two findings that changed the shape of this work

**The roster has two install mechanisms, not one.** `~/.claude/plugins/cache/`
holds the CLI's 27 enabled plugins. The desktop app materialises a *separate*
set of 27 under a session-scoped runtime directory
(`AppData/Roaming/Claude/local-agent-mode-sessions/<id>/<id>/rpm/plugin_*/`).
`caveman`, `ponytail`, `data`, `design`, `engineering`, `finance`,
`operations`, `product-management` and others exist **only** there and are
invisible to `enabledPlugins`. An audit of the CLI cache alone measures roughly
half the roster. Hence `--plugin-root`, which §5's command passes.

**Thirteen plugins are installed under both roots.** A live session lists each
once, so the duplication costs no context — but it is a version-drift hazard.
See CONSOLIDATE.

---

## 2. The rubric applied

From the issue, in order — first match wins:

1. KEEP regardless: safety/boundary skills, anything another kept unit depends
   on, anything under 30 days old.
2. KEEP: recorded use.
3. CONSOLIDATE: functional overlap — name the survivor.
4. ARCHIVE: zero use, no standing role, not a dependency.
5. **When torn: KEEP.** A wrong prune breaks a session; a kept dud costs ~40
   tokens. That asymmetry is encoded in the tool, which only ever emits
   `CANDIDATE` — never `ARCHIVE`. A human assigns the bucket.

The prune **unit** is a plugin or a standalone global skill, never an
individual skill: `enabledPlugins` and the desktop plugin UI both toggle whole
plugins.

**Bucket naming.** The issue's fourth bucket is ARCHIVE, meaning *move into
`fakoli-plugins/archive/` with a tombstone*. This document calls it **DISABLE**,
because §4 establishes that the archive mechanism does not exist for 7 of the 9
units and would not change session cost for the other 2. Approving §3a approves
**local configuration changes, not repository moves.** The rename is deliberate
so that approval cannot be mistaken for the issue's original action.

---

## 3. Verdicts

### 3a. DISABLE — proposed, pending `[operator]` approval

Zero recorded use across 142 sessions, no standing role, no cross-unit
dependency, older than the 30-day guard.

| Unit | Entries | Est. tokens | Age | Notes |
| --- | --- | --- | --- | --- |
| `systems-thinking@fakoli-plugins` | 15 | 1,496 | 42d | ships hooks — checked, see below |
| `code-modernization@claude-plugins-official` | 17 | 841 | 41d | no modernization work in window |
| Cloudflare skills with no local tie (6) | 6 | 571 | 47d | see the suite note |
| `microsoft-docs@claude-plugins-official` | 3 | 348 | 41d | |
| `quick-notes@fakoli-plugins` | 3 | 282 | 42d | note store `~/technical-notes/notes.jsonl` was never created |
| `claude-md-management` | 2 | 117 | 41d | both roots; counted once |
| `claude-code-setup` | 1 | 101 | 41d | both roots; counted once |
| `playground` | 1 | 73 | 41d | both roots; counted once |
| `blog-tts-mlx@blog-tts-mlx` | 1 | 62 | 42d | |
| **Total** | **49** | **3,891** | | |

**−3,891 tokens = −23.6% of the 16,508-token loaded roster listing.**

**`systems-thinking` — the hook check, run rather than assumed.** §6 states
that hook-driven plugins are invisible to the usage join, and §3b keeps
`caveman` and `ponytail` on exactly that basis, so the largest DISABLE item
owed the same check. It ships `plugins/systems-thinking/hooks/hooks.json`
registering `SessionStart`, `UserPromptSubmit` and `Stop`. Reading
`hooks/user-prompt-gate.sh` and `hooks/stop-quality-gate.sh`: both are
invocation-gated, so with zero invocations neither fires beyond a `SessionStart`
`uv`/`jq` probe. The verdict survives the check.

**`systems-thinking` and CI.** `scripts/check-all.sh:41` runs its pytest suite
as a repo-wide gate. That is a *repository* role, unaffected by whether the
operator's machine has the plugin enabled — and it is precisely why the bucket
is DISABLE and not the issue's ARCHIVE: moving the plugin to `archive/` would
break that CI step on the first run.

**The Cloudflare suite is split, not archived wholesale.** Eleven global skills
carry Cloudflare content and none has a recorded invocation, which initially
read as one clean 1,064-token cut. It is not: `~/ai-code/sekoudoumbouya`
deploys a **live Cloudflare Worker + D1 backend** (`workers/claps/`, wired
through `npm run claps:setup` and `CLAPS_API` in `src/config.ts`). Zero
invocations is not no standing role, and the rubric says keep when torn:

- **KEEP** — `cloudflare` (95), `wrangler` (86), `durable-objects` (100),
  `workers-best-practices` (96) = 377. They cover a deployment that exists here.
- **KEEP** — `web-perf` (116). Judged on its own, not by adjacency: it contains
  zero occurrences of "cloudflare" and is a generic Chrome-DevTools-MCP
  performance skill. Torn ⇒ keep.
- **DISABLE** — `cloudflare-one` (85), `cloudflare-one-migrations` (53),
  `cloudflare-email-service` (133), `turnstile-spin` (100), `sandbox-sdk` (89),
  `agents-sdk` (111) = 571. Zero-Trust/SASE, transactional email, CAPTCHA,
  sandboxed execution, Cloudflare Agents — no counterpart in any of the 135
  repositories under `~/ai-code`, and no call to the connected Cloudflare MCP
  server in any transcript.

Only 3 of the 11 have any inbound reference, so "they cross-reference each
other" is not the reason for treating them together — the shared domain is.

### 3b. KEEP — zero recorded use, but a standing role

| Unit | Est. tokens | Rule | Why it stays |
| --- | --- | --- | --- |
| `caveman@rpm` | 962 | 1 | Hook-driven and active in the session that produced this document. Invocation counters cannot see hook plugins. |
| `ponytail@rpm` | 621 | 1 | Same, and it also has 25 recorded uses. |
| `agent-sdk-dev` | 177 | 1 | The operator's global instruction mandates the Claude Agent SDK for all model-calling code. A standing mandate outranks a zero count. |
| `anvil-pulse@fakoli-plugins` | 169 | 1 | Installed 29d ago — inside the guard — and it is the operator dashboard for `anvil`, the heaviest-used plugin (243 calls). |
| `recall-mode-verifier@fakoli-plugins` | 166 | 1 | 29d, and a verification/safety role. (It references `ship-loop`, not the reverse — an earlier draft had this backwards.) |
| `gate-router@fakoli-plugins` | 155 | 1 | 29d — inside the guard. Workstream 2 expanding it is a plan, not a standing role, and is not what keeps it. |
| `session-report@claude-plugins-official` | 46 | 5 | Kept under *when torn, keep*. The honest position: its analyzer runs from a filesystem path, so the audit works whether or not the roster entry is listed — the standing role does not strictly require the 46 tokens. |
| `pdf`, `find-skills`, `skill-improver`, `code-maturity-assessor`, `vercel-react-best-practices`, `secure-workflow-guide` | 553 | 1 | All under 30 days old; no usage window exists yet. |

### 3c. CONSOLIDATE

| Overlap | Survivor | Action |
| --- | --- | --- |
| 13 plugins under both install roots | one root per plugin | **No token win** — a session lists each once. A version-drift hazard, not a context cost. Follow-up, not this PR. |
| 11 Cloudflare global skills | the 4 covering the live Worker | Split, not merged — see §3a. |

### 3d. Out of scope — operator judgment required

**Desktop-bundled suites the tool cannot age.** No `manifest.json` entry, so no
install date exists and their files are re-materialised every launch; the
under-30-days guard protects them by default. All show **zero recorded use**.
The tool will not nominate them; the operator must decide directly.

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

Disabling all eight brings the combined reduction to **−7,073 tokens (−42.8%)**.

**MCP servers.** Out of scope per the issue — auth state is invisible to the
audit — but the reason must be stated correctly. MCP tool *schemas* are
deferred (surfaced by name, loaded via `ToolSearch`), so they are not a fixed
tax. Each server's **instructions block is not deferred**: this session's
prompt carries multi-paragraph blocks for Airtable, computer-use,
claude-in-chrome, Windows-MCP, Context7, Hugging Face and Microsoft Learn, plus
~250 deferred tool *names* listed verbatim. None of that is in the 16,508
denominator. It is a real, unmeasured share of the fixed cost and a candidate
for the next workstream.

**Project-scoped skills** in `anvil-serving` (10 entries, 418 tokens) are that
repository's product surface and are excluded from the loaded baseline.

---

## 4. Why this PR moves nothing into `archive/`

The issue's step 3 was "move to `fakoli-plugins/archive/` … global `~/.claude`
roster entries and marketplace listings updated the same PR". The second half
is done. The first is not, for one decisive reason and two supporting ones.

**The archive mechanism does not exist for most of the list.** Seven of the
nine DISABLE units are not this repository's plugins:
`code-modernization`, `microsoft-docs`, `claude-md-management`,
`claude-code-setup` and `playground` belong to `claude-plugins-official`;
`blog-tts-mlx` to its own marketplace; the six Cloudflare skills are global
user skills in `~/.claude/skills/`. None can be moved into
`fakoli-plugins/archive/` at all. The issue's archive step is *inapplicable* to
78% of the list by count.

Supporting:

1. **For the remaining two it would be all cost and no benefit.** Plugins load
   from `~/.claude/plugins/cache/`, gated by `enabledPlugins`; the marketplace
   under `~/.claude/plugins/marketplaces/fakoli-plugins` is an independent
   clone, not a link to any working tree. Moving `plugins/systems-thinking` to
   `archive/` changes zero bytes of any session prompt while removing a
   general-purpose published plugin from every consumer — and breaking the CI
   step that runs its tests.
2. **Fifteen of the marketplace's 24 plugins are not installed here**, so no
   usage signal exists for them. Judging them from this data would be inventing
   evidence.

`archive/README.md`'s existing three criteria are about *reuse value* —
project-specific, superseded, no documented reuse path — and neither candidate
meets them. **Disclosure:** this PR also *adds* a paragraph to that file making
the usage-vs-reuse distinction explicit. The conclusion rests on the three
pre-existing criteria, not on the sentence added here; the addition records the
lesson for the next reader.

---

## 5. Operator action list

Approve §3a (and optionally §3d) as a PR review, then apply. Nothing is
destructive: every plugin remains installed and one flag flips back.

CLI-installed plugins — set these to `false` in `enabledPlugins` in
`~/.claude/settings.json`:

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

Global skills — the six Cloudflare skills with no local tie. Move rather than
delete so restoring is one `mv`:

```bash
mkdir -p ~/.claude/skills-disabled && cd ~/.claude/skills && mv cloudflare-one cloudflare-one-migrations cloudflare-email-service turnstile-spin sandbox-sdk agents-sdk ~/.claude/skills-disabled/
```

`cloudflare`, `wrangler`, `durable-objects`, `workers-best-practices` and
`web-perf` deliberately stay — see §3a.

Desktop-installed plugins (§3d) — no config file; use the desktop app's plugin
settings UI.

Re-measure and confirm the delta. The desktop plugin root is session-scoped, so
resolve it with a glob rather than pasting a stale id:

```bash
RPM="$(ls -d "$HOME/AppData/Roaming/Claude/local-agent-mode-sessions"/*/*/rpm | head -1)" && node "$HOME"/.claude/plugins/cache/claude-plugins-official/session-report/*/skills/session-report/analyze-sessions.mjs --json > /tmp/usage.json && python scripts/roster-audit.py --roster-root ~/.claude --usage /tmp/usage.json --plugin-root "$RPM"
```

Omitting `--plugin-root` measures roughly half the roster (45 units / 10,370
tokens) and will not reproduce the 16,508 baseline these percentages use.

**Record what you applied.** The archive+tombstone the issue specified left a
durable, reviewable record; flipping config flags does not. `skills-disabled/`
is untracked, outside git, and will not survive a `~/.claude` reprovision — and
a later reinstall silently forks a second copy. Reversibility is comparable;
auditability is strictly worse. Compensate by pasting the applied list and date
as a comment on issue #145.

---

## 6. Known ceilings of the instrument

- **Hook-driven plugins record zero invocations.** `caveman` and `ponytail`
  shape every response without appearing as a Skill call. Any plugin whose
  value is a hook is invisible to the usage join and must be judged by hand —
  including checking whether its hooks are invocation-gated (see the
  `systems-thinking` check in §3a).
- **Zero invocations does not establish zero standing role.** The Cloudflare
  suite looked like one clean 1,064-token cut until a search of the machine
  turned up a live Worker + D1 deployment. A usage count is evidence about the
  past; a standing role is a claim about the future. Before archiving anything
  domain-shaped, grep the operator's repositories for artifacts of that domain
  and let a hit outrank the count.
- **Ages come from install metadata, never file mtimes.** Both install roots
  re-materialise files, so sixteen unrelated CLI plugins share one mtime.
  CLI-cache units are aged from `installed_plugins.json` `installedAt` —
  deliberately not `lastUpdated`, which is a bulk cache refresh and would reset
  the guard for plugins the operator has had for months. Desktop units use
  `manifest.json` `updatedAt`. **Desktop plugins absent from that manifest
  cannot be aged at all** and fall through to a permanent KEEP — that is why
  §3d exists.
- **Desktop plugins are assumed enabled.** The CLI path reads `enabledPlugins`;
  the desktop root has no equivalent signal the audit can read, so a plugin
  disabled in the desktop UI still counts toward the totals.
- **Bare-name reference matching is deliberately strict**, and that has a cost
  in the dangerous direction. Only slug-shaped (hyphenated) bare names,
  namespaced ids, and delimited forms (`` `name` ``, `/name`) classify —
  otherwise a unit named `update` or `analyze` matches ordinary prose and
  becomes permanently unprunable. A genuine dependency on an unhyphenated name
  written as plain prose is therefore missed by the classifier; those surface
  separately as **weak references** in the report and must be checked by hand
  before archiving.
- **The system prompt is larger than the roster listing.** MCP server
  instruction blocks and deferred tool names are injected every session and are
  not in the denominator, so the percentages describe the roster listing only.
- **Usage is all-time (142 sessions, 2026-06-27 to 2026-08-08), not the issue's
  30-session window — deliberately.** Under the literal last-30-sessions
  window every transcript falls on 2026-08-08 and only 5 units show any use;
  dozens of current KEEPs would read as zero. Every DISABLE nomination stays
  zero under either window, so all-time is strictly the safer basis for a prune
  list.
- **`--usage` is optional and its absence is silent.** Without it every unit
  reads as unused and the candidate list is meaningless. Always pass it.
