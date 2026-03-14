---
name: gws-quick-ref
description: "Quick reference for gws CLI syntax — core patterns, key flags, pagination, field masks, and output formats."
trigger:
  - keyword: gws reference
  - keyword: gws syntax
  - keyword: gws flags
  - keyword: gws cheatsheet
  - keyword: how to use gws
---

# gws Quick Reference

> **Note:** See the **gws-shared** skill for auth setup and security rules.

Quick reference card for the `gws` CLI syntax and patterns.

## Core Syntax

```bash
gws <service> <resource> [sub-resource] <method> [flags]
```

### Getting Help

```bash
gws --help                              # All services
gws <service> --help                    # Service resources
gws <service> <resource> --help         # Resource methods
gws <service> <resource> <method> --help  # Method flags
```

## Key Flags

| Flag | Purpose | Example |
|------|---------|---------|
| `--params '<JSON>'` | URL/query parameters | `--params '{"userId": "me", "q": "is:unread"}'` |
| `--json '<JSON>'` | Request body (POST/PUT/PATCH) | `--json '{"name": "My File"}'` |
| `--fields '<MASK>'` | Limit response fields | `--fields "files(id,name)"` |
| `--format <FMT>` | Output format | `json`, `yaml`, `csv`, `table` |
| `--page-all` | Auto-paginate (NDJSON output) | Streams all pages |
| `--page-limit N` | Limit pagination pages | `--page-limit 3` |
| `--upload <PATH>` | Multipart file upload | `--upload ./file.pdf` |
| `--output <PATH>` | Download to file | `--output ./download.pdf` |
| `--dry-run` | Preview without executing | Shows what would happen |
| `--sanitize <TPL>` | Model Armor scan | Scans response for injection |

## Common Patterns

### 1. Reading Data (GET/LIST)

```bash
# Always use --fields to minimize response size
gws drive files list \
  --params '{"q": "name contains \"Report\"", "pageSize": 10}' \
  --fields "files(id,name,mimeType)"
```

### 2. Writing Data (POST/PUT/PATCH)

```bash
# Always --dry-run first, then execute
gws calendar events insert \
  --params '{"calendarId": "primary"}' \
  --json '{"summary": "Meeting", "start": {...}, "end": {...}}' \
  --dry-run
```

### 3. Pagination

```bash
# Auto-paginate all results (NDJSON — one JSON object per line)
gws admin users list --params '{"domain": "example.com"}' --page-all

# Limit to N pages
gws drive files list --page-limit 3
```

### 4. Schema Introspection

```bash
# Check method parameters before executing
gws schema drive.files.list
gws schema calendar.events.insert --resolve-refs
```

### 5. File Operations

```bash
# Upload (auto-detects MIME type)
gws drive files create --json '{"name": "report.pdf"}' --upload ./report.pdf

# Download
gws drive files get --params '{"fileId": "ID", "alt": "media"}' --output ./file.pdf

# Export Google Doc as PDF
gws drive files export --params '{"fileId": "ID", "mimeType": "application/pdf"}' --output doc.pdf
```

## Helper Commands (+prefix)

Helpers are service-specific shortcuts that simplify common operations:

| Service | Helpers |
|---------|---------|
| Gmail | `+send`, `+reply`, `+reply-all`, `+forward`, `+triage`, `+watch` |
| Calendar | `+agenda`, `+insert` |
| Drive | `+upload` |
| Sheets | `+read`, `+append` |
| Docs | `+write` |
| Chat | `+send` |
| Script | `+push` |
| Events | `+subscribe`, `+renew` |
| Model Armor | `+create-template`, `+sanitize-prompt`, `+sanitize-response` |
| Workflow | `+standup-report`, `+meeting-prep`, `+email-to-task`, `+weekly-digest`, `+file-announce` |

## Output Formats

| Format | Use Case |
|--------|----------|
| `json` | Default. For parsing and piping to `jq` |
| `yaml` | Human-readable structured output |
| `csv` | Tabular export for spreadsheets |
| `table` | Quick visual scan |

## Available Services

`drive`, `sheets`, `gmail`, `calendar`, `docs`, `slides`, `tasks`, `people`, `chat`, `classroom`, `forms`, `keep`, `meet`, `events`, `admin-reports`, `modelarmor`, `workflow`, `script`
