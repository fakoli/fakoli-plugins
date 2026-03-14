---
name: recipe-watch-drive-changes
description: "Subscribe to change notifications on a Google Drive file or folder."
trigger:
  - keyword: watch drive
  - keyword: drive notifications
  - keyword: file change alerts
---

# Watch for Drive Changes

Subscribe to change notifications on a Google Drive file or folder using Workspace Events.

## When to Use

Use this workflow when the user wants to be notified when files in a Drive folder are created, updated, or deleted — useful for monitoring shared folders.

## Workflow

### 1. Prerequisites

Ensure the user has full scopes and a GCP project with Pub/Sub:

```bash
gws auth status
```

If missing pubsub scope: `gws auth login --full`

### 2. Create the subscription

```bash
gws events subscriptions create \
  --json '{"targetResource": "//drive.googleapis.com/drives/DRIVE_ID", "eventTypes": ["google.workspace.drive.file.v1.updated"], "notificationEndpoint": {"pubsubTopic": "projects/PROJECT/topics/TOPIC"}, "payloadOptions": {"includeResource": true}}'
```

### 3. Verify the subscription

```bash
gws events subscriptions list --format table
```

### 4. Set up renewal reminders

Subscriptions expire — renew before expiry:

```bash
gws events +renew --subscription SUBSCRIPTION_ID
```

## Safety

- This creates a real-time notification pipeline — confirm the user understands the Pub/Sub costs
- Verify the GCP project and topic are correct

## Tips

- Event types: `google.workspace.drive.file.v1.created`, `.updated`, `.trashed`
- Use `"includeResource": true` to get file metadata in notifications
- Subscriptions typically last 7 days before needing renewal
