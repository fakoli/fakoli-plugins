---
description: >-
  Export a Google Sheets spreadsheet as a CSV file for local backup or processing. Trigger when user wants to export a google sheets spreadsheet as a csv file for local backup or processing. Uses: sheets,
  drive.
name: recipe-backup-sheet-as-csv
version: 1.0.0
---

# Export a Google Sheet as CSV

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-sheets`, `gws-drive`

Export a Google Sheets spreadsheet as a CSV file for local backup or processing.

## Steps

1. Get spreadsheet details: `gws sheets spreadsheets get --params '{"spreadsheetId": "SHEET_ID"}'`
2. Export as CSV: `gws drive files export --params '{"fileId": "SHEET_ID", "mimeType": "text/csv"}'`
3. Or read values directly: `gws sheets +read --spreadsheet SHEET_ID --range 'Sheet1' --format csv`

