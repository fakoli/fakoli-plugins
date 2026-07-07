# handoff

Cross-session, **cross-checkout** project handoff notes for Claude Code: a
durable "resume point" that survives the per-session git worktrees and separate
local clones many workflows spin up.

## The problem it fixes

Some setups create a **new git worktree or clone per session**. A handoff
written to a checkout-local file (for example `<cwd>/.remember/`) is thrown away
with that checkout, or hidden from the next session in a different clone.

`handoff` stores the note keyed by the normalized `origin` remote when one is
available, so separate clones of the same repo resolve to the **same** handoff
file. Local repos without a remote fall back to the **git common dir**
(`git rev-parse --git-common-dir`), which keeps linked worktrees sharing one
note.

## How it works

- **Storage:** `~/.claude/handoff/<repo-key>/handoff.md` — private (your home dir,
  not the repo), project-scoped, independent of Claude Code's internal slugs.
  `<repo-key>` is derived from the normalized `origin` remote when available, or
  from the repo root for local-only repos.
- **SessionStart hook** (`hooks/session-start.py`, with
  `hooks/session-start.sh` kept as the legacy shell wrapper) — injects the
  handoff as a resume banner at the start of every session (quiet if none
  exists). The hook emits Codex/Claude SessionStart JSON on stdout.
- **`/handoff:handoff [summary]`** — save/refresh the resume note.
- **`/handoff:recall`** — show it on demand.
- **`scripts/handoff-path.sh`** — the single source of truth for path
  resolution, used by the hook and both skills.

It **complements** native auto-memory (`MEMORY.md`): native memory is for durable
facts/preferences; this handoff is the live "where we are right now."

## Install

From the Fakoli Plugins marketplace:

```text
/plugin marketplace add fakoli/fakoli-plugins
/plugin install handoff@fakoli-plugins
```

Or enable `handoff@fakoli-plugins` in `~/.claude/settings.json`. For a quick
local try from a checkout, point Claude Code at the plugin dir:

```bash
claude --plugin-dir /path/to/fakoli-plugins/plugins/handoff
```

Hooks load at session start, so restart Claude Code after enabling.

## Verify

```bash
# from any checkout of the same remote, the path is identical:
bash scripts/handoff-path.sh /path/to/repo
bash scripts/handoff-path.sh /path/to/repo/.claude/worktrees/some-worktree
bash scripts/handoff-path.sh /path/to/another-clone-of-the-same-repo
```

Both should print the same `~/.claude/handoff/<repo-key>/handoff.md`.
