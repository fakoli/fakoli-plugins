---
description: >-
  Export Google Contacts directory to a Google Sheets spreadsheet. Trigger when user wants to export google contacts directory to a google sheets spreadsheet. Uses: people, sheets.
name: recipe-sync-contacts-to-sheet
version: 1.0.0
---

# Export Google Contacts to Sheets

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-people`, `gws-sheets`

Export Google Contacts directory to a Google Sheets spreadsheet.

## Steps

1. List contacts: `gws people people listDirectoryPeople --params '{"readMask": "names,emailAddresses,phoneNumbers", "sources": ["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"], "pageSize": 100}' --format json`
2. Create a sheet: `gws sheets +append --spreadsheet SHEET_ID --range 'Contacts' --values '["Name", "Email", "Phone"]'`
3. Append each contact row: `gws sheets +append --spreadsheet SHEET_ID --range 'Contacts' --values '["Jane Doe", "jane@company.com", "+1-555-0100"]'`

