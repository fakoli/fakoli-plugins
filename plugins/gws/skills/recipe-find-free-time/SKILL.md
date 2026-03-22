---
name: recipe-find-free-time
description: "Query Google Calendar free/busy status for multiple users to find a meeting slot."
trigger:
  - keyword: find free time
  - keyword: free slots
  - keyword: availability
version: 1.0.0
---

# Find Free Time Across Calendars

Query Google Calendar free/busy status for multiple users to find a meeting slot.

## When to Use

Use this workflow when the user needs to schedule a meeting and wants to find a time when all participants are available.

## Workflow

### 1. Gather participants

Ask the user for the list of email addresses to check availability for.

### 2. Define the time window

Ask for the date range and business hours to search within.

### 3. Query free/busy status

```bash
gws calendar freebusy query \
  --json '{"timeMin": "START_ISO8601", "timeMax": "END_ISO8601", "items": [{"id": "user1@company.com"}, {"id": "user2@company.com"}]}'
```

### 4. Analyze and present options

Parse the busy blocks from each calendar, find overlapping free windows, and present them to the user.

### 5. Create the event (optional)

If the user picks a slot:

```bash
gws calendar +insert \
  --summary 'MEETING_TITLE' \
  --attendee user1@company.com \
  --attendee user2@company.com \
  --start 'START_TIME' \
  --end 'END_TIME' \
  --dry-run
```

## Safety

- Always `--dry-run` before creating the event

## Tips

- Times must be in RFC 3339 format with timezone (e.g., `2026-03-20T09:00:00-04:00`)
- Check across multiple days if no same-day slots are available
- Suggest the shortest reasonable meeting duration
