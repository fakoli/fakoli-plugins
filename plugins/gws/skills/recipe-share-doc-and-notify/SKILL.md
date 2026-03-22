---
name: recipe-share-doc-and-notify
description: "Share a Google Docs document with edit access and email collaborators the link."
trigger:
  - keyword: share doc
  - keyword: share and notify
  - keyword: share document
version: 1.0.0
---

# Share a Google Doc and Notify Collaborators

Share a Google Docs document with edit access and email collaborators the link.

## When to Use

Use this workflow when the user wants to share a document and make sure the recipients know about it via email.

## Workflow

### 1. Find the document

```bash
gws drive files list \
  --params '{"q": "name contains 'DOC_NAME' and mimeType = 'application/vnd.google-apps.document'"}' \
  --fields "files(id,name,webViewLink)" --format table
```

### 2. Grant access

Ask the user what access level to grant:

```bash
gws drive permissions create \
  --params '{"fileId": "DOC_ID"}' \
  --json '{"role": "writer", "type": "user", "emailAddress": "reviewer@company.com"}' \
  --dry-run
```

Confirm, then execute.

### 3. Send notification email

```bash
gws gmail +send \
  --to reviewer@company.com \
  --subject 'Please review: DOC_NAME' \
  --body 'I have shared DOC_NAME with you: DOC_LINK' \
  --dry-run
```

Confirm, then send.

## Safety

- Always `--dry-run` for both permission and email
- Use the minimum necessary access level (reader vs writer)

## Tips

- Use `webViewLink` from the file listing as the shareable URL
- `"role": "commenter"` is good for review workflows
