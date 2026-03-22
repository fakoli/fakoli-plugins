---
description: Read, write, and append data to Google Sheets spreadsheets
argument-hint: "<read|append|create> [spreadsheet-id] [range] [values]"
allowed-tools: [Bash]
---

# /gws-sheets

Manage Google Sheets spreadsheets using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine the operation.

### Common Operations

**Read spreadsheet data:**
```bash
gws sheets +read --spreadsheet SPREADSHEET_ID --range "Sheet1!A1:D10"
```

**Read entire sheet:**
```bash
gws sheets +read --spreadsheet SPREADSHEET_ID --range Sheet1
```

**Append a row:**
```bash
gws sheets +append --spreadsheet SPREADSHEET_ID --values "val1,val2,val3"
```

**Append multiple rows (JSON):**
```bash
gws sheets +append --spreadsheet SPREADSHEET_ID --json-values '[["a","b"],["c","d"]]'
```

**Create a new spreadsheet:**
```bash
gws sheets spreadsheets create --json '{"properties": {"title": "My Sheet"}}'
```

**Read with table output:**
```bash
gws sheets +read --spreadsheet SPREADSHEET_ID --range "Sheet1!A1:D10" --format table
```

## URL Handling

Extract spreadsheet ID from URLs:
- `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit` → `SPREADSHEET_ID`

## Range Notation

- `Sheet1!A1:D10` — specific range
- `Sheet1` — entire sheet
- `A1:D10` — range on first sheet
- Use double quotes around ranges with `!` in zsh

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
- If spreadsheet not found, suggest searching Drive: `gws drive files list --params '{"q": "mimeType=\"application/vnd.google-apps.spreadsheet\"", "pageSize": 10}' --format table`
