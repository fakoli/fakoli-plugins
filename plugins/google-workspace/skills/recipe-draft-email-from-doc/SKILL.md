---
description: >-
  Read content from a Google Doc and use it as the body of a Gmail message. Trigger when user wants to read content from a google doc and use it as the body of a gmail message. Uses: docs, gmail.
name: recipe-draft-email-from-doc
version: 1.0.0
---

# Draft a Gmail Message from a Google Doc

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-docs`, `gws-gmail`

Read content from a Google Doc and use it as the body of a Gmail message.

## Steps

1. Get the document content: `gws docs documents get --params '{"documentId": "DOC_ID"}'`
2. Copy the text from the body content
3. Send the email: `gws gmail +send --to recipient@example.com --subject 'Newsletter Update' --body 'CONTENT_FROM_DOC'`

