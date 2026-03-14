---
description: Prepare for your next meeting with attendees, agenda, and linked docs
argument-hint: "[--calendar CALENDAR_NAME]"
allowed-tools: [Bash]
---

# /gws-meeting-prep

Prepare for your next meeting using the `gws` CLI.

## Instructions

Run the meeting preparation workflow which gathers attendees, description, and linked documents:

```bash
gws workflow +meeting-prep
```

For a specific calendar:
```bash
gws workflow +meeting-prep --calendar "CALENDAR_NAME"
```

## What It Includes

- Next meeting details (time, attendees, description)
- Linked Drive documents from the event
- Attendee information

## Tips

- Run this 5-10 minutes before a meeting for quick prep.
- Combine with `/gws-docs` to review linked documents.

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
