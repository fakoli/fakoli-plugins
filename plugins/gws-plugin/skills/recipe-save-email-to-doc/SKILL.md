---
name: recipe-save-email-to-doc
description: "Save a Gmail message body into a Google Doc for archival or reference."
trigger:
  - keyword: save email to doc
  - keyword: email to document
  - keyword: archive email
version: 1.0.0
---

# Save a Gmail Message to Google Docs

Save a Gmail message body into a Google Doc for archival or reference.

## When to Use

Use this workflow when the user wants to preserve an email as a permanent document — for record-keeping, compliance, or easy sharing.

## Workflow

### 1. Find the message

```bash
gws gmail users messages list \
  --params '{"userId": "me", "q": "SEARCH_QUERY"}' \
  --fields "messages(id)" --format table
```

### 2. Get the message content

```bash
gws gmail users messages get --params '{"userId": "me", "id": "MSG_ID"}'
```

Extract the subject, sender, date, and body text.

### 3. Create the document

```bash
gws docs documents create --json '{"title": "Saved Email - SUBJECT"}'
```

### 4. Write the email content

```bash
gws docs +write --document-id DOC_ID \
  --text 'From: SENDER\nDate: DATE\nSubject: SUBJECT\n\nBODY_TEXT'
```

### 5. Provide the link

Give the user: `https://docs.google.com/document/d/DOC_ID`

## Tips

- Include metadata (From, Date, Subject) at the top of the doc for context
- For HTML emails, extract the plain text version to avoid formatting issues
- Share the doc if others need access: use `gws drive permissions create`
