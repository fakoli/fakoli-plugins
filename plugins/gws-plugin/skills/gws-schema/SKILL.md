---
name: gws-schema
description: "Introspect any Google Workspace API schema — discover method parameters, request bodies, and response types before executing."
trigger:
  - keyword: schema
  - keyword: introspect api
  - keyword: api schema
  - keyword: discover method
  - keyword: what parameters
---

# gws schema

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Introspect any Google Workspace API schema at runtime. Use this **before** executing unfamiliar API calls to understand the exact parameters, request body structure, and response types.

## Why Use Schema Introspection

- **Avoid guessing** — see the exact JSON payload structure before writing `--json`
- **Discover parameters** — find required vs optional query/path parameters
- **Explore types** — inspect nested object schemas and enum values
- **Resolve references** — follow `$ref` pointers to see full type definitions

## Syntax

```bash
# Introspect a method's parameters and request/response schemas
gws schema <service>.<resource>.<method>

# Introspect a type definition
gws schema <service>.<TypeName>

# Resolve $ref pointers to inline the full schema
gws schema <service>.<resource>.<method> --resolve-refs
```

## Examples

### Discover method parameters

```bash
# What parameters does drive files list accept?
gws schema drive.files.list

# What does the request body for calendar events insert look like?
gws schema calendar.events.insert

# What fields are in a Gmail message?
gws schema gmail.Message
```

### Resolve nested references

```bash
# Inline all $ref pointers for the full picture
gws schema sheets.spreadsheets.create --resolve-refs
```

### Explore before executing

```bash
# Step 1: Check the schema
gws schema drive.permissions.create

# Step 2: Now execute with confidence
gws drive permissions create \
  --params '{"fileId": "FILE_ID"}' \
  --json '{"role": "reader", "type": "user", "emailAddress": "user@example.com"}'
```

## Tips

- Always run `gws schema` before using an unfamiliar API method
- Use `--resolve-refs` when the schema output contains `$ref` pointers you want to see inline
- Combine with `--help` for flag-level docs: `gws drive files list --help`
- The schema is fetched from Google's Discovery Service — it's always up to date
