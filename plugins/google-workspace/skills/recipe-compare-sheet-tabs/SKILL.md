---
description: >-
  Read data from two tabs in a Google Sheet to compare and identify differences. Trigger when user wants to read data from two tabs in a google sheet to compare and identify differences. Uses: sheets.
name: recipe-compare-sheet-tabs
version: 1.0.0
---

# Compare Two Google Sheets Tabs

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-sheets`

Read data from two tabs in a Google Sheet to compare and identify differences.

## Steps

1. Read the first tab: `gws sheets +read --spreadsheet SHEET_ID --range "January!A1:D"`
2. Read the second tab: `gws sheets +read --spreadsheet SHEET_ID --range "February!A1:D"`
3. Compare the data and identify changes

