---
description: >-
  Create a recurring Google Calendar event with attendees. Trigger when user wants to create a recurring google calendar event with attendees. Uses: calendar.
name: recipe-schedule-recurring-event
version: 1.0.0
---

# Schedule a Recurring Meeting

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-calendar`

Create a recurring Google Calendar event with attendees.

## Steps

1. Create recurring event: `gws calendar events insert --params '{"calendarId": "primary"}' --json '{"summary": "Weekly Standup", "start": {"dateTime": "2024-03-18T09:00:00", "timeZone": "America/New_York"}, "end": {"dateTime": "2024-03-18T09:30:00", "timeZone": "America/New_York"}, "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"], "attendees": [{"email": "team@company.com"}]}'`
2. Verify it was created: `gws calendar +agenda --days 14 --format table`

