# Session tooling program: build, replace, consolidate

**Date:** 2026-08-08 · **Origin:** retrospective of the anvil-serving divergence
program session (13 PRs, 8 features, ~7 subagent dispatches in one day).
**Executors:** assume a sonnet-class implementer; opus only where an issue says
so. Decisions in this document are CLOSED — execute, don't re-litigate.

## Why these four, and only these

That session's token/time waste clustered in exactly three mechanical classes
(ssh/quoting retries, hand-assembled ship gates, ad-hoc subagent packets) plus
one structural cost (an always-loaded roster taxing every session). Each
workstream below kills one class and **explicitly retires something** — the
program's rule is *replace, don't add*: a build that doesn't name what it
retires is rejected.

| # | Workstream | Kills | Retires |
| --- | --- | --- | --- |
| 1 | `fleet-exec` MCP server plugin | ssh/quoting/banner retry class (~30 wasted calls/session) | raw `ssh` Bash calls in sessions; ad-hoc quoting fixes |
| 2 | `gate-router` **ship mode** | hand-assembled test→PR→CI→merge loop (~10 calls × 8/day) | ad-hoc gate typing; `ship-loop`'s internal gate/merge mechanics (delegates instead) |
| 3 | `dispatch-packet` skill | ad-hoc subagent prompt assembly; the 2/7 stall rate | freehand dispatch prompts |
| 4 | Roster prune | fixed per-session context tax of ~100 always-listed skills | every measurably-unused roster entry |

## Source material (the hardening is already written — port, don't reinvent)

All in `fakoli/anvil-serving`, battle-tested on the live fleet 2026-08-08:

- `anvil_serving/fleet.py` — `probe_host` (BatchMode ssh, timeout, state
  classification ok/unreachable/not-installed/timeout), `_remote_hash_script`
  + its **base64 wrapper and client-side quoting** (PR #372 — cmd.exe re-splits
  ssh argv; any spaced `-c` payload must ship quoted, multi-line must ship
  base64), `_local_hostname_matches` (first-DNS-label + `-`-token matching;
  bare containment and bare prefix are both wrong — see PR #371 history),
  python3→python launcher fallback (Windows Store stub answers "Python was
  not found"), `** `-prefixed ssh banner filtering (client advisory banners
  masquerade as errors).
- `docs/FEATURE-EXECUTION-PLAYBOOK.md` — gate sequence, mutation-check
  discipline, environment gotchas. Issues here assume the executor has read it.
- Issues #374–#383 there — the packet format workstream 3 must generate.
- The operator's memory files `subagent-dispatch-discipline` and
  `windows-fleet-shell-gotchas` restate the same facts session-side.

## Execution rules (all four workstreams)

1. One workstream = one branch = one PR in `fakoli/fakoli-plugins`, mirroring
   an existing plugin's layout (`plugins/<name>/.claude-plugin/plugin.json`,
   `skills/`, `commands/`, `scripts/`; `gate-router` is the reference for a
   script-backed plugin). Validate with the repo's own tooling
   (`fakoli-plugin-critic` / `marketplace-manager` if present, else
   `plugin-dev:plugin-validator`).
2. Tests: every script gets an offline test with injected runners — no real
   ssh, docker, or network. Copy the fake-`_run` pattern from anvil's
   `tests/test_fleet_drift.py`.
3. Mutation-check before PR: break the core classification/decision line,
   confirm a test fails, restore. Verify the mutation hit code, not a comment.
4. Each PR body: what it retires (name the roster entries / call patterns),
   and the migration note for existing sessions.
5. The fleet hosts, user names, and addresses are **private operator state** —
   plugins ship with generic examples only; real host config comes from
   `~/.ssh/config` and per-project files, never hardcoded (same
   public/private boundary as anvil ADR-0032).
6. Credentials: never transmitted, never read, structurally unreachable —
   arguments that look like secrets (`token`, `key=`, base64 blobs over N
   chars) are refused, not filtered.

## Consolidation map (workstream 4 input, and the "replace" contract)

When each lands, the retirement is part of the SAME PR or an immediate
follow-up — not a someday:

- **fleet-exec lands** → project CLAUDE.md guidance in fleet-touching repos
  gains "remote exec goes through fleet-exec tools, raw ssh is a fallback for
  diagnosing fleet-exec itself"; the anvil `fleet version/drift` product verbs
  stay (product surface ≠ session tool — they serve CI and operators without
  Claude).
- **gate-router ship mode lands** → `ship-loop` is refactored to delegate its
  gate/PR/CI/merge mechanics to gate-router (its value is the workflow around
  them: isolate, scope, adversarial review); `commit-commands:commit-push-pr`
  stays for un-gated repos, and its README says so.
- **dispatch-packet lands** → it lives inside `ship-loop` (a skill there), not
  standalone — one home for orchestration discipline.
- **Roster prune** → measurement first (`session-report` / `explain-usage`
  over the last ~30 sessions), then archive — `fakoli-plugins/archive/`
  already exists as the destination; nothing is deleted.

## Fidelity notes for the executing session

- Read this document, then the anvil playbook, THEN the issue — in that order.
- Anti-stall: first file edit within ~5 tool calls of finishing the reads.
- When an issue's spec conflicts with observed reality, prefer reality, say so
  in the PR, and keep the change minimal — do not redesign.
- Live validation against real hosts is `[operator]`-gated: produce the exact
  command list for the operator instead of running it.
