---
description: >-
  Move a Google Calendar event to a new time and automatically notify all attendees. Trigger when user wants to move a google calendar event to a new time and automatically notify all attendees. Uses: calendar.
name: recipe-reschedule-meeting
version: 1.0.0
---

# Reschedule a Google Calendar Meeting

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-calendar`

Move a Google Calendar event to a new time and automatically notify all attendees.

## Steps

1. Find the event: `gws calendar +agenda`
2. Get event details: `gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'`
3. Update the time: `gws calendar events patch --params '{"calendarId": "primary", "eventId": "EVENT_ID", "sendUpdates": "all"}' --json '{"start": {"dateTime": "2025-01-22T14:00:00", "timeZone": "America/New_York"}, "end": {"dateTime": "2025-01-22T15:00:00", "timeZone": "America/New_York"}}'`

