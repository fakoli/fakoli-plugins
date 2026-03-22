---
name: recipe-email-drive-link
description: "Share a Google Drive file and email the link with a message to recipients."
trigger:
  - keyword: email drive link
  - keyword: share file link
  - keyword: send file link
version: 1.0.0
---

# Email a Google Drive File Link

Share a Google Drive file and email the link with a message to recipients.

## When to Use

Use this workflow when the user wants to share a file from Drive by granting access and sending the link via email in one step.

## Workflow

### 1. Find the file

```bash
gws drive files list \
  --params '{"q": "name contains 'FILE_NAME'"}' \
  --fields "files(id,name,webViewLink)" --format table
```

### 2. Grant access

Ask the user what role to grant (reader, writer, commenter):

```bash
gws drive permissions create \
  --params '{"fileId": "FILE_ID"}' \
  --json '{"role": "reader", "type": "user", "emailAddress": "recipient@example.com"}' \
  --dry-run
```

Confirm, then execute.

### 3. Send the email with the link

```bash
gws gmail +send \
  --to recipient@example.com \
  --subject 'SUBJECT' \
  --body 'MESSAGE_WITH_LINK' \
  --dry-run
```

Confirm, then send.

## Safety

- Always `--dry-run` for both the permission grant and email send
- Confirm the access level — don't grant `writer` when `reader` is sufficient

## Tips

- The `webViewLink` from the file listing is the shareable URL
- Use `"type": "anyone"` with `"role": "reader"` for "anyone with the link" sharing
