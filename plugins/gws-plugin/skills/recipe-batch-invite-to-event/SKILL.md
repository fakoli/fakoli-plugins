---
name: recipe-batch-invite-to-event
description: "Add a list of attendees to an existing Google Calendar event and send notifications."
trigger:
  - keyword: batch invite
  - keyword: add attendees
  - keyword: bulk invite
---

# Add Multiple Attendees to a Calendar Event

Add a list of attendees to an existing Google Calendar event and send notifications.

## When to Use

Use this workflow when the user needs to add multiple people to an existing event, or bulk-invite a team to a meeting.

## Workflow

### 1. Find the event

Show the user's upcoming events so they can identify the right one:

```bash
gws calendar +agenda --format table
```

### 2. Get current event details

Fetch the event to see existing attendees (you'll need to preserve them):

```bash
gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}' \
  --fields "summary,attendees"
```

### 3. Add new attendees

Merge the existing attendee list with the new ones. Use `--dry-run` first:

```bash
gws calendar events patch \
  --params '{"calendarId": "primary", "eventId": "EVENT_ID", "sendUpdates": "all"}' \
  --json '{"attendees": [EXISTING_PLUS_NEW_ATTENDEES]}' \
  --dry-run
```

Confirm with the user, then execute without `--dry-run`.

### 4. Verify

```bash
gws calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}' \
  --fields "summary,attendees"
```

## Safety

- Always preview with `--dry-run` before patching
- Use `"sendUpdates": "all"` so attendees get notified
- Preserve existing attendees — the `attendees` field is a full replacement, not an append

## Tips

- Ask the user for email addresses as a comma-separated list
- The `attendees` array replaces the entire list — always include existing attendees
