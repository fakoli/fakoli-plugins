---
name: recipe-schema-explore
description: "Discover and introspect any Google Workspace API before using it — explore methods, parameters, and types."
trigger:
  - keyword: explore api
  - keyword: discover api
  - keyword: api discovery
  - keyword: what methods
  - keyword: api parameters
---

# Explore an API Before Using It

Discover and introspect any Google Workspace API using `gws schema` before executing commands.

## When to Use

Use this workflow when the user wants to explore an unfamiliar API, check method parameters, or understand the request/response structure before making calls.

## Steps

1. **List available methods for a service:**
   ```bash
   gws <service> --help
   ```
   Example:
   ```bash
   gws drive --help
   gws sheets --help
   ```

2. **Drill into a resource:**
   ```bash
   gws drive files --help
   gws sheets spreadsheets --help
   ```

3. **Inspect method parameters:**
   ```bash
   gws schema drive.files.list
   gws schema calendar.events.insert
   ```

4. **Resolve nested type references:**
   ```bash
   gws schema sheets.spreadsheets.create --resolve-refs
   ```

5. **Inspect a specific type:**
   ```bash
   gws schema gmail.Message
   gws schema drive.File
   ```

6. **Test with a dry run:**
   ```bash
   gws drive files list \
     --params '{"pageSize": 3}' \
     --fields "files(id,name)" \
     --dry-run
   ```

7. **Execute with confidence:**
   ```bash
   gws drive files list \
     --params '{"pageSize": 3}' \
     --fields "files(id,name)"
   ```

## Tips

- Always start with `gws schema` when using an API for the first time
- Use `--resolve-refs` to see the full schema without chasing `$ref` pointers
- The schema data comes from Google's live Discovery Service — always current
- Combine `--help` (for CLI flags) with `gws schema` (for API structure)
