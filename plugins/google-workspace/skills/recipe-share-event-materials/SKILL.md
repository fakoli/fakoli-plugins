---
description: >-
  Share Google Drive files with all attendees of a Google Calendar event. Trigger when user wants to share google drive files with all attendees of a google calendar event. Uses: calendar, drive.
name: recipe-share-event-materials
version: 1.0.0
---

# Share Files with Meeting Attendees

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-calendar`, `gws-drive`

Share Google Drive files with all attendees of a Google Calendar event.

## Steps

1. Get event attendees: `gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'`
2. Share file with each attendee: `gws drive permissions create --params '{"fileId": "FILE_ID"}' --json '{"role": "reader", "type": "user", "emailAddress": "attendee@company.com"}'`
3. Verify sharing: `gws drive permissions list --params '{"fileId": "FILE_ID"}' --format table`

