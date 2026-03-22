---
description: Generate a standup report from Google Workspace data
allowed-tools: Bash(gws:*)
---

# /standup-gws

Generate a standup report combining today's calendar and open tasks.

## Instructions

1. Run the standup report:
   ```bash
   gws workflow +standup-report --format table
   ```

2. Present the combined meeting and task summary in a clean standup format:
   - **Today's meetings** — what's on the calendar
   - **Open tasks** — current task list items

3. Offer to help the user compose a formatted standup message from the data.
