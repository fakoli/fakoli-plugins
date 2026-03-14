---
description: >-
  Duplicate a Google Sheets template tab for a new month of tracking. Trigger when user wants to duplicate a google sheets template tab for a new month of tracking. Uses: sheets.
name: recipe-copy-sheet-for-new-month
version: 1.0.0
---

# Copy a Google Sheet for a New Month

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-sheets`

Duplicate a Google Sheets template tab for a new month of tracking.

## Steps

1. Get spreadsheet details: `gws sheets spreadsheets get --params '{"spreadsheetId": "SHEET_ID"}'`
2. Copy the template sheet: `gws sheets spreadsheets sheets copyTo --params '{"spreadsheetId": "SHEET_ID", "sheetId": 0}' --json '{"destinationSpreadsheetId": "SHEET_ID"}'`
3. Rename the new tab: `gws sheets spreadsheets batchUpdate --params '{"spreadsheetId": "SHEET_ID"}' --json '{"requests": [{"updateSheetProperties": {"properties": {"sheetId": 123, "title": "February 2025"}, "fields": "title"}}]}'`

