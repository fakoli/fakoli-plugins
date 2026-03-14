---
name: recipe-share-event-materials
description: "Share Google Drive files with all attendees of a Google Calendar event."
trigger:
  - keyword: share event materials
  - keyword: meeting materials
  - keyword: share with attendees
---

# Share Files with Meeting Attendees

Share Google Drive files with all attendees of a Google Calendar event.

## When to Use

Use this workflow when the user wants to share preparation materials, agendas, or documents with everyone invited to a specific meeting.

## Workflow

### 1. Get event details and attendee list

```bash
gws calendar events get \
  --params '{"calendarId": "primary", "eventId": "EVENT_ID"}' \
  --fields "summary,attendees"
```

Extract the attendee email addresses.

### 2. Share the file with each attendee

For each attendee, grant read access:

```bash
gws drive permissions create \
  --params '{"fileId": "FILE_ID"}' \
  --json '{"role": "reader", "type": "user", "emailAddress": "ATTENDEE_EMAIL"}' \
  --dry-run
```

Confirm the full list with the user, then execute for each attendee.

### 3. Verify sharing

```bash
gws drive permissions list --params '{"fileId": "FILE_ID"}' --format table
```

## Safety

- Preview the attendee list before sharing — events may include people who shouldn't access the file
- Use `--dry-run` on the first permission grant to confirm the format

## Tips

- Use `"role": "reader"` for view-only, `"writer"` if attendees need to collaborate
- Consider adding the file link to the calendar event description for easy access
