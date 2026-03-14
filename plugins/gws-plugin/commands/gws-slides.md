---
description: Read and create Google Slides presentations
argument-hint: "<read|create> [presentation-id]"
allowed-tools: [Bash]
---

# /gws-slides

Manage Google Slides presentations using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine the operation.

### Common Operations

**Read a presentation:**
```bash
gws slides presentations get --params '{"presentationId": "PRES_ID"}'
```

**Create a presentation:**
```bash
gws slides presentations create --json '{"title": "Presentation Title"}'
```

**List presentations on Drive:**
```bash
gws drive files list --params '{"q": "mimeType=\"application/vnd.google-apps.presentation\"", "pageSize": 10}' --fields "files(id,name,modifiedTime)" --format table
```

## URL Handling

Extract presentation ID from URLs:
- `https://docs.google.com/presentation/d/PRES_ID/edit` → `PRES_ID`

## Tips

- Use `gws schema slides.presentations.get` to discover available fields.
- For slide manipulation (adding slides, shapes, text), use `presentations.batchUpdate`.

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
