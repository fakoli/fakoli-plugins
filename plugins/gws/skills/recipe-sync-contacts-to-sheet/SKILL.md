---
name: recipe-sync-contacts-to-sheet
description: "Export Google Contacts directory to a Google Sheets spreadsheet."
trigger:
  - keyword: sync contacts
  - keyword: export contacts
  - keyword: contacts to sheet
version: 1.0.0
---

# Export Google Contacts to Sheets

Export Google Contacts directory to a Google Sheets spreadsheet.

## When to Use

Use this workflow when the user wants to export their organization's contact directory to a spreadsheet for reporting, mail merge, or backup.

## Workflow

### 1. List contacts from the directory

```bash
gws people people listDirectoryPeople \
  --params '{"readMask": "names,emailAddresses,phoneNumbers", "sources": ["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"], "pageSize": 100}' \
  --format json
```

### 2. Prepare the spreadsheet

Find an existing sheet or create headers in a new one:

```bash
gws sheets +append --spreadsheet SHEET_ID --range 'Contacts' \
  --values '["Name", "Email", "Phone"]'
```

### 3. Append each contact

For each contact from the directory response:

```bash
gws sheets +append --spreadsheet SHEET_ID --range 'Contacts' \
  --values '["DISPLAY_NAME", "EMAIL", "PHONE"]'
```

### 4. Report results

Tell the user how many contacts were exported and provide the spreadsheet link.

## Tips

- Use `--page-all` on the contacts list if there are more than 100 contacts
- The `readMask` controls which fields are returned — add `organizations`, `titles`, etc. as needed
- For personal contacts (not directory), use `people connections list` instead
