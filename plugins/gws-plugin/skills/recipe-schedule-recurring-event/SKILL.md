---
name: recipe-schedule-recurring-event
description: "Create a recurring Google Calendar event with attendees."
trigger:
  - keyword: recurring event
  - keyword: recurring meeting
  - keyword: weekly meeting
version: 1.0.0
---

# Schedule a Recurring Meeting

Create a recurring Google Calendar event with attendees.

## When to Use

Use this workflow when the user wants to set up a repeating meeting — weekly standups, biweekly 1:1s, monthly reviews, etc.

## Workflow

### 1. Gather details

Ask the user for:
- **Title** (e.g., "Weekly Standup")
- **Day/time** and timezone
- **Duration**
- **Recurrence pattern** (weekly, biweekly, monthly)
- **Attendees** (email addresses)

### 2. Build the recurrence rule

Common RRULE patterns:
- Weekly on Monday: `RRULE:FREQ=WEEKLY;BYDAY=MO`
- Biweekly on Tuesday: `RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU`
- Monthly first Wednesday: `RRULE:FREQ=MONTHLY;BYDAY=1WE`
- Daily weekdays: `RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR`

### 3. Create the event

```bash
gws calendar events insert \
  --params '{"calendarId": "primary"}' \
  --json '{"summary": "TITLE", "start": {"dateTime": "START", "timeZone": "TZ"}, "end": {"dateTime": "END", "timeZone": "TZ"}, "recurrence": ["RRULE"], "attendees": [{"email": "ATTENDEE"}]}' \
  --dry-run
```

Confirm with the user, then execute.

### 4. Verify

```bash
gws calendar +agenda --days 14 --format table
```

## Safety

- Always `--dry-run` first — recurring events create many instances
- Add `COUNT=N` to the RRULE to limit the number of occurrences

## Tips

- Use `UNTIL=20261231T000000Z` in the RRULE to set an end date
- The first occurrence date is set by the `start` field, not the RRULE
