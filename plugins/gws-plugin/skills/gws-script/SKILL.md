---
name: gws-script
description: "Apps Script: Deploy and manage Google Apps Script projects with gws script +push."
trigger:
  - keyword: apps script
  - keyword: script push
  - keyword: deploy script
  - keyword: google apps script
  - keyword: gws script
version: 1.0.0
---

# gws script

> **Reference:** See the `gws-shared` skill for auth, global flags, and security rules.

Deploy and manage Google Apps Script projects using the `gws` CLI.

## Helper Command

### +push — Upload local files to an Apps Script project

Replaces ALL files in the target Apps Script project with files from a local directory.

```bash
gws script +push --script SCRIPT_ID
gws script +push --script SCRIPT_ID --dir ./src
```

**Supported file types:** `.gs`, `.js`, `.html`, `appsscript.json`

**Automatic behavior:**
- Skips hidden files and `node_modules`
- Replaces the entire project content (not a merge)

## Raw API Access

You can also use the Apps Script API directly:

```bash
# List script projects
gws script projects list

# Get project content
gws script projects getContent --params '{"scriptId": "SCRIPT_ID"}'

# Get project metadata
gws script projects get --params '{"scriptId": "SCRIPT_ID"}'
```

## Examples

### Deploy a script from current directory

```bash
# Check what files will be uploaded
ls *.gs *.html appsscript.json

# Push to the project
gws script +push --script 1BxTjDmEZcABxhVBmFLRfMXD4eHJB7k_g2r-example
```

### Deploy from a specific directory

```bash
gws script +push --script SCRIPT_ID --dir ./apps-script-src
```

### View current project content before pushing

```bash
gws script projects getContent --params '{"scriptId": "SCRIPT_ID"}'
```

## Caution

- `+push` **replaces all files** in the project — there is no merge or diff
- Always verify the script ID before pushing
- Consider keeping a backup of the current project content:
  ```bash
  gws script projects getContent --params '{"scriptId": "SCRIPT_ID"}' > backup.json
  ```

## Tips

- Keep your Apps Script source files in a dedicated directory (e.g., `./apps-script/`)
- Use version control (git) alongside `+push` for change tracking
- The `appsscript.json` manifest file controls runtime settings, scopes, and triggers
