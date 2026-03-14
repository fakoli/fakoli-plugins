---
description: >-
  Add a list of attendees to an existing Google Calendar event and send notifications. Trigger when user wants to add a list of attendees to an existing google calendar event and send notifications. Uses:
  calendar.
name: recipe-batch-invite-to-event
version: 1.0.0
---

# Add Multiple Attendees to a Calendar Event

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-calendar`

Add a list of attendees to an existing Google Calendar event and send notifications.

## Steps

1. Get the event: `gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'`
2. Add attendees: `gws calendar events patch --params '{"calendarId": "primary", "eventId": "EVENT_ID", "sendUpdates": "all"}' --json '{"attendees": [{"email": "alice@company.com"}, {"email": "bob@company.com"}, {"email": "carol@company.com"}]}'`
3. Verify attendees: `gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'`

