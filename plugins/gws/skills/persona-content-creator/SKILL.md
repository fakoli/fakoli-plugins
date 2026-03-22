---
name: persona-content-creator
description: "Create, organize, and distribute content across Workspace."
trigger:
  - keyword: content creator
  - keyword: create content
  - keyword: content writing
version: 1.0.0
---

# Content Creator

> **Related skills:** This persona uses the following service skills for detailed API reference: `gws-docs`, `gws-drive`, `gws-gmail`, `gws-chat`, `gws-slides`

Create, organize, and distribute content across Workspace.

## Relevant Workflows
- `gws workflow +file-announce`

## Instructions
- Draft content in Google Docs with `gws docs +write`.
- Organize content assets in Drive folders — use `gws drive files list` to browse.
- Share finished content by announcing in Chat with `gws workflow +file-announce`.
- Send content review requests via email with `gws gmail +send`.
- Upload media assets to Drive with `gws drive +upload`.

## Tips
- Use `gws docs +write` for quick content updates — it handles the Docs API formatting.
- Keep a 'Content Calendar' in a shared Sheet for tracking publication schedules.
- Use `--format yaml` for human-readable output when debugging API responses.

