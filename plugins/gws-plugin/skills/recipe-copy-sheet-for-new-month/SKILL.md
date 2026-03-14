---
name: recipe-copy-sheet-for-new-month
description: "Duplicate a Google Sheets template tab for a new month of tracking."
trigger:
  - keyword: copy sheet tab
  - keyword: new month sheet
  - keyword: duplicate tab
---

# Copy a Google Sheet Tab for a New Month

Duplicate a Google Sheets template tab for a new month of tracking.

## When to Use

Use this workflow when the user has a monthly tracking sheet and wants to create a new tab for the next month based on an existing template tab.

## Workflow

### 1. Get the spreadsheet structure

```bash
gws sheets spreadsheets get --params '{"spreadsheetId": "SHEET_ID"}' \
  --fields "sheets.properties(sheetId,title)"
```

Identify the template tab's `sheetId` from the output.

### 2. Copy the template tab

```bash
gws sheets spreadsheets sheets copyTo \
  --params '{"spreadsheetId": "SHEET_ID", "sheetId": TEMPLATE_SHEET_ID}' \
  --json '{"destinationSpreadsheetId": "SHEET_ID"}'
```

Note the new sheet ID from the response.

### 3. Rename the new tab

Ask the user what to name it (e.g., "March 2026"):

```bash
gws sheets spreadsheets batchUpdate \
  --params '{"spreadsheetId": "SHEET_ID"}' \
  --json '{"requests": [{"updateSheetProperties": {"properties": {"sheetId": NEW_SHEET_ID, "title": "NEW_TAB_NAME"}, "fields": "title"}}]}'
```

### 4. Confirm

Tell the user the new tab was created and named.

## Tips

- The copied tab will include all formatting, formulas, and conditional formatting from the template
- If the template has formulas referencing other tabs, verify they still work in the copy
