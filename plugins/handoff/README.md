# handoff

Cross-session, **cross-worktree** project handoff notes for Claude Code — a
durable "resume point" that survives the per-session git worktrees many workflows
spin up.

## The problem it fixes

Some setups create a **new git worktree per session**
(`.../.claude/worktrees/<name>/`). A handoff written to a worktree-local file
(e.g. `<cwd>/.remember/`) is thrown away with that worktree — the next session,
in a different worktree, never sees it.

`handoff` stores the note keyed by the **git common dir**
(`git rev-parse --git-common-dir`), which is shared by every linked worktree of a
repo. So all worktrees of one repo resolve to the **same** handoff file.

## How it works

- **Storage:** `~/.claude/handoff/<repo-key>/handoff.md` — private (your home dir,
  not the repo), project-scoped, independent of Claude Code's internal slugs.
  `<repo-key>` is the sanitized absolute path of the repo root.
- **SessionStart hook** (`hooks/session-start.sh`) — prints the handoff as a
  resume banner at the start of every session (quiet if none exists).
- **`/handoff:handoff [summary]`** — save/refresh the resume note.
- **`/handoff:recall`** — show it on demand.
- **`scripts/handoff-path.sh`** — the single source of truth for path
  resolution, used by the hook and both skills.

It **complements** native auto-memory (`MEMORY.md`): native memory is for durable
facts/preferences; this handoff is the live "where we are right now."

## Install

```bash
# point Claude Code at the plugin dir for a quick local try
claude --plugin-dir /Users/sdoumbouya/code/handoff
```

Or add it to a marketplace and enable `handoff@<marketplace>` in
`~/.claude/settings.json`. Hooks load at session start, so restart Claude Code
after enabling.

## Verify

```bash
# from any worktree of a repo, the path is identical:
bash scripts/handoff-path.sh /path/to/repo
bash scripts/handoff-path.sh /path/to/repo/.claude/worktrees/some-worktree
```

Both should print the same `~/.claude/handoff/<repo-key>/handoff.md`.
