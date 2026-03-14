---
name: recipe-create-expense-tracker
description: "Set up a Google Sheets spreadsheet for tracking expenses with headers and initial entries."
trigger:
  - keyword: expense tracker
  - keyword: track expenses
  - keyword: expense sheet
---

# Create a Google Sheets Expense Tracker

Set up a Google Sheets spreadsheet for tracking expenses with headers and initial entries.

## When to Use

Use this workflow when the user wants to create a new expense tracking spreadsheet with a standard structure.

## Workflow

### 1. Create the spreadsheet

```bash
gws drive files create --json '{"name": "TRACKER_NAME", "mimeType": "application/vnd.google-apps.spreadsheet"}'
```

Capture the spreadsheet ID from the response.

### 2. Add headers

```bash
gws sheets +append --spreadsheet SHEET_ID --range 'Sheet1' \
  --values '["Date", "Category", "Description", "Amount"]'
```

### 3. Optionally add sample entries

If the user wants example data:

```bash
gws sheets +append --spreadsheet SHEET_ID --range 'Sheet1' \
  --values '["2026-03-14", "Travel", "Flight to NYC", "450.00"]'
```

### 4. Share with others (optional)

If the user wants to share:

```bash
gws drive permissions create \
  --params '{"fileId": "SHEET_ID"}' \
  --json '{"role": "reader", "type": "user", "emailAddress": "manager@company.com"}' \
  --dry-run
```

Confirm, then execute.

### 5. Provide the link

Give the user: `https://docs.google.com/spreadsheets/d/SHEET_ID`

## Tips

- Customize headers based on the user's needs (add "Project", "Receipt URL", etc.)
- Suggest using Data Validation in Sheets for the Category column
