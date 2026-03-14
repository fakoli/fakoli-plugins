---
name: recipe-share-folder-with-team
description: "Share a Google Drive folder and all its contents with a list of collaborators."
trigger:
  - keyword: share folder
  - keyword: team folder access
  - keyword: folder permissions
---

# Share a Google Drive Folder with a Team

Share a Google Drive folder and all its contents with a list of collaborators.

## When to Use

Use this workflow when the user wants to give team members access to a project folder — folder-level sharing cascades to all files inside.

## Workflow

### 1. Find the folder

```bash
gws drive files list \
  --params '{"q": "name = 'FOLDER_NAME' and mimeType = 'application/vnd.google-apps.folder'"}' \
  --fields "files(id,name)" --format table
```

### 2. Add collaborators

For each person, ask the user what role to assign and use `--dry-run`:

```bash
gws drive permissions create \
  --params '{"fileId": "FOLDER_ID"}' \
  --json '{"role": "writer", "type": "user", "emailAddress": "colleague@company.com"}' \
  --dry-run
```

Confirm, then execute for each collaborator.

### 3. Verify permissions

```bash
gws drive permissions list --params '{"fileId": "FOLDER_ID"}' --format table
```

## Safety

- Always `--dry-run` before granting permissions
- Folder-level sharing applies to ALL current and future files in the folder
- Confirm with the user that they want cascade sharing

## Tips

- Roles: `reader`, `commenter`, `writer`, `fileOrganizer` (can organize), `organizer` (full control)
- Use `"type": "group"` for Google Groups instead of individual users
