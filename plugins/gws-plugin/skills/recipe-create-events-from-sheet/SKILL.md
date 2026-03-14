---
name: recipe-create-events-from-sheet
description: "Read event data from a Google Sheets spreadsheet and create Google Calendar entries for each row."
trigger:
  - keyword: events from sheet
  - keyword: sheet to calendar
  - keyword: import events
---

# Create Calendar Events from a Sheet

Read event data from a Google Sheets spreadsheet and create Google Calendar entries for each row.

## When to Use

Use this workflow when the user has a spreadsheet of events (dates, titles, attendees) and wants to batch-create calendar entries from it.

## Workflow

### 1. Read the event data

```bash
gws sheets +read --spreadsheet SHEET_ID --range "SHEET_NAME!A1:E" --format table
```

Review the data with the user. Confirm which columns map to summary, start time, end time, and attendees.

### 2. Preview events to create

Show the user a list of events that will be created. For each row, preview using `--dry-run`:

```bash
gws calendar +insert \
  --summary 'EVENT_TITLE' \
  --start 'START_DATETIME' \
  --end 'END_DATETIME' \
  --attendee attendee@company.com \
  --dry-run
```

### 3. Create events

After user confirmation, create each event (without `--dry-run`).

### 4. Report results

Summarize: how many events created, any that failed, and links to the calendar.

## Safety

- Always preview ALL events with `--dry-run` before creating any
- Confirm the total count with the user — batch event creation is hard to undo
- Check for duplicate events in the calendar before creating

## Tips

- Ensure date/time formats in the sheet are ISO 8601 (e.g., `2026-03-20T09:00:00`)
- Process rows sequentially — if one fails, stop and report rather than continuing
