---
name: recipe-organize-drive-folder
description: "Create a Google Drive folder structure and move files into the right locations."
trigger:
  - keyword: organize drive
  - keyword: folder structure
  - keyword: organize files
---

# Organize Files into Google Drive Folders

Create a Google Drive folder structure and move files into the right locations.

## When to Use

Use this workflow when the user wants to create a project folder hierarchy, reorganize existing files, or set up a standard folder structure.

## Workflow

### 1. Create the root folder

```bash
gws drive files create \
  --json '{"name": "FOLDER_NAME", "mimeType": "application/vnd.google-apps.folder"}'
```

Capture the folder ID.

### 2. Create sub-folders

```bash
gws drive files create \
  --json '{"name": "SUB_FOLDER_NAME", "mimeType": "application/vnd.google-apps.folder", "parents": ["PARENT_FOLDER_ID"]}'
```

### 3. Move existing files (if applicable)

```bash
gws drive files update \
  --params '{"fileId": "FILE_ID", "addParents": "FOLDER_ID", "removeParents": "OLD_PARENT_ID"}'
```

### 4. Verify the structure

```bash
gws drive files list \
  --params '{"q": "'FOLDER_ID' in parents"}' \
  --fields "files(id,name,mimeType)" --format table
```

## Safety

- Moving files changes their location for all collaborators — confirm with the user
- The `removeParents` parameter is needed to move (not copy) files

## Tips

- Create a standard structure first (e.g., Documents, Assets, Archive), then move files
- Use `mimeType = 'application/vnd.google-apps.folder'` to filter for folders only
