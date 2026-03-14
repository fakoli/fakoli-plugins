---
description: >-
  Find Gmail messages with a specific label and forward them to another address. Trigger when user wants to find gmail messages with a specific label and forward them to another address. Uses: gmail.
name: recipe-forward-labeled-emails
version: 1.0.0
---

# Forward Labeled Gmail Messages

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-gmail`

Find Gmail messages with a specific label and forward them to another address.

## Steps

1. Find labeled messages: `gws gmail users messages list --params '{"userId": "me", "q": "label:needs-review"}' --format table`
2. Get message content: `gws gmail users messages get --params '{"userId": "me", "id": "MSG_ID"}'`
3. Forward via new email: `gws gmail +send --to manager@company.com --subject 'FW: [Original Subject]' --body 'Forwarding for your review:

[Original Message Body]'`

