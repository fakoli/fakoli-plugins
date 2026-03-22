---
name: recipe-create-doc-from-template
description: "Copy a Google Docs template, fill in content, and share with collaborators."
trigger:
  - keyword: doc from template
  - keyword: copy template
  - keyword: document template
version: 1.0.0
---

# Create a Google Doc from a Template

Copy a Google Docs template, fill in content, and share with collaborators.

## When to Use

Use this workflow when the user wants to create a new document based on an existing template (e.g., project briefs, meeting notes, proposals).

## Workflow

### 1. Find the template

Help the user locate the template document:

```bash
gws drive files list \
  --params '{"q": "name contains 'TEMPLATE_NAME' and mimeType = 'application/vnd.google-apps.document'"}' \
  --fields "files(id,name)" --format table
```

### 2. Copy the template

```bash
gws drive files copy \
  --params '{"fileId": "TEMPLATE_DOC_ID"}' \
  --json '{"name": "NEW_DOCUMENT_NAME"}'
```

Capture the new document ID from the response.

### 3. Fill in content

```bash
gws docs +write --document-id NEW_DOC_ID --text 'CONTENT_HERE'
```

### 4. Share with collaborators

Use `--dry-run` first:

```bash
gws drive permissions create \
  --params '{"fileId": "NEW_DOC_ID"}' \
  --json '{"role": "writer", "type": "user", "emailAddress": "collaborator@company.com"}' \
  --dry-run
```

Confirm, then execute.

### 5. Provide the link

Give the user the document URL: `https://docs.google.com/document/d/NEW_DOC_ID`

## Tips

- Copy preserves all formatting from the template
- Use `"role": "commenter"` for review-only access
