---
name: ship-loop
description: Run the full ship loop for a feature or fix — sync and isolate in a worktree, scope with ground-truth sweeps, implement with reality-faithful tests, gate on a multi-angle adversarial review, merge, and close the follow-up loop (promotions ledger, out-of-diff issues). Use when the user says "ship this the usual way", "run the loop", "ship-loop", starts substantive feature/fix work in a fakoli repo, or asks to take a change from idea to merged PR with the standard review gate. The adversarial review is the merge gate — never merge substantive work without it.
user-invocable: true
---

# Ship Loop

The end-to-end procedure for shipping substantive work: every step is
mandatory for feature/fix PRs; docs-only or mechanical diffs may run a lean
review (step 5, one conventions + one accuracy angle) but never zero.

Composition: this skill owns the loop; `/ship` (ship-task plugin), when
installed, owns the mechanical tail of step 6 (push → PR → CI → squash-merge
→ base sync). anvil-tracked projects: run the loop inside `anvil claim` /
`submit` / `apply` so evidence gates apply.

## 1. Sync and isolate

Never reason about, or build on, a stale or shared tree:

- `git fetch origin` FIRST, always. Then check `git status -sb` and the
  current branch of the main checkout — **another agent may be mid-flight in
  it** (dirty tree, unfamiliar branch). If so, do not touch it.
- Work in a dedicated worktree off the fresh remote default:
  `git worktree add ../<repo>-wt-<topic> origin/main -b feat/<topic>`
- Set repo-local git identity if the worktree is fresh
  (`git config user.email/user.name`).

## 2. Scope with ground truth

Dispatch read-only Explore agent(s) with PRECISE questions (file:line
citations required), covering: the existing mechanics you are changing, every
config/pattern precedent to mirror, existing test fixtures to reuse, and the
doc surfaces that must track the change.

**Ground-truth rule**: verify every load-bearing assumption against reality
before building on it — read the actual on-disk data format, the actual env
var values, the actual schema, not the docs or your expectation. (The
`payload_json` incident: a dashboard shipped reading `payload` because both
the code and its fixture encoded the same wrong guess; one `head` of the real
file would have caught it.)

## 3. Implement

- Mirror the repo's own precedents (config knob shapes, gate tiers, error
  codes) — name the precedent in a comment when you introduce a sibling.
- Fail CLOSED in guards and gates: when safety state cannot be established,
  refuse with the escape hatches named, never proceed-with-warning.
- Leave it better: an unrelated break you trip over gets fixed (if small) or
  filed as an issue (if not) — never routed around silently.

### Windows/platform discipline (hard-won)

- Multi-line patch scripts: write them to a file with the Write tool and run
  `python3 patch.py` — bash heredocs MANGLE backslashes (`\\n` arrives as a
  real newline) and the failure is silent when you forget an assert.
- Every patch-script replacement gets an `assert anchor in text` — silent
  no-op replaces are how "fixed" bugs survive.
- ASCII-only in printed CLI output unless the repo reconfigures streams
  (cp1252 consoles crash on ✎/em-dash); `PYTHONUTF8=1` for tooling runs.
- Node cannot spawn `.cmd`/`.bat` directly (CVE-2024-27980 throws EINVAL
  synchronously) and MSYS `/c/...` paths mean nothing to Windows-native
  processes — convert with `cygpath -m`.

## 4. Test against reality

- Hermetic tests with dependency-injected seams (fake `_run`, frozen clocks,
  monkeypatched env) — AND fixtures byte-faithful to the real formats they
  fake. A fixture that mirrors your assumption certifies your bug.
- When new verification makes old fixed-response fakes fail, the fakes were
  never testing that behavior — update them to represent the failure mode,
  and add the missing negative-path test.
- Scrub ambient env (session ids, actor vars) in conftest when behavior
  reads the environment — suites run inside harness sessions.
- Run the FULL suite the repo's own way (check CLAUDE.md — e.g.
  `cd bin && uv run pytest -q`). All green before review.
- **Cross-platform gate**: anything shipped must run on Windows AND Linux,
  under Claude Code AND Codex. Concretely: (a) run shell/script suites on
  real Linux before merge — WSL via the wsl-linux-check discipline
  (git-archive export, never /mnt/c copies) or a CI job on ubuntu-latest;
  (b) ensure the repo's CI actually EXECUTES the new suite on Linux (wire it
  into the workflow — a merged suite nobody runs on Linux is not coverage);
  (c) Codex exposure is skills-first (`.codex-plugin` manifest or documented
  skill parity) — hooks and slash commands do not carry over.

## 5. Adversarial review — THE merge gate

Fire it yourself; never wait to be asked. Launch parallel read-only finder
agents over `git diff main...HEAD`, covering all eight angles (consolidate
into ~4 agents when context is tight, but never drop an angle):

1. **Line-by-line** — every hunk + its enclosing function; inputs/state/
   timing/platform that make each line wrong.
2. **Removed behavior** — every deleted line's invariant, and where it is
   re-established (mode-"x" backups lost to `copy2` was caught here).
3. **Cross-file / boundary tracer** — NON-NEGOTIABLE. Every caller of every
   changed function, in every OTHER process: MCP servers, hook subprocesses,
   spawned CLIs, browsers. Ask "who else constructs this, with which env, on
   which stdin". Three consecutive PRs' worst bugs lived here (payload key
   mismatch; MCP prompt EOF-aborting; session-env divergence killing leases).
4. **Reuse** — re-implementations of existing helpers; version-bump tooling
   that doesn't know new manifests.
5. **Simplification** — dead knobs, unreachable code, ladder smells.
6. **Efficiency** — per-request I/O, hidden latency floors, DOM/alloc churn.
7. **Altitude** — special cases vs the general mechanism; policy living on
   one surface only; truncation/heuristics that became load-bearing.
8. **Conventions** — the repo's CLAUDE.md/AGENTS.md/docs rules, quoted
   rule + violating line; doc surfaces that must track the change.

Then: **verify findings against ground truth** (run the real binary, read the
real file, check the real env format) — finders may hypothesize wrongly in
both directions (the `session_01HA` prefix hypothesis was wrong for the
default env but right for pinned ids). Fix everything CONFIRMED/PLAUSIBLE;
an intentionally-kept design a finder disliked gets its rationale recorded
in code comment + PR body, not silence. Out-of-diff findings: file an issue
with blame refs — flag, never bury.

Re-run the full suite after fixes.

## 6. Ship

- CHANGELOG under `[Unreleased]` (Keep-a-Changelog); explicit
  **BREAKING**/behavior-change callouts for anything automation depends on.
- Commit message: what + why + the review findings fixed; repo trailer
  conventions.
- Push, open the PR with a testing-evidence section (suite counts, live
  smoke), watch CI (`gh pr checks --watch`), squash-merge, delete branch,
  remove the worktree (`git worktree remove`), confirm `origin/main`.

## 7. Close the loop

- If the work maps to a retro-corpus opportunity: update
  `post-session-findings/promotions.json` (status/refs/what-remains), re-run
  both generators, commit and push. The corpus must know what shipped.
- File issues for anything the review surfaced outside the diff.
- Promote durable lessons: repo docs/CLAUDE.md for repo-specific rules,
  agent memory for cross-repo working rules, this skill for process changes.
