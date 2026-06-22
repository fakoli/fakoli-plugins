---
name: recall
description: Show this project's saved cross-session handoff note (the resume point shared across checkouts of the same git remote and across linked worktrees). Use when the user types /recall, asks "where did we leave off?", "what's the handoff?", "what was I working on?", or "catch me up".
allowed-tools: Bash, Read
---

# Show the project handoff

Print the durable resume note for THIS project (the same note from every
checkout of the same git remote, and from every linked worktree of local repos).

## Steps

1. Resolve the path:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/handoff-path.sh"
   ```

2. If the file exists and is non-empty, `Read` it and show it to the user
   verbatim, then offer to act on the top item under **Resume**.

3. If it is missing or empty, tell the user there is no saved handoff for this
   project yet and suggest `/handoff:handoff` to create one.
