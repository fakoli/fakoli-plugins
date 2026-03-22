---
description: Show upcoming calendar events
argument-hint: "[today | tomorrow | week | days N]"
allowed-tools: Bash(gws:*)
---

# /agenda

Show upcoming calendar events using the `gws` CLI.

## Instructions

1. Parse the argument to determine the time range:
   - `today` or no argument → `--today`
   - `tomorrow` → `--tomorrow`
   - `week` → `--week`
   - `N` (number) → `--days N`

2. Run the command:
   ```bash
   gws calendar +agenda --today --format table
   ```

3. Present the results in a clean, readable format.

4. If the user asks about a specific calendar, add `--calendar '<NAME>'`.
