---
description: >-
  Create recurring focus time blocks on Google Calendar to protect deep work hours. Trigger when user wants to create recurring focus time blocks on google calendar to protect deep work hours. Uses: calendar.
name: recipe-block-focus-time
version: 1.0.0
---

# Block Focus Time on Google Calendar

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-calendar`

Create recurring focus time blocks on Google Calendar to protect deep work hours.

## Steps

1. Create recurring focus block: `gws calendar events insert --params '{"calendarId": "primary"}' --json '{"summary": "Focus Time", "description": "Protected deep work block", "start": {"dateTime": "2025-01-20T09:00:00", "timeZone": "America/New_York"}, "end": {"dateTime": "2025-01-20T11:00:00", "timeZone": "America/New_York"}, "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"], "transparency": "opaque"}'`
2. Verify it shows as busy: `gws calendar +agenda`

