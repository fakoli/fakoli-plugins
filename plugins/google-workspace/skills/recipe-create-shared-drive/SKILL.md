---
description: >-
  Create a Google Shared Drive and add members with appropriate roles. Trigger when user wants to create a google shared drive and add members with appropriate roles. Uses: drive.
name: recipe-create-shared-drive
version: 1.0.0
---

# Create and Configure a Shared Drive

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-drive`

Create a Google Shared Drive and add members with appropriate roles.

## Steps

1. Create shared drive: `gws drive drives create --params '{"requestId": "unique-id-123"}' --json '{"name": "Project X"}'`
2. Add a member: `gws drive permissions create --params '{"fileId": "DRIVE_ID", "supportsAllDrives": true}' --json '{"role": "writer", "type": "user", "emailAddress": "member@company.com"}'`
3. List members: `gws drive permissions list --params '{"fileId": "DRIVE_ID", "supportsAllDrives": true}'`

