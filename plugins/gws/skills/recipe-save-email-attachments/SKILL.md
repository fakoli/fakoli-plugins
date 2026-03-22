---
name: recipe-save-email-attachments
description: "Find Gmail messages with attachments and save them to a Google Drive folder."
trigger:
  - keyword: save attachments
  - keyword: email attachments
  - keyword: download attachments
version: 1.0.0
---

# Save Gmail Attachments to Google Drive

Find Gmail messages with attachments and save them to a Google Drive folder.

## When to Use

Use this workflow when the user wants to extract attachments from emails and store them in Drive — e.g., saving client documents, receipts, or reports.

## Workflow

### 1. Search for emails with attachments

```bash
gws gmail users messages list \
  --params '{"userId": "me", "q": "has:attachment ADDITIONAL_QUERY"}' \
  --fields "messages(id)" --format table
```

### 2. Get message details

For each message, retrieve attachment metadata:

```bash
gws gmail users messages get \
  --params '{"userId": "me", "id": "MESSAGE_ID"}' \
  --fields "payload.parts(filename,body,mimeType)"
```

### 3. Download attachments

```bash
gws gmail users messages attachments get \
  --params '{"userId": "me", "messageId": "MESSAGE_ID", "id": "ATTACHMENT_ID"}'
```

### 4. Upload to Drive

```bash
gws drive +upload --file ./ATTACHMENT_FILENAME --parent FOLDER_ID
```

### 5. Report results

Tell the user which files were saved and where.

## Tips

- Use specific search queries to narrow down: `from:client@example.com has:attachment after:2026/01/01`
- Attachment data is base64-encoded — you may need to decode before uploading
- For large batches, process one message at a time to avoid errors
