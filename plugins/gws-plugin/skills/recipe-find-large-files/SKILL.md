---
name: recipe-find-large-files
description: "Identify large Google Drive files consuming storage quota."
trigger:
  - keyword: find large files
  - keyword: storage usage
  - keyword: big files drive
version: 1.0.0
---

# Find Largest Files in Drive

Identify large Google Drive files consuming storage quota.

## When to Use

Use this workflow when the user wants to find large files eating their Drive storage, clean up space, or identify files to archive.

## Workflow

### 1. List files by size

```bash
gws drive files list \
  --params '{"orderBy": "quotaBytesUsed desc", "pageSize": 20, "fields": "files(id,name,size,mimeType,owners)"}' \
  --format table
```

### 2. Review with the user

Present the results and help identify files to:
- **Delete** — files no longer needed
- **Move** — files that should be in a shared drive (doesn't count against personal quota)
- **Keep** — files that are needed

### 3. Take action (if requested)

The user may want to delete or move files — confirm each action individually.

## Tips

- Google-native files (Docs, Sheets, Slides) don't count against quota — focus on uploaded files
- `size` field is in bytes — convert to MB/GB for readability
- Files in Trash still count against quota until permanently deleted
