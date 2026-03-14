---
description: >-
  Save a Gmail message body into a Google Doc for archival or reference. Trigger when user wants to save a gmail message body into a google doc for archival or reference. Uses: gmail, docs.
name: recipe-save-email-to-doc
version: 1.0.0
---

# Save a Gmail Message to Google Docs

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-gmail`, `gws-docs`

Save a Gmail message body into a Google Doc for archival or reference.

## Steps

1. Find the message: `gws gmail users messages list --params '{"userId": "me", "q": "subject:important from:boss@company.com"}' --format table`
2. Get message content: `gws gmail users messages get --params '{"userId": "me", "id": "MSG_ID"}'`
3. Create a doc with the content: `gws docs documents create --json '{"title": "Saved Email - Important Update"}'`
4. Write the email body: `gws docs +write --document-id DOC_ID --text 'From: boss@company.com
Subject: Important Update

[EMAIL BODY]'`

