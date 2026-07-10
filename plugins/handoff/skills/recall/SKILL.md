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

2. If the file exists and is non-empty, `Read` it and show the user the
   PROSE (everything below the `---` frontmatter block, when one is present —
   the frontmatter is machine metadata, not part of the note).

3. Check whether the note is still current before recommending its Resume
   items:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/handoff-freshness.sh"
   ```

   Surface every `STALE` line to the user prominently (branch moved, HEAD
   advanced/diverged, recorded anvil claim no longer active, note older than
   `HANDOFF_MAX_AGE_DAYS`). A legacy note reports "freshness unavailable" —
   say so and continue. Then offer to act on the top item under **Resume**,
   adjusted for any staleness (e.g. re-verify a Resume step whose claim was
   released).

4. If it is missing or empty, tell the user there is no saved handoff for this
   project yet and suggest `/handoff:handoff` to create one.
