---
name: recipe-create-shared-drive
description: "Create a Google Shared Drive and add members with appropriate roles."
trigger:
  - keyword: shared drive
  - keyword: create team drive
  - keyword: new shared drive
version: 1.0.0
---

# Create and Configure a Shared Drive

Create a Google Shared Drive and add members with appropriate roles.

## When to Use

Use this workflow when the user needs to set up a shared team drive with specific member access.

## Workflow

### 1. Create the shared drive

```bash
gws drive drives create \
  --params '{"requestId": "UNIQUE_REQUEST_ID"}' \
  --json '{"name": "DRIVE_NAME"}'
```

Capture the drive ID from the response. Generate a unique `requestId` (e.g., UUID).

### 2. Add members

For each member, confirm role (organizer, writer, commenter, reader) with the user:

```bash
gws drive permissions create \
  --params '{"fileId": "DRIVE_ID", "supportsAllDrives": true}' \
  --json '{"role": "writer", "type": "user", "emailAddress": "member@company.com"}' \
  --dry-run
```

Confirm, then execute.

### 3. Verify members

```bash
gws drive permissions list \
  --params '{"fileId": "DRIVE_ID", "supportsAllDrives": true}' --format table
```

## Safety

- Always `--dry-run` before adding permissions
- Use `"supportsAllDrives": true` for all Shared Drive operations

## Tips

- Shared Drive roles: `organizer`, `fileOrganizer`, `writer`, `commenter`, `reader`
- The `requestId` must be unique per request — use a UUID or timestamp
