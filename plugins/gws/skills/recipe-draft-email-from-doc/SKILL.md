---
name: recipe-draft-email-from-doc
description: "Read content from a Google Doc and use it as the body of a Gmail message."
trigger:
  - keyword: email from doc
  - keyword: doc to email
  - keyword: draft from document
version: 1.0.0
---

# Draft a Gmail Message from a Google Doc

Read content from a Google Doc and use it as the body of a Gmail message.

## When to Use

Use this workflow when the user has drafted content in a Google Doc (e.g., a newsletter, announcement, update) and wants to send it as an email.

## Workflow

### 1. Get the document content

```bash
gws docs documents get --params '{"documentId": "DOC_ID"}' \
  --fields "body,title"
```

Extract the text content from the response body.

### 2. Preview the email

Show the user the extracted content and ask them to confirm:
- **To:** recipient(s)
- **Subject:** (suggest using the doc title)
- **Body:** (the extracted content)

### 3. Send the email

Use `--dry-run` first:

```bash
gws gmail +send \
  --to recipient@example.com \
  --subject 'SUBJECT' \
  --body 'CONTENT_FROM_DOC' \
  --dry-run
```

Confirm with the user, then send.

## Safety

- Always `--dry-run` and confirm before sending
- Verify the recipient list

## Tips

- For HTML-formatted emails, use `--html` instead of `--body`
- The Doc API returns structured content — you may need to flatten it into plain text
