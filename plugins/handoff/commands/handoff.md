---
description: Save or refresh this project's cross-session handoff note
allowed-tools: Bash, Read, Write
argument-hint: [summary]
---

# /handoff:handoff

Use the `handoff` skill to save or refresh the durable resume note for the current project. If the user supplied a summary, use it as the seed; otherwise inspect the current worktree state and write a concise handoff with resume steps, open threads, recent work, and gotchas.
