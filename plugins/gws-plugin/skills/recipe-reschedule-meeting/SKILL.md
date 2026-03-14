---
name: recipe-reschedule-meeting
description: "Move a Google Calendar event to a new time and automatically notify all attendees."
trigger:
  - keyword: reschedule meeting
  - keyword: move meeting
  - keyword: change meeting time
---

# Reschedule a Google Calendar Meeting

Move a Google Calendar event to a new time and automatically notify all attendees.

## When to Use

Use this workflow when the user needs to change the time of an existing meeting and wants attendees notified of the change.

## Workflow

### 1. Find the event

```bash
gws calendar +agenda --format table
```

Ask the user which event to reschedule.

### 2. Get event details

```bash
gws calendar events get \
  --params '{"calendarId": "primary", "eventId": "EVENT_ID"}' \
  --fields "summary,start,end,attendees"
```

### 3. Confirm the new time

Ask the user for the new date/time. Preview the change:

```bash
gws calendar events patch \
  --params '{"calendarId": "primary", "eventId": "EVENT_ID", "sendUpdates": "all"}' \
  --json '{"start": {"dateTime": "NEW_START", "timeZone": "TIMEZONE"}, "end": {"dateTime": "NEW_END", "timeZone": "TIMEZONE"}}' \
  --dry-run
```

### 4. Execute

After user confirmation, run without `--dry-run`. The `"sendUpdates": "all"` parameter ensures all attendees get notified.

## Safety

- Always `--dry-run` first
- `"sendUpdates": "all"` sends email notifications to all attendees — confirm this is desired

## Tips

- Preserve the event duration unless the user explicitly wants to change it
- Check for conflicts at the new time before rescheduling
