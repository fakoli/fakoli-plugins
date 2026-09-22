---
name: handoff
description: Save or update this project's cross-session handoff note — the resume point for the next session, shared across checkouts of the same git remote and across linked worktrees. Use when the user types /handoff (optionally with a one-line summary), says "save a handoff", "note where we are for next time", "write a handoff before I clear context", or is wrapping up a session.
allowed-tools: Bash Read Write
---

Resolve `PLUGIN_ROOT` from the host-provided `PLUGIN_ROOT` / `CLAUDE_PLUGIN_ROOT`, or from this loaded skill’s directory (`../..`). Use that absolute path for the bundled commands; do not assume the current directory is the install root.


# Save the project handoff

Write or refresh the durable, cross-checkout resume note for THIS project so the
next session in another clone or linked worktree can pick up exactly where this
one left off.

## Steps

1. Resolve the handoff file path (keyed by normalized git remote when available,
   with a git-common-dir fallback for local repos; do not compute it yourself):

   ```bash
   bash "${PLUGIN_ROOT}/scripts/handoff-path.sh"
   ```

   Use the printed path as `<HANDOFF>`. **Never** write the handoff to a
   worktree-local `.remember/` or anywhere inside the repo — only to `<HANDOFF>`.

2. If `<HANDOFF>` already exists, `Read` it first so you preserve still-open
   items from earlier sessions instead of clobbering them. Treat everything
   from a leading `---` line through the next `---` line as machine metadata:
   DISCARD it when composing — step 3 regenerates a fresh block, and carrying
   the old one forward stacks stale `saved_at`/`head` blocks into the prose.

3. Capture the state the note is being saved against (branch, HEAD, dirty
   count, optional anvil claim snapshot — all best-effort):

   ```bash
   bash "${PLUGIN_ROOT}/scripts/handoff-meta.sh"
   ```

   Place its output (a `---`-fenced frontmatter block) at the very TOP of
   `<HANDOFF>`, before the prose. `/recall` compares it against live state to
   flag a stale note. Do not hand-edit the block or reorder its keys.
   The helper records `HANDOFF_SESSION_ID` (or the host's `CODEX_THREAD_ID`)
   and an explicitly selected `HANDOFF_WORKSTREAM_ID` when available. If the
   host supplies its session ID only in context, pass it as `HANDOFF_SESSION_ID`
   to this command. Never guess scope from the project, branch or note title.
   Automatic injection requires an exact session match, or an exact workstream
   match when the host explicitly selects one. Missing scope keeps the note
   available through `/handoff:recall` without automatically loading its prose.

4. Compose a tight, scannable handoff and write it below the frontmatter,
   overwriting `<HANDOFF>` with `Write`. If the user gave a one-line summary
   with the command (or in their message), lead with it. Structure:

   - **Resume** — the 1–3 concrete next actions, most important first (real
     commands, task IDs, file paths, PR numbers — not vague prose).
   - **Open threads** — pending decisions, WIP, blockers.
   - **Recently shipped** — one or two lines for context.
   - **Gotchas** — non-obvious context the next session will need.

5. Confirm to the user: the path written and a one-line summary of what you saved.

## Notes

- This is the LIVE resume note — overwrite it in place, don't append endlessly.
- It complements native auto-memory (`MEMORY.md`): native memory is for durable
  facts/preferences; this handoff is "where we are right now."
- The path is private (under `~/.claude/handoff/`), project-scoped, and the same
  from every checkout of the same remote or linked worktree of a local repo.
