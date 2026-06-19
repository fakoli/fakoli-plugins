# Changelog

## 0.1.0

Initial release.

- Cross-session, cross-worktree project handoff notes, keyed by the git common
  dir (shared across all worktrees of a repo) rather than cwd.
- SessionStart hook prints a resume banner from the project's handoff note.
- `/handoff` saves/updates the note; `/recall` shows it.
- Storage under `~/.claude/handoff/<repo-key>/handoff.md` (private, project-scoped).
