---
description: >-
  Append a deal status update to a Google Sheets sales tracking spreadsheet. Trigger when user wants to append a deal status update to a google sheets sales tracking spreadsheet. Uses: sheets, drive.
name: recipe-log-deal-update
version: 1.0.0
---

# Log Deal Update to Sheet

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-sheets`, `gws-drive`

Append a deal status update to a Google Sheets sales tracking spreadsheet.

## Steps

1. Find the tracking sheet: `gws drive files list --params '{"q": "name = '\''Sales Pipeline'\'' and mimeType = '\''application/vnd.google-apps.spreadsheet'\''"}'`
2. Read current data: `gws sheets +read --spreadsheet SHEET_ID --range "Pipeline!A1:F"`
3. Append new row: `gws sheets +append --spreadsheet SHEET_ID --range 'Pipeline' --values '["2024-03-15", "Acme Corp", "Proposal Sent", "$50,000", "Q2", "jdoe"]'`

