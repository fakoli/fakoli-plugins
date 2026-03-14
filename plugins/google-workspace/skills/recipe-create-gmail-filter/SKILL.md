---
description: >-
  Create a Gmail filter to automatically label, star, or categorize incoming messages. Trigger when user wants to create a gmail filter to automatically label, star, or categorize incoming messages. Uses:
  gmail.
name: recipe-create-gmail-filter
version: 1.0.0
---

# Create a Gmail Filter

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-gmail`

Create a Gmail filter to automatically label, star, or categorize incoming messages.

## Steps

1. List existing labels: `gws gmail users labels list --params '{"userId": "me"}' --format table`
2. Create a new label: `gws gmail users labels create --params '{"userId": "me"}' --json '{"name": "Receipts"}'`
3. Create a filter: `gws gmail users settings filters create --params '{"userId": "me"}' --json '{"criteria": {"from": "receipts@example.com"}, "action": {"addLabelIds": ["LABEL_ID"], "removeLabelIds": ["INBOX"]}}'`
4. Verify filter: `gws gmail users settings filters list --params '{"userId": "me"}' --format table`

