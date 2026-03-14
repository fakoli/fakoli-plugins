---
description: >-
  Copy a Google Docs template, fill in content, and share with collaborators. Trigger when user wants to copy a google docs template, fill in content, and share with collaborators. Uses: drive, docs.
name: recipe-create-doc-from-template
version: 1.0.0
---

# Create a Google Doc from a Template

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-drive`, `gws-docs`

Copy a Google Docs template, fill in content, and share with collaborators.

## Steps

1. Copy the template: `gws drive files copy --params '{"fileId": "TEMPLATE_DOC_ID"}' --json '{"name": "Project Brief - Q2 Launch"}'`
2. Get the new doc ID from the response
3. Add content: `gws docs +write --document-id NEW_DOC_ID --text '## Project: Q2 Launch

### Objective
Launch the new feature by end of Q2.'`
4. Share with team: `gws drive permissions create --params '{"fileId": "NEW_DOC_ID"}' --json '{"role": "writer", "type": "user", "emailAddress": "team@company.com"}'`

