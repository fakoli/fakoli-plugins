---
name: gws-sheets-append
description: "Google Sheets: Append a row to a spreadsheet."
trigger:
  - keyword: append sheet
  - keyword: add row
  - keyword: sheets append
  - keyword: add to spreadsheet
---

# sheets +append

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Append a row to a spreadsheet

## Usage

```bash
gws sheets +append --spreadsheet <ID>
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--spreadsheet` | ✓ | — | Spreadsheet ID |
| `--values` | — | — | Comma-separated values (simple strings) |
| `--json-values` | — | — | JSON array of rows, e.g. '[["a","b"],["c","d"]]' |

## Examples

```bash
gws sheets +append --spreadsheet ID --values 'Alice,100,true'
gws sheets +append --spreadsheet ID --json-values '[["a","b"],["c","d"]]'
```

## Tips

- Use --values for simple single-row appends.
- Use --json-values for bulk multi-row inserts.

> [!CAUTION]
> This is a **write** command — confirm with the user before executing.

## See Also

- **gws-shared** — Global flags and auth
- [gws-sheets](../gws-sheets/SKILL.md) — All read and write spreadsheets commands
