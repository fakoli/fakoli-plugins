---
description: Upload a file to Google Drive
argument-hint: "[file-path] [folder-id]"
allowed-tools: Bash(gws:*)
---

# /upload

Upload a file to Google Drive using the `gws` CLI.

## Instructions

1. Parse the argument for the file path and optional folder ID.

2. Verify the file exists locally.

3. Run with `--dry-run` first:
   ```bash
   gws drive +upload <file-path> --dry-run
   ```
   If a folder ID was provided, add `--parent <FOLDER_ID>`.

4. On confirmation, run the actual upload.

5. Report the resulting file ID and the web view link from the response.
