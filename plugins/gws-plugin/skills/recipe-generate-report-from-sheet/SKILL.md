---
name: recipe-generate-report-from-sheet
description: "Read data from a Google Sheet and create a formatted Google Docs report."
trigger:
  - keyword: report from sheet
  - keyword: generate report
  - keyword: sheet to doc
---

# Generate a Google Docs Report from Sheet Data

Read data from a Google Sheet and create a formatted Google Docs report.

## When to Use

Use this workflow when the user wants to turn spreadsheet data into a narrative report — e.g., sales summaries, project status, financial reports.

## Workflow

### 1. Read the source data

```bash
gws sheets +read --spreadsheet SHEET_ID --range "SHEET_NAME!A1:Z" --format table
```

Review the data with the user and understand what they want in the report.

### 2. Create the report document

```bash
gws docs documents create --json '{"title": "REPORT_TITLE"}'
```

Capture the document ID.

### 3. Write the report

Compose the report content from the data and write it:

```bash
gws docs +write --document-id DOC_ID --text 'FORMATTED_REPORT_CONTENT'
```

### 4. Share with stakeholders (optional)

```bash
gws drive permissions create \
  --params '{"fileId": "DOC_ID"}' \
  --json '{"role": "reader", "type": "user", "emailAddress": "stakeholder@company.com"}' \
  --dry-run
```

### 5. Provide the link

Give the user: `https://docs.google.com/document/d/DOC_ID`

## Tips

- Structure the report with markdown-style headings — `gws docs +write` handles formatting
- Summarize data rather than dumping raw numbers — add context and analysis
- Use `--fields` when reading the sheet to limit data to relevant columns
