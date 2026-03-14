---
name: recipe-create-presentation
description: "Create a new Google Slides presentation and add initial slides."
trigger:
  - keyword: create presentation
  - keyword: new slides
  - keyword: make presentation
version: 1.0.0
---

# Create a Google Slides Presentation

Create a new Google Slides presentation and optionally share it with collaborators.

## When to Use

Use this workflow when the user wants to create a new blank presentation or set up a shared deck.

## Workflow

### 1. Create the presentation

```bash
gws slides presentations create --json '{"title": "PRESENTATION_TITLE"}'
```

Capture the presentation ID from the response.

### 2. Share with collaborators (optional)

```bash
gws drive permissions create \
  --params '{"fileId": "PRESENTATION_ID"}' \
  --json '{"role": "writer", "type": "user", "emailAddress": "collaborator@company.com"}' \
  --dry-run
```

Confirm, then execute.

### 3. Provide the link

Give the user: `https://docs.google.com/presentation/d/PRESENTATION_ID`

## Tips

- Slide content is best added through the Google Slides UI — the API for manipulating slides is very complex
- Use `"role": "reader"` for view-only access, `"writer"` for edit access
