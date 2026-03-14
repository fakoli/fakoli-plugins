---
description: Read, create, and append content to Google Docs documents
argument-hint: "<read|write|create> [document-id] [text]"
allowed-tools: [Bash]
---

# /gws-docs

Manage Google Docs documents using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine the operation.

### Common Operations

**Read a document:**
```bash
gws docs documents get --params '{"documentId": "DOC_ID"}'
```

**Append text to a document:**
```bash
gws docs +write --document DOC_ID --text "Content to append"
```

**Create a new document:**
```bash
gws docs documents create --json '{"title": "Document Title"}'
```

## URL Handling

Extract document ID from URLs:
- `https://docs.google.com/document/d/DOC_ID/edit` → `DOC_ID`

## Tips

- The `+write` helper appends text. For rich formatting, use the raw `batchUpdate` API.
- Use `--format json` when you need to parse document structure programmatically.
- To find a document, search Drive: `gws drive files list --params '{"q": "mimeType=\"application/vnd.google-apps.document\" and name contains \"QUERY\""}' --format table`

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
