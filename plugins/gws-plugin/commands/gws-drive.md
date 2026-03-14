---
description: Search, upload, download, and share Google Drive files and folders
argument-hint: "<search query | upload path | file-id>"
allowed-tools: [Bash]
---

# /gws-drive

Manage Google Drive files using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine what the user wants to do with Drive.

### Common Operations

**Search files:**
```bash
gws drive files list --params '{"q": "name contains \"QUERY\"", "pageSize": 10}' --fields "files(id,name,mimeType,modifiedTime)" --format table
```

**Upload a file:**
```bash
gws drive +upload ./local-file.pdf
```

**Upload to a specific folder:**
```bash
gws drive +upload ./file.pdf --parent FOLDER_ID
```

**Download a file:**
```bash
gws drive files get --params '{"fileId": "FILE_ID", "alt": "media"}' --output ./local-file.pdf
```

**Create a folder:**
```bash
gws drive files create --json '{"name": "Folder Name", "mimeType": "application/vnd.google-apps.folder"}'
```

**Share a file:**
```bash
gws drive permissions create --params '{"fileId": "FILE_ID"}' --json '{"role": "reader", "type": "user", "emailAddress": "user@example.com"}'
```

**List folder contents:**
```bash
gws drive files list --params '{"q": "\"FOLDER_ID\" in parents", "pageSize": 20}' --fields "files(id,name,mimeType)" --format table
```

## URL Handling

If the user provides a Google Drive URL, extract the file ID from between `/d/` and the next `/`:
- `https://drive.google.com/file/d/FILE_ID/view` → `FILE_ID`
- `https://docs.google.com/document/d/DOC_ID/edit` → `DOC_ID`

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
- Exit code 1: API error. Check the error message for details.

## Tips

- Always use `--fields` to limit response size and protect context window.
- Use `--format table` for display, `--format json` for programmatic use.
- Use `--dry-run` before destructive operations (delete, update permissions).
- For zsh: use double quotes for queries containing `!`.
