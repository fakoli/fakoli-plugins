---
description: >-
  Create a Google Drive folder structure and move files into the right locations. Trigger when user wants to create a google drive folder structure and move files into the right locations. Uses: drive.
name: recipe-organize-drive-folder
version: 1.0.0
---

# Organize Files into Google Drive Folders

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-drive`

Create a Google Drive folder structure and move files into the right locations.

## Steps

1. Create a project folder: `gws drive files create --json '{"name": "Q2 Project", "mimeType": "application/vnd.google-apps.folder"}'`
2. Create sub-folders: `gws drive files create --json '{"name": "Documents", "mimeType": "application/vnd.google-apps.folder", "parents": ["PARENT_FOLDER_ID"]}'`
3. Move existing files into folder: `gws drive files update --params '{"fileId": "FILE_ID", "addParents": "FOLDER_ID", "removeParents": "OLD_PARENT_ID"}'`
4. Verify structure: `gws drive files list --params '{"q": "FOLDER_ID in parents"}' --format table`

