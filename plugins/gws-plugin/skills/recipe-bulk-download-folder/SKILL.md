---
name: recipe-bulk-download-folder
description: "List and download all files from a Google Drive folder."
trigger:
  - keyword: bulk download
  - keyword: download folder
  - keyword: download drive folder
version: 1.0.0
---

# Bulk Download Drive Folder

List and download all files from a Google Drive folder to the local filesystem.

## When to Use

Use this workflow when the user wants to download an entire folder from Google Drive, or export Google Docs/Sheets as local files.

## Workflow

### 1. Find the folder

Search for the folder by name:

```bash
gws drive files list \
  --params '{"q": "name = 'FOLDER_NAME' and mimeType = 'application/vnd.google-apps.folder'"}' \
  --fields "files(id,name)" --format table
```

### 2. List files in the folder

```bash
gws drive files list \
  --params '{"q": "'FOLDER_ID' in parents"}' \
  --fields "files(id,name,mimeType,size)" --format table
```

Show the user the file list and confirm they want to download all.

### 3. Download each file

For regular files (PDFs, images, etc.):

```bash
gws drive files get --params '{"fileId": "FILE_ID", "alt": "media"}' --output ./filename.ext
```

For Google Docs/Sheets/Slides (must export):

```bash
gws drive files export --params '{"fileId": "FILE_ID", "mimeType": "application/pdf"}' --output ./document.pdf
```

### 4. Report results

Tell the user which files were downloaded and where they are.

## Tips

- Google-native files (Docs, Sheets, Slides) must be exported — they can't be downloaded directly
- Common export MIME types: `application/pdf`, `text/csv`, `text/plain`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Use `--fields` to keep the file listing compact
