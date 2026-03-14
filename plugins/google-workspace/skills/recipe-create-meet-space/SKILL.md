---
description: >-
  Create a Google Meet meeting space and share the join link. Trigger when user wants to create a google meet meeting space and share the join link. Uses: meet, gmail.
name: recipe-create-meet-space
version: 1.0.0
---

# Create a Google Meet Conference

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-meet`, `gws-gmail`

Create a Google Meet meeting space and share the join link.

## Steps

1. Create meeting space: `gws meet spaces create --json '{"config": {"accessType": "OPEN"}}'`
2. Copy the meeting URI from the response
3. Email the link: `gws gmail +send --to team@company.com --subject 'Join the meeting' --body 'Join here: MEETING_URI'`

