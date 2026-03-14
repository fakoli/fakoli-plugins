---
name: recipe-log-deal-update
description: "Append a deal status update to a Google Sheets sales tracking spreadsheet."
trigger:
  - keyword: log deal
  - keyword: deal update
  - keyword: sales log
version: 1.0.0
---

# Log Deal Update to Sheet

Append a deal status update to a Google Sheets sales tracking spreadsheet.

## When to Use

Use this workflow when the user wants to log a deal status change, update a sales pipeline tracker, or record a customer interaction.

## Workflow

### 1. Find the tracking sheet

```bash
gws drive files list \
  --params '{"q": "name contains 'SHEET_NAME' and mimeType = 'application/vnd.google-apps.spreadsheet'"}' \
  --fields "files(id,name)" --format table
```

### 2. Review current data

```bash
gws sheets +read --spreadsheet SHEET_ID --range "SHEET_TAB!A1:F" --format table
```

Show the user the current state of the pipeline.

### 3. Append the update

Gather the update details from the user and append:

```bash
gws sheets +append --spreadsheet SHEET_ID --range 'SHEET_TAB' \
  --values '["DATE", "COMPANY", "STATUS", "AMOUNT", "QUARTER", "OWNER"]'
```

### 4. Confirm

Show the user the updated row.

## Tips

- Use today's date in ISO format for consistency
- Match the column order to the existing sheet headers
- If the sheet has formulas in certain columns, skip those in the append
