---
name: gws-workflow-meeting-prep
description: "Google Workflow: Prepare for your next meeting: agenda, attendees, and linked docs."
trigger:
  - keyword: meeting prep
  - keyword: prepare for meeting
  - keyword: meeting preparation
version: 1.0.0
---

# workflow +meeting-prep

> **Reference:** See the `gws-shared` skill for auth, global flags, and security rules.

Prepare for your next meeting: agenda, attendees, and linked docs

## Usage

```bash
gws workflow +meeting-prep
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--calendar` | — | primary | Calendar ID (default: primary) |
| `--format` | — | — | Output format: json (default), table, yaml, csv |

## Examples

```bash
gws workflow +meeting-prep
gws workflow +meeting-prep --calendar Work
```

## Tips

- Read-only — never modifies data.
- Shows the next upcoming event with attendees and description.

## See Also

- **gws-shared** — Global flags and auth
- [gws-workflow](../gws-workflow/SKILL.md) — All cross-service productivity workflows commands
