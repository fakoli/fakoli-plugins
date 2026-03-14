---
description: >-
  Read event data from a Google Sheets spreadsheet and create Google Calendar entries for each row. Trigger when user wants to read event data from a google sheets spreadsheet and create google calendar
  entries for each row. Uses: sheets, calendar.
name: recipe-create-events-from-sheet
version: 1.0.0
---

# Create Google Calendar Events from a Sheet

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-sheets`, `gws-calendar`

Read event data from a Google Sheets spreadsheet and create Google Calendar entries for each row.

## Steps

1. Read event data: `gws sheets +read --spreadsheet SHEET_ID --range "Events!A2:D"`
2. For each row, create a calendar event: `gws calendar +insert --summary 'Team Standup' --start '2026-01-20T09:00:00' --end '2026-01-20T09:30:00' --attendee alice@company.com --attendee bob@company.com`

