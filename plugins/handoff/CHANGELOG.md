# Changelog

## [0.2.0] - 2026-07-09

### Added

- **Handoff freshness** (the retro corpus's handoff-freshness opportunity):
  `/handoff` now records the state it was saved against (branch, HEAD, dirty
  count, optional anvil claim snapshot) as flat frontmatter via the new
  `scripts/handoff-meta.sh`; `/recall` compares it against live repo/anvil
  state via `scripts/handoff-freshness.sh` and surfaces STALE flags (branch
  moved, HEAD advanced vs diverged, recorded claim no longer active, note
  older than `HANDOFF_MAX_AGE_DAYS`, default 14). Legacy notes without
  frontmatter degrade to "freshness unavailable" — fully backward compatible.
- `tests/test-handoff-freshness.sh` (21 assertions, sandboxed git + fake
  anvil shim).

### Fixed

- Windows/MSYS: `git rev-parse --git-common-dir` can emit an absolute
  `C:/...` path, which the absolute-path check (`/*`) missed — the key hint
  degraded to `-git` and local-repo handoffs landed under the wrong key.
  Drive-letter paths are now recognized as absolute (pre-existing; exposed
  by the test suite on Windows).

## 0.1.4

- Add a shell-free Python SessionStart hook that emits the required
  Codex/Claude SessionStart JSON envelope and avoids the Windows `bash.exe` WSL
  launcher timeout.
- Removed unsupported top-level hook metadata from `hooks/hooks.json` so runtime hook loaders accept the session-start handoff hook.

## 0.1.3

- Replace unsupported `author.github` manifest metadata with `author.url`.
- Add slash-command wrappers for `/handoff:handoff` and `/handoff:recall`, matching the README and session-start banner.

## 0.1.2

- Add regression tests proving the handoff resolves to a single path across linked
  worktrees of a **remote-backed** repo, and from a subdirectory of one — the exact
  worktree case the resolver must guarantee (the suite previously covered
  remote-across-clones and local-across-worktrees, but not their intersection).
  No behavior change; the resolver was already worktree-safe.

## 0.1.1

- Share handoff notes across separate local clones of the same `origin` remote,
  while preserving the git-common-dir fallback for local repos and linked
  worktrees.
- Migrate an existing common-dir handoff note into the new remote-scoped path on
  first resolver run.

## 0.1.0

Initial release.

- Cross-session, cross-worktree project handoff notes, keyed by the git common
  dir (shared across all worktrees of a repo) rather than cwd.
- SessionStart hook prints a resume banner from the project's handoff note.
- `/handoff` saves/updates the note; `/recall` shows it.
- Storage under `~/.claude/handoff/<repo-key>/handoff.md` (private, project-scoped).
