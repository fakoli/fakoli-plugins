---
description: >-
  Set up a Google Sheets spreadsheet for tracking expenses with headers and initial entries. Trigger when user wants to set up a google sheets spreadsheet for tracking expenses with headers and initial
  entries. Uses: sheets, drive.
name: recipe-create-expense-tracker
version: 1.0.0
---

# Create a Google Sheets Expense Tracker

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-sheets`, `gws-drive`

Set up a Google Sheets spreadsheet for tracking expenses with headers and initial entries.

## Steps

1. Create spreadsheet: `gws drive files create --json '{"name": "Expense Tracker 2025", "mimeType": "application/vnd.google-apps.spreadsheet"}'`
2. Add headers: `gws sheets +append --spreadsheet SHEET_ID --range 'Sheet1' --values '["Date", "Category", "Description", "Amount"]'`
3. Add first entry: `gws sheets +append --spreadsheet SHEET_ID --range 'Sheet1' --values '["2025-01-15", "Travel", "Flight to NYC", "450.00"]'`
4. Share with manager: `gws drive permissions create --params '{"fileId": "SHEET_ID"}' --json '{"role": "reader", "type": "user", "emailAddress": "manager@company.com"}'`

