---
description: >-
  Subscribe to change notifications on a Google Drive file or folder. Trigger when user wants to subscribe to change notifications on a google drive file or folder. Uses: events.
name: recipe-watch-drive-changes
version: 1.0.0
---

# Watch for Drive Changes

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-events`

Subscribe to change notifications on a Google Drive file or folder.

## Steps

1. Create subscription: `gws events subscriptions create --json '{"targetResource": "//drive.googleapis.com/drives/DRIVE_ID", "eventTypes": ["google.workspace.drive.file.v1.updated"], "notificationEndpoint": {"pubsubTopic": "projects/PROJECT/topics/TOPIC"}, "payloadOptions": {"includeResource": true}}'`
2. List active subscriptions: `gws events subscriptions list`
3. Renew before expiry: `gws events +renew --subscription SUBSCRIPTION_ID`

