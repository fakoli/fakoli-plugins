---
name: gws-workflow-weekly-digest
description: "Google Workflow: Weekly summary: this week's meetings + unread email count."
trigger:
  - keyword: weekly digest
  - keyword: weekly summary
  - keyword: week recap
---

# workflow +weekly-digest

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Weekly summary: this week's meetings + unread email count

## Usage

```bash
gws workflow +weekly-digest
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--format` | — | — | Output format: json (default), table, yaml, csv |

## Examples

```bash
gws workflow +weekly-digest
gws workflow +weekly-digest --format table
```

## Tips

- Read-only — never modifies data.
- Combines calendar agenda (week) with gmail triage summary.

## See Also

- **gws-shared** — Global flags and auth
- [gws-workflow](../gws-workflow/SKILL.md) — All cross-service productivity workflows commands
