---
name: recipe-block-focus-time
description: "Create recurring focus time blocks on Google Calendar to protect deep work hours."
trigger:
  - keyword: block focus time
  - keyword: deep work
  - keyword: focus block
---

# Block Focus Time on Google Calendar

Create recurring focus time blocks on Google Calendar to protect deep work hours.

## When to Use

Use this workflow when the user wants to block off recurring time for deep work, focus sessions, or protected time on their calendar.

## Workflow

### 1. Check existing schedule

Review the current week to find good slots for focus time:

```bash
gws calendar +agenda --week --format table
```

### 2. Confirm details with the user

Ask the user for:
- **Days** — which weekdays (e.g., Mon-Fri, or specific days)
- **Time window** — start and end time
- **Timezone** — their local timezone
- **Title** — what to call the block (default: "Focus Time")

### 3. Create the recurring block

Use `--dry-run` first to preview:

```bash
gws calendar events insert \
  --params '{"calendarId": "primary"}' \
  --json '{"summary": "Focus Time", "description": "Protected deep work block", "start": {"dateTime": "START_TIME", "timeZone": "TIMEZONE"}, "end": {"dateTime": "END_TIME", "timeZone": "TIMEZONE"}, "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"], "transparency": "opaque"}' \
  --dry-run
```

Confirm with the user, then execute without `--dry-run`.

### 4. Verify it shows as busy

```bash
gws calendar +agenda --format table
```

## Safety

- Always `--dry-run` before creating recurring events — they're hard to undo in bulk
- Set `"transparency": "opaque"` so the block shows as "busy" to others

## Tips

- Use `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR` for specific days
- Add `COUNT=12` to the RRULE to limit to 12 weeks instead of indefinitely
