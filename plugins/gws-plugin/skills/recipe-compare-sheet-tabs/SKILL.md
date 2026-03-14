---
name: recipe-compare-sheet-tabs
description: "Read data from two tabs in a Google Sheet to compare and identify differences."
trigger:
  - keyword: compare sheets
  - keyword: compare tabs
  - keyword: diff spreadsheet
version: 1.0.0
---

# Compare Two Google Sheets Tabs

Read data from two tabs in a Google Sheet to compare and identify differences.

## When to Use

Use this workflow when the user wants to compare data across two tabs (e.g., month-over-month, before/after, or version comparison).

## Workflow

### 1. Identify the spreadsheet and tabs

Ask the user for the spreadsheet ID and the two tab names to compare.

### 2. Read both tabs

```bash
gws sheets +read --spreadsheet SHEET_ID --range "TAB_1!A1:Z"
```

```bash
gws sheets +read --spreadsheet SHEET_ID --range "TAB_2!A1:Z"
```

### 3. Compare and report

Analyze the data from both tabs and present:
- Rows that exist in one tab but not the other
- Values that changed between tabs
- Summary statistics (row counts, totals, etc.)

## Tips

- Limit the range (e.g., `A1:D50`) if the sheet is large to avoid overwhelming output
- Use `--format json` for programmatic comparison
- If tabs have different structures, note the column differences for the user
