# Changelog

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
