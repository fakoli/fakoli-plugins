---
name: recipe-backup-sheet-as-csv
description: "Export a Google Sheets spreadsheet as a CSV file for local backup or processing."
trigger:
  - keyword: export spreadsheet csv
  - keyword: backup sheet
  - keyword: sheet to csv
version: 1.0.0
---

# Export a Google Sheet as CSV

Export a Google Sheets spreadsheet as a CSV file for local backup or processing.

## When to Use

Use this workflow when the user wants to back up spreadsheet data locally, export data for use in other tools, or create a CSV snapshot of a sheet.

## Workflow

### 1. Identify the spreadsheet

Ask the user for the spreadsheet name or ID. If they provide a name, search for it:

```bash
gws drive files list \
  --params '{"q": "name contains 'SHEET_NAME' and mimeType = 'application/vnd.google-apps.spreadsheet'"}' \
  --fields "files(id,name)" --format table
```

### 2. Check the sheet structure

Review what tabs and data ranges exist:

```bash
gws sheets spreadsheets get --params '{"spreadsheetId": "SHEET_ID"}' \
  --fields "sheets.properties(sheetId,title)"
```

### 3. Export as CSV

**Option A — Export via Drive API** (downloads the first sheet as CSV):

```bash
gws drive files export --params '{"fileId": "SHEET_ID", "mimeType": "text/csv"}'
```

**Option B — Read values directly** (more control over range and format):

```bash
gws sheets +read --spreadsheet SHEET_ID --range 'Sheet1' --format csv
```

### 4. Confirm with the user

Show the user the output path and a preview of the data.

## Tips

- Use Option B (`+read`) when you need a specific tab or range
- Use `--format csv` for machine-readable output, `--format table` for a quick visual check
- For large sheets, limit the range to avoid overwhelming output
