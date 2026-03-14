---
description: >-
  Identify large Google Drive files consuming storage quota. Trigger when user wants to identify large google drive files consuming storage quota. Uses: drive.
name: recipe-find-large-files
version: 1.0.0
---

# Find Largest Files in Drive

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-drive`

Identify large Google Drive files consuming storage quota.

## Steps

1. List files sorted by size: `gws drive files list --params '{"orderBy": "quotaBytesUsed desc", "pageSize": 20, "fields": "files(id,name,size,mimeType,owners)"}' --format table`
2. Review the output and identify files to archive or move

