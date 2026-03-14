---
description: >-
  Apply Gmail labels to matching messages and archive them to keep your inbox clean. Trigger when user wants to apply gmail labels to matching messages and archive them to keep your inbox clean. Uses: gmail.
name: recipe-label-and-archive-emails
version: 1.0.0
---

# Label and Archive Gmail Threads

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-gmail`

Apply Gmail labels to matching messages and archive them to keep your inbox clean.

## Steps

1. Search for matching emails: `gws gmail users messages list --params '{"userId": "me", "q": "from:notifications@service.com"}' --format table`
2. Apply a label: `gws gmail users messages modify --params '{"userId": "me", "id": "MESSAGE_ID"}' --json '{"addLabelIds": ["LABEL_ID"]}'`
3. Archive (remove from inbox): `gws gmail users messages modify --params '{"userId": "me", "id": "MESSAGE_ID"}' --json '{"removeLabelIds": ["INBOX"]}'`

