---
description: Prepare for your next meeting with agenda and attendees
argument-hint: "[calendar-id]"
allowed-tools: Bash(gws:*)
---

# /meeting-prep

Prepare for your next meeting using the `gws` CLI.

## Instructions

1. Run meeting prep:
   ```bash
   gws workflow +meeting-prep --format table
   ```
   If a calendar ID is provided, add `--calendar '<ID>'`.

2. Present the results showing:
   - Meeting title and time
   - Attendees
   - Description/agenda
   - Linked documents (if any)

3. Offer to help the user prepare notes or send a pre-meeting message to attendees.
