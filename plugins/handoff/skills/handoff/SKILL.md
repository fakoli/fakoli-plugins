---
name: handoff
description: Save or update this project's cross-session handoff note — the resume point for the next session, shared across all git worktrees of the repo. Use when the user types /handoff (optionally with a one-line summary), says "save a handoff", "note where we are for next time", "write a handoff before I clear context", or is wrapping up a session.
allowed-tools: Bash, Read, Write
---

# Save the project handoff

Write or refresh the durable, cross-worktree resume note for THIS project so the
next session — in any git worktree — can pick up exactly where this one left off.

## Steps

1. Resolve the handoff file path (keyed by the git common dir, shared across all
   worktrees — do not compute it yourself):

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/handoff-path.sh"
   ```

   Use the printed path as `<HANDOFF>`. **Never** write the handoff to a
   worktree-local `.remember/` or anywhere inside the repo — only to `<HANDOFF>`.

2. If `<HANDOFF>` already exists, `Read` it first so you preserve still-open
   items from earlier sessions instead of clobbering them.

3. Compose a tight, scannable handoff and overwrite `<HANDOFF>` with `Write`.
   If the user gave a one-line summary with the command (or in their message),
   lead with it. Structure:

   - **Resume** — the 1–3 concrete next actions, most important first (real
     commands, task IDs, file paths, PR numbers — not vague prose).
   - **Open threads** — pending decisions, WIP, blockers.
   - **Recently shipped** — one or two lines for context.
   - **Gotchas** — non-obvious context the next session will need.

4. Confirm to the user: the path written and a one-line summary of what you saved.

## Notes

- This is the LIVE resume note — overwrite it in place, don't append endlessly.
- It complements native auto-memory (`MEMORY.md`): native memory is for durable
  facts/preferences; this handoff is "where we are right now."
- The path is private (under `~/.claude/handoff/`), project-scoped, and the same
  from every worktree of this repo.
