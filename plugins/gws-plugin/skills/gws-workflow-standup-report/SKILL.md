---
name: gws-workflow-standup-report
description: "Google Workflow: Today's meetings + open tasks as a standup summary."
trigger:
  - keyword: standup report
  - keyword: daily standup
  - keyword: standup
---

# workflow +standup-report

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Today's meetings + open tasks as a standup summary

## Usage

```bash
gws workflow +standup-report
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--format` | — | — | Output format: json (default), table, yaml, csv |

## Examples

```bash
gws workflow +standup-report
gws workflow +standup-report --format table
```

## Tips

- Read-only — never modifies data.
- Combines calendar agenda (today) with tasks list.

## See Also

- **gws-shared** — Global flags and auth
- [gws-workflow](../gws-workflow/SKILL.md) — All cross-service productivity workflows commands
